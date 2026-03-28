"""Scan simulator dialog — lets developers trigger fake scans without NFC/QR hardware.

Visible only when config.debug is True. Provides a text field for a member's
pass_serial and a method selector (NFC / QR), then emits a signal that
MainWindow wires into its normal _do_scan flow.
"""

from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
)

from . import styles
from .shadows import NEO_RADIUS_XL, paint_neo_raised
from .widgets import NeoButton, NeoInput


class SimulatorDialog(QDialog):
    """Neumorphic dialog for simulating NFC/QR scans in debug mode."""

    scan_requested = pyqtSignal(str, str)  # (serial, method)

    def __init__(self, api_client, parent=None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(440, 360)
        self.setStyleSheet(styles.GLOBAL_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(300)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        rect = QRectF(12, 12, self.width() - 24, self.height() - 24)
        paint_neo_raised(p, rect, radius=NEO_RADIUS_XL, distance=10)
        p.end()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 36, 36, 28)
        root.setSpacing(14)

        title = QLabel("Scan Simulator")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {styles.TEXT_PRIMARY}; "
            f"background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        root.addWidget(title)

        subtitle = QLabel("Simulate a member scan without hardware")
        subtitle.setStyleSheet(styles.FONT_SMALL)
        root.addWidget(subtitle)

        root.addSpacing(4)

        # Serial input
        serial_label = QLabel("Pass Serial (UUID)")
        serial_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {styles.TEXT_SECONDARY}; "
            f"background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        root.addWidget(serial_label)

        self._serial_input = NeoInput("e.g. a1b2c3d4-…")
        root.addWidget(self._serial_input)

        root.addSpacing(4)

        # Method selector
        method_label = QLabel("Scan Method")
        method_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {styles.TEXT_SECONDARY}; "
            f"background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        root.addWidget(method_label)

        method_row = QHBoxLayout()
        radio_style = (
            f"color: {styles.TEXT_PRIMARY}; background: transparent; "
            f"font-size: 13px; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        self._radio_nfc = QRadioButton("NFC")
        self._radio_nfc.setStyleSheet(radio_style)
        self._radio_nfc.setChecked(True)
        self._radio_qr = QRadioButton("QR")
        self._radio_qr.setStyleSheet(radio_style)
        method_row.addWidget(self._radio_nfc)
        method_row.addWidget(self._radio_qr)
        method_row.addStretch()
        root.addLayout(method_row)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(
            f"font-size: 11px; color: {styles.ACCENT_RED}; background: transparent; "
            f"font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        root.addWidget(self._error_label)

        root.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        close_btn = NeoButton(text="Close")
        close_btn.setFixedSize(100, 44)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        scan_btn = NeoButton(text="Scan")
        scan_btn.setFixedSize(100, 44)
        scan_btn.clicked.connect(self._do_scan)
        btn_row.addWidget(scan_btn)

        root.addLayout(btn_row)

    def _do_scan(self) -> None:
        serial = self._serial_input.text().strip()
        if not serial:
            self._error_label.setText("Enter a pass serial UUID.")
            return

        method = "nfc" if self._radio_nfc.isChecked() else "qr"
        self._error_label.setText("")
        self.scan_requested.emit(serial, method)
        self.accept()
