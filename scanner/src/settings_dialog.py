"""Settings dialog — neumorphic frameless dialog requiring PIN (api key) to open."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from .config import ScannerConfig, save_config
from .shadows import apply_raised_shadow
from .styles import ACCENT_BLUE, ACCENT_GREEN, CARD_RAISED, GLOBAL_STYLE, TEXT_PRIMARY
from .widgets import NeoButton, NeoInput


class SettingsDialog(QDialog):
    """Configuration dialog that persists changes to config.json."""

    def __init__(self, config: ScannerConfig, api_client, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.api_client = api_client
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setFixedSize(480, 540)
        self.setStyleSheet(GLOBAL_STYLE + CARD_RAISED)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel("Scanner Settings")
        title.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {TEXT_PRIMARY};")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)

        self.api_url_input = NeoInput(self.config.api_base_url)
        self.api_url_input.setText(self.config.api_base_url)
        form.addRow("API URL", self.api_url_input)

        self.api_key_input = NeoInput("API Key")
        self.api_key_input.setText(self.config.api_key)
        self.api_key_input.setEchoMode(NeoInput.EchoMode.Password)
        form.addRow("API Key", self.api_key_input)

        self.scanner_id_input = NeoInput("Scanner ID")
        self.scanner_id_input.setText(self.config.scanner_id)
        form.addRow("Scanner ID", self.scanner_id_input)

        self.lat_input = NeoInput("Latitude")
        self.lat_input.setText(str(self.config.geofence_lat))
        form.addRow("Geofence Lat", self.lat_input)

        self.lng_input = NeoInput("Longitude")
        self.lng_input.setText(str(self.config.geofence_lng))
        form.addRow("Geofence Lng", self.lng_input)

        self.webcam_input = NeoInput("0")
        self.webcam_input.setText(str(self.config.webcam_index))
        form.addRow("Webcam Index", self.webcam_input)

        self.selfie_check = QCheckBox("Enable selfie capture on QR scan")
        self.selfie_check.setChecked(self.config.qr_selfie_enabled)
        form.addRow("", self.selfie_check)

        root.addLayout(form)
        root.addSpacing(12)

        # Test connection button
        btn_row = QHBoxLayout()
        test_btn = NeoButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(test_btn)

        save_btn = NeoButton("Save")
        save_btn.setStyleSheet(
            save_btn.styleSheet()
            + f"QPushButton {{ background-color: {ACCENT_BLUE}; color: white; }}"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = NeoButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        root.addLayout(btn_row)

    def _test_connection(self) -> None:
        # Temporarily update client config for the test
        self.api_client.base_url = self.api_url_input.text().rstrip("/")
        self.api_client.headers["X-Scanner-Key"] = self.api_key_input.text()
        ok = self.api_client.test_connection()
        QMessageBox.information(
            self,
            "Connection Test",
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
