"""Main scanner window — neumorphic kiosk UI with NFC + QR scanning."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QFont, QImage, QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .api_client import ApiClient
from .config import ScannerConfig
from .nfc_reader import NfcReaderThread
from .offline import OfflineManager
from .qr_reader import QrReaderThread
from .settings_dialog import SettingsDialog
from .shadows import apply_raised_shadow
from .widgets import EventLogWidget, NeoButton, NeoCard, StatusPill


class MainWindow(QWidget):
    """Frameless neumorphic scanner window with three zones."""

    def __init__(self, config: ScannerConfig) -> None:
        super().__init__()
        self.config = config
        self.api = ApiClient(config)
        self.offline = OfflineManager(config.offline_cache_path, config.api_key or "dev")
        self._online = False
        self._cache_version = 0
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setStyleSheet(styles.GLOBAL_STYLE)
        self.setMinimumSize(900, 640)

        self._build_ui()
        self._start_threads()
        self._start_timers()

    # ------------------------------------------------------------------ UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_main_card(), stretch=1)
        root.addWidget(self._build_bottom_tray())

    # -- Top bar --

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(styles.TOP_BAR_STYLE)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel(f"Meridian  \u2022  {self.config.scanner_id}")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {styles.TEXT_PRIMARY};")
        lay.addWidget(title)

        lay.addStretch()

        self.pill_api = StatusPill("API")
        self.pill_nfc = StatusPill("NFC")
        self.pill_queue = StatusPill("Queue: 0")
        for pill in (self.pill_api, self.pill_nfc, self.pill_queue):
            lay.addWidget(pill)

        settings_btn = NeoButton("\u2699")
        settings_btn.setFixedSize(40, 40)
        settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(settings_btn)

        return bar

    # -- Main result card --

    def _build_main_card(self) -> QWidget:
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 16, 32, 16)

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        # Page 0: idle
        idle_card = NeoCard()
        idle_lay = QVBoxLayout(idle_card)
        self._idle_label = QLabel("Ready to Scan")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_label.setStyleSheet(
            f"font-size: 32px; font-weight: 300; color: {styles.TEXT_SECONDARY};"
        )
        idle_lay.addWidget(self._idle_label)
        self._idle_sub = QLabel("Tap NFC or show QR code")
        self._idle_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_sub.setStyleSheet(f"font-size: 16px; color: {styles.TEXT_SECONDARY};")
        idle_lay.addWidget(self._idle_sub)

        # Breathing shadow animation
        self._idle_shadow = apply_raised_shadow(idle_card)
        self._breath_anim = QPropertyAnimation(self._idle_shadow, b"blurRadius", self)
        self._breath_anim.setDuration(3000)
        self._breath_anim.setStartValue(8)
        self._breath_anim.setEndValue(18)
        self._breath_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._breath_anim.setLoopCount(-1)
        self._breath_anim.start()

        self._stack.addWidget(idle_card)

        # Page 1: success
        success_card = NeoCard()
        success_lay = QVBoxLayout(success_card)
        self._success_name = QLabel("")
        self._success_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_name.setStyleSheet(f"font-size: 36px; font-weight: 700; color: {styles.ACCENT_GREEN};")
        success_lay.addWidget(self._success_name)
        self._success_detail = QLabel("")
        self._success_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_detail.setStyleSheet(f"font-size: 18px; color: {styles.TEXT_PRIMARY};")
        success_lay.addWidget(self._success_detail)
        self._stack.addWidget(success_card)

        # Page 2: error
        error_card = NeoCard()
        error_lay = QVBoxLayout(error_card)
        self._error_msg = QLabel("")
        self._error_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_msg.setWordWrap(True)
        self._error_msg.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {styles.ACCENT_RED};")
        error_lay.addWidget(self._error_msg)
        self._stack.addWidget(error_card)

        return container

    # -- Bottom tray --

    def _build_bottom_tray(self) -> QFrame:
        tray = QFrame()
        tray.setStyleSheet(styles.BOTTOM_TRAY_STYLE)
        lay = QHBoxLayout(tray)
        lay.setContentsMargins(16, 8, 16, 8)

        # Left: webcam preview
        self._webcam_label = QLabel("No webcam feed")
        self._webcam_label.setFixedSize(320, 200)
        self._webcam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._webcam_label.setStyleSheet(
            f"background: #D0D5DC; border-radius: 12px; color: {styles.TEXT_SECONDARY};"
        )
        lay.addWidget(self._webcam_label)

        # Right: event log
        self._event_log = EventLogWidget()
        lay.addWidget(self._event_log, stretch=1)

        return tray

    # ----------------------------------------------------------------- Threads

    def _start_threads(self) -> None:
        self._nfc_thread = NfcReaderThread()
        self._nfc_thread.card_detected.connect(self._on_nfc_scan)
        self._nfc_thread.reader_status.connect(self._on_nfc_status)
        self._nfc_thread.start()

        self._qr_thread = QrReaderThread(
            webcam_index=self.config.webcam_index,
            selfie_enabled=self.config.qr_selfie_enabled,
        )
        self._qr_thread.frame_ready.connect(self._on_frame)
        self._qr_thread.qr_detected.connect(self._on_qr_scan)
        self._qr_thread.start()

    # ----------------------------------------------------------------- Timers

    def _start_timers(self) -> None:
        # Heartbeat every 30s
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._do_heartbeat)
        self._heartbeat_timer.start(30_000)
        # Initial heartbeat
        QTimer.singleShot(1000, self._do_heartbeat)

        # Queue flush every 60s
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_offline_queue)
        self._flush_timer.start(60_000)

    # ----------------------------------------------------------------- Scan handling

    def _parse_uri(self, uri: str) -> dict:
        """Parse frcattend:// URI into components."""
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        return {
            "action": parsed.netloc,  # "checkin" or "totp"
            "serial": params.get("serial", [""])[0],
            "payload": params.get("payload", [""])[0],
            "code": params.get("code", [""])[0],
        }

    def _on_nfc_scan(self, uri: str) -> None:
        parts = self._parse_uri(uri)
        self._do_scan(
            serial=parts["serial"],
            method="nfc",
            nfc_payload=uri,
            totp_code=None,
            selfie_b64=None,
        )

    def _on_qr_scan(self, uri: str, selfie_b64: str) -> None:
        parts = self._parse_uri(uri)
        self._do_scan(
            serial=parts["serial"],
            method="qr",
            nfc_payload=None,
            totp_code=parts["code"],
            selfie_b64=selfie_b64 or None,
        )

    def _do_scan(
        self,
        serial: str,
        method: str,
        nfc_payload: str | None,
        totp_code: str | None,
        selfie_b64: str | None,
    ) -> None:
        """Attempt check-in; if already checked in, try check-out."""
        try:
            result = self.api.checkin(serial, nfc_payload, totp_code, method, selfie_b64)
            name = result.get("member_name", "Member")
            self._show_success(name, "Checked In")
            self._event_log.add_event(f"\u2714 {name} checked in", success=True)
        except Exception as checkin_err:
            # If 409 (already checked in), try checkout
            err_text = str(checkin_err)
            if "409" in err_text:
                try:
                    result = self.api.checkout(serial, nfc_payload, totp_code, method, selfie_b64)
                    name = result.get("member_name", "Member")
                    dur = result.get("duration_minutes", 0)
                    self._show_success(name, f"Checked Out \u2022 {dur} min")
                    self._event_log.add_event(f"\u2714 {name} out ({dur}m)", success=True)
                except Exception as checkout_err:
                    self._handle_scan_error(checkout_err, serial, method, nfc_payload, totp_code, selfie_b64, "checkout")
            else:
                self._handle_scan_error(checkin_err, serial, method, nfc_payload, totp_code, selfie_b64, "checkin")

        # Resume scanning after display period
        QTimer.singleShot(4000, self._return_to_idle)

    def _handle_scan_error(self, err, serial, method, nfc_payload, totp_code, selfie_b64, action) -> None:
        err_text = str(err)
        if self._online:
            self._show_error(f"Scan failed: {err_text[:80]}")
            self._event_log.add_event(f"\u2718 Error: {err_text[:50]}", success=False)
        else:
            # Queue for offline processing
            self.offline.queue_event({
                "serial": serial,
                "nfc_payload": nfc_payload,
                "totp_code": totp_code,
                "method": method,
                "selfie_base64": selfie_b64,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._show_error("Offline \u2022 Scan queued")
            self._event_log.add_event(f"\u23F3 Queued offline scan", success=False)
            self._update_queue_pill()

    # ----------------------------------------------------------------- Display states

    def _show_success(self, name: str, detail: str) -> None:
        self._success_name.setText(name)
        self._success_detail.setText(detail)
        self._stack.setCurrentIndex(1)

    def _show_error(self, message: str) -> None:
        self._error_msg.setText(message)
        self._stack.setCurrentIndex(2)

    def _return_to_idle(self) -> None:
        self._stack.setCurrentIndex(0)
        self._qr_thread.resume()

    # ----------------------------------------------------------------- Webcam preview

    def _on_frame(self, qimg: QImage) -> None:
        pix = QPixmap.fromImage(qimg).scaled(
            self._webcam_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._webcam_label.setPixmap(pix)

    # ----------------------------------------------------------------- Status

    def _on_nfc_status(self, connected: bool) -> None:
        if connected:
            self.pill_nfc.set_active("NFC")
        else:
            self.pill_nfc.set_error("NFC")

    def _do_heartbeat(self) -> None:
        try:
            resp = self.api.heartbeat(self.config.scanner_id, self._cache_version, self.offline.queue_count)
            self._online = True
            self.pill_api.set_active("API")
            if resp.get("cache_stale"):
                self._refresh_cache()
        except Exception:
            self._online = False
            self.pill_api.set_error("API")

    def _refresh_cache(self) -> None:
        try:
            cache_data = self.api.fetch_cache()
            self.offline.save_cache(cache_data)
            self._cache_version = cache_data.get("cache_version", self._cache_version + 1)
        except Exception:
            pass

    def _flush_offline_queue(self) -> None:
        if not self._online:
            return
        pending = self.offline.get_pending_events()
        if not pending:
            return
        events = [e["payload"] for e in pending]
        try:
            result = self.api.flush_queue(events)
            ids = [e["id"] for e in pending]
            self.offline.mark_synced(ids)
            self._update_queue_pill()
            processed = result.get("processed", 0)
            self._event_log.add_event(f"\u2191 Synced {processed} offline events", success=True)
        except Exception:
            pass

    def _update_queue_pill(self) -> None:
        count = self.offline.queue_count
        if count > 0:
            self.pill_queue.set_error(f"Queue: {count}")
        else:
            self.pill_queue.set_active("Queue: 0")

    # ----------------------------------------------------------------- Settings

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config, self.api, self)
        if dlg.exec():
            # Restart threads with new config
            self._nfc_thread.stop()
            self._qr_thread.stop()
            self.api.close()
            self.api = ApiClient(self.config)
            self.offline = OfflineManager(self.config.offline_cache_path, self.config.api_key or "dev")
            self._start_threads()

    # ----------------------------------------------------------------- Window drag

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 60:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None

    # ----------------------------------------------------------------- Cleanup

    def closeEvent(self, event) -> None:
        self._nfc_thread.stop()
        self._qr_thread.stop()
        self.api.close()
        super().closeEvent(event)
