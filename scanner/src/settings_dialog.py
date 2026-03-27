"""Settings dialog — neumorphic frameless dialog using painted widgets."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .config import ScannerConfig, save_config
from .shadows import paint_neo_raised, NEO_RADIUS
from .widgets import NeoButton, NeoInput


class SettingsDialog(QDialog):
    """Configuration dialog with neumorphic card background."""

    def __init__(self, config: ScannerConfig, api_client, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.api_client = api_client
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(500, 580)
        self.setStyleSheet(styles.GLOBAL_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        rect = QRectF(12, 12, self.width() - 24, self.height() - 24)
        paint_neo_raised(p, rect, radius=24, distance=10)
        p.end()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 36, 36, 28)
        root.setSpacing(16)

        title = QLabel("Scanner Settings")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {styles.TEXT_PRIMARY}; background: transparent;")
        root.addWidget(title)

        subtitle = QLabel("Configure connection and hardware")
        subtitle.setStyleSheet(styles.FONT_SMALL)
        root.addWidget(subtitle)

        root.addSpacing(4)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {styles.TEXT_SECONDARY}; background: transparent;")
            return lbl

        self.api_url_input = NeoInput(self.config.api_base_url)
        self.api_url_input.setText(self.config.api_base_url)
        form.addRow(_label("API URL"), self.api_url_input)

        self.api_key_input = NeoInput("API Key")
        self.api_key_input.setText(self.config.api_key)
        self.api_key_input.setEchoMode(self.api_key_input.EchoMode.Password)
        form.addRow(_label("API Key"), self.api_key_input)

        self.scanner_id_input = NeoInput("Scanner ID")
        self.scanner_id_input.setText(self.config.scanner_id)
        form.addRow(_label("Scanner ID"), self.scanner_id_input)

        self.lat_input = NeoInput("Latitude")
        self.lat_input.setText(str(self.config.geofence_lat))
        form.addRow(_label("Latitude"), self.lat_input)

        self.lng_input = NeoInput("Longitude")
        self.lng_input.setText(str(self.config.geofence_lng))
        form.addRow(_label("Longitude"), self.lng_input)

        self.webcam_input = NeoInput("0")
        self.webcam_input.setText(str(self.config.webcam_index))
        form.addRow(_label("Webcam #"), self.webcam_input)

        self.selfie_check = QCheckBox("Enable selfie capture on QR scan")
        self.selfie_check.setChecked(self.config.qr_selfie_enabled)
        self.selfie_check.setStyleSheet(f"color: {styles.TEXT_PRIMARY}; background: transparent; font-size: 13px;")
        form.addRow(_label(""), self.selfie_check)

        root.addLayout(form)
        root.addStretch()

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        test_btn = NeoButton(text="Test Connection")
        test_btn.setFixedSize(140, 44)
        test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(test_btn)

        btn_row.addStretch()

        cancel_btn = NeoButton(text="Cancel")
        cancel_btn.setFixedSize(100, 44)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = NeoButton(text="Save")
        save_btn.setFixedSize(100, 44)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        root.addLayout(btn_row)

    def _test_connection(self) -> None:
        self.api_client.base_url = self.api_url_input.text().rstrip("/")
        self.api_client.headers["X-Scanner-Key"] = self.api_key_input.text()
        ok = self.api_client.test_connection()
        QMessageBox.information(
            self, "Connection Test",
            "Connected successfully!" if ok else "Connection failed. Check URL and API key.",
        )

    def _save(self) -> None:
        self.config.api_base_url = self.api_url_input.text()
        self.config.api_key = self.api_key_input.text()
        self.config.scanner_id = self.scanner_id_input.text()
        self.config.geofence_lat = float(self.lat_input.text() or 0)
        self.config.geofence_lng = float(self.lng_input.text() or 0)
        self.config.webcam_index = int(self.webcam_input.text() or 0)
        self.config.qr_selfie_enabled = self.selfie_check.isChecked()
        save_config(self.config)
        self.accept()
