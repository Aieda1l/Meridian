"""Settings dialog — neumorphic frameless dialog using painted widgets."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .config import ScannerConfig, save_config
from .shadows import paint_neo_raised, NEO_RADIUS, NEO_RADIUS_XL
from .neo_alert import NeoAlertPopup
from .widgets import NeoButton, NeoInput


class AdminLoginDialog(QDialog):
    """Small neumorphic dialog that authenticates an admin via the backend API."""

    def __init__(self, api_client, parent=None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._authenticated = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(400, 340)
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

        title = QLabel("Admin Login")
        title.setStyleSheet(
            f"font-size: 20px; font-weight: 700; color: {styles.TEXT_PRIMARY}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        root.addWidget(title)

        subtitle = QLabel("Sign in with an admin account to access settings")
        subtitle.setStyleSheet(styles.FONT_SMALL)
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        root.addSpacing(4)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {styles.TEXT_SECONDARY}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
            )
            return lbl

        self.email_input = NeoInput("admin@team.org")
        form.addRow(_label("Email"), self.email_input)

        self.password_input = NeoInput("Password")
        self.password_input.setEchoMode(self.password_input.EchoMode.Password)
        form.addRow(_label("Password"), self.password_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(
            f"font-size: 11px; color: {styles.ACCENT_RED}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;"
        )
        self._error_label.setWordWrap(True)
        form.addRow(_label(""), self._error_label)

        root.addLayout(form)
        root.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = NeoButton(text="Cancel")
        cancel_btn.setFixedSize(100, 44)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        login_btn = NeoButton(text="Login")
        login_btn.setFixedSize(100, 44)
        login_btn.clicked.connect(self._do_login)
        btn_row.addWidget(login_btn)

        root.addLayout(btn_row)

    def _do_login(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not email or not password:
            self._error_label.setText("Please enter email and password.")
            return
        try:
            result = self.api_client.admin_login(email, password)
            role = result.get("role", "")
            if role not in ("admin", "mentor"):
                self._error_label.setText("Access denied. Admin or mentor role required.")
                return
            self._authenticated = True
            self.accept()
        except Exception as exc:
            err = str(exc)
            if "401" in err:
                self._error_label.setText("Invalid email or password.")
            elif "Connection" in err or "connect" in err.lower():
                self._error_label.setText("Cannot reach the server. Check your network.")
            else:
                self._error_label.setText(f"Login failed: {err[:80]}")

    @property
    def authenticated(self) -> bool:
        return self._authenticated


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
        root.setSpacing(16)

        title = QLabel("Scanner Settings")
        title.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {styles.TEXT_PRIMARY}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;")
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
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {styles.TEXT_SECONDARY}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;")
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

        self.webcam_input = NeoInput("0")
        self.webcam_input.setText(str(self.config.webcam_index))
        form.addRow(_label("Webcam #"), self.webcam_input)

        self.selfie_check = QCheckBox("Enable selfie capture on QR scan")
        self.selfie_check.setChecked(self.config.qr_selfie_enabled)
        self.selfie_check.setStyleSheet(f"color: {styles.TEXT_PRIMARY}; background: transparent; font-size: 13px; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;")
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
        if ok:
            NeoAlertPopup.success(self, "Connected successfully!")
        else:
            NeoAlertPopup.error(self, "Connection failed. Check URL and API key.")

    def _save(self) -> None:
        self.config.api_base_url = self.api_url_input.text()
        self.config.api_key = self.api_key_input.text()
        self.config.scanner_id = self.scanner_id_input.text()
        self.config.webcam_index = int(self.webcam_input.text() or 0)
        self.config.qr_selfie_enabled = self.selfie_check.isChecked()
        save_config(self.config)
        self.accept()
