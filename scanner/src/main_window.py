"""Main scanner window — neumorphic kiosk UI with NFC + QR scanning.

Three zones:
  1. Top bar  (64 px)  — title, status pills, settings button
  2. Main card (flex)   — stacked idle / success / error states
  3. Bottom tray (240px)— webcam preview + event log
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
from functools import partial
from urllib.parse import parse_qs, urlparse

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QSize,
    Qt,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import styles
from .api_client import ApiClient
from .config import ScannerConfig
from .exceptions import ApiError
from .nfc_reader import NfcReaderThread
from .offline import OfflineManager
from .qr_reader import QrReaderThread
from .settings_dialog import AdminLoginDialog, SettingsDialog
from .shadows import (
    NEO_BASE,
    NEO_DISTANCE,
    NEO_RADIUS,
    NEO_RADIUS_SM,
    NEO_RADIUS_LG,
    NEO_RADIUS_XL,
    paint_neo_inset,
    paint_neo_raised,
)
from .simulator_dialog import SimulatorDialog
from .widgets import EventLogWidget, NeoButton, NeoCard, StatusPill

# ───────────────────────────────────────────────────────────────────────
# Timing constants
# ───────────────────────────────────────────────────────────────────────

SUCCESS_DISPLAY_MS = 2500          # How long to show the success/error card
HEARTBEAT_INTERVAL_MS = 30_000     # API heartbeat interval
QUEUE_FLUSH_INTERVAL_MS = 60_000   # Offline queue flush interval
INITIAL_HEARTBEAT_DELAY_MS = 1000  # Delay before first heartbeat
THREAD_STOP_TIMEOUT_MS = 5000      # Max wait for threads to stop


# ───────────────────────────────────────────────────────────────────────
# Painted top bar
# ───────────────────────────────────────────────────────────────────────

class _TopBar(QWidget):
    """Top bar with a subtle bottom shadow edge, painted neumorphically."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height() + 12)
        paint_neo_raised(p, rect, radius=0, distance=4, blur=8)
        p.end()


# ───────────────────────────────────────────────────────────────────────
# Painted webcam frame (inset)
# ───────────────────────────────────────────────────────────────────────

class _WebcamFrame(QWidget):
    """Inset neumorphic frame that displays the webcam feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setFixedSize(300, 200)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_pixmap(self, pm: QPixmap) -> None:
        self._pixmap = pm
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        margin = 6
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)
        paint_neo_inset(p, rect, radius=NEO_RADIUS_SM, distance=4)

        if self._pixmap and not self._pixmap.isNull():
            inner = rect.adjusted(5, 5, -5, -5)
            scaled = self._pixmap.scaled(
                int(inner.width()), int(inner.height()),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            x = inner.left() + (inner.width() - scaled.width()) / 2
            y = inner.top() + (inner.height() - scaled.height()) / 2
            p.drawPixmap(int(x), int(y), scaled)
        else:
            p.setPen(QColor(styles.TEXT_MUTED))
            font = QFont("Nunito Sans", 10)
            font.setWeight(QFont.Weight.Light)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No webcam feed")

        p.end()


# ───────────────────────────────────────────────────────────────────────
# Bottom tray
# ───────────────────────────────────────────────────────────────────────

class _BottomTray(QWidget):
    """Bottom tray with a subtle top shadow edge."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(240)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, -12, self.width(), self.height() + 12)
        paint_neo_raised(p, rect, radius=0, distance=4, blur=8)
        p.end()


# ───────────────────────────────────────────────────────────────────────
# Main Window
# ───────────────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    """Frameless neumorphic scanner kiosk window."""

    def __init__(self, config: ScannerConfig) -> None:
        super().__init__()
        self.config = config
        self.api = ApiClient(config)
        self.offline = OfflineManager(config.offline_cache_path, config.api_key or "dev")
        self._online = False
        self._cache_version = 0
        self._scan_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            #| Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet(styles.GLOBAL_STYLE)

        self._build_ui()
        self._start_threads()
        self._start_timers()

    # ================================================================= UI

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_top_bar())
        root.addWidget(self._build_main_area(), stretch=1)
        root.addWidget(self._build_bottom_tray())

    # -- Top bar --------------------------------------------------------

    def _build_top_bar(self) -> QWidget:
        bar = _TopBar()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(24, 0, 24, 0)
        lay.setSpacing(12)

        # Title
        title = QLabel(f"Meridian  \u2022  {self.config.scanner_id}")
        title.setStyleSheet(styles.FONT_TITLE)
        lay.addWidget(title)

        lay.addStretch()

        # Status pills
        self.pill_api = StatusPill("API")
        self.pill_nfc = StatusPill("NFC")
        self.pill_queue = StatusPill("Queue: 0")
        self.pill_queue.setMinimumWidth(110)
        for pill in (self.pill_api, self.pill_nfc, self.pill_queue):
            lay.addWidget(pill)

        lay.addSpacing(8)

        # Simulator button (debug mode only)
        if self.config.debug:
            sim_btn = NeoButton(text="SIM")
            sim_btn.setFixedSize(64, 48)
            sim_btn.clicked.connect(self._open_simulator)
            lay.addWidget(sim_btn)

        # Settings button
        settings_btn = NeoButton(icon_text="\u2699\uFE0F")
        settings_btn.setFixedSize(48, 48)
        settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(settings_btn)

        return bar

    # -- Main area (stacked card) ----------------------------------------

    def _build_main_area(self) -> QWidget:
        container = QWidget()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(40, 20, 40, 20)

        self._stack = QStackedWidget()
        self._stack.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay.addWidget(self._stack)

        # -- Page 0: idle -----------------------------------------------
        idle_card = NeoCard()
        idle_inner = QVBoxLayout(idle_card)
        idle_inner.setContentsMargins(40, 40, 40, 40)
        idle_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # NFC icon (large)
        nfc_icon = QLabel("\U0001F4F3")
        nfc_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nfc_icon.setStyleSheet("font-size: 56px; background: transparent;")
        idle_inner.addWidget(nfc_icon)

        idle_inner.addSpacing(12)

        self._idle_label = QLabel("Ready to Scan")
        self._idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_label.setStyleSheet(styles.FONT_HEADING)
        idle_inner.addWidget(self._idle_label)

        self._idle_sub = QLabel("Tap your NFC pass or show a QR code")
        self._idle_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._idle_sub.setStyleSheet(styles.FONT_SUBHEAD)
        idle_inner.addWidget(self._idle_sub)

        # Breathing shadow animation — matches CSS neo-breathe:
        #   0%,100% { box-shadow: 6px 6px 12px }  (shadow_spread = 6)
        #   50%     { box-shadow: 8px 8px 16px }  (shadow_spread = 10)
        # Uses sequential group (forward + reverse) for smooth ping-pong.
        self._idle_card = idle_card

        fwd = QPropertyAnimation(idle_card, b"shadow_spread", idle_card)
        fwd.setDuration(1500)                         # half of 3s cycle
        fwd.setStartValue(6.0)
        fwd.setEndValue(10.0)
        fwd.setEasingCurve(QEasingCurve.Type.InOutSine)

        rev = QPropertyAnimation(idle_card, b"shadow_spread", idle_card)
        rev.setDuration(1500)
        rev.setStartValue(10.0)
        rev.setEndValue(6.0)
        rev.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._breath_group = QSequentialAnimationGroup(idle_card)
        self._breath_group.addAnimation(fwd)
        self._breath_group.addAnimation(rev)
        self._breath_group.setLoopCount(-1)            # infinite
        self._breath_group.start()

        self._stack.addWidget(idle_card)

        # -- Page 1: success --------------------------------------------
        success_card = NeoCard()
        success_inner = QVBoxLayout(success_card)
        success_inner.setContentsMargins(40, 40, 40, 40)
        success_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        success_icon = QLabel("\u2705")
        success_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_icon.setStyleSheet("font-size: 52px; background: transparent;")
        success_inner.addWidget(success_icon)

        success_inner.addSpacing(8)

        self._success_name = QLabel("")
        self._success_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_name.setStyleSheet(f"{styles.FONT_LARGE} color: {styles.ACCENT_GREEN};")
        success_inner.addWidget(self._success_name)

        self._success_detail = QLabel("")
        self._success_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_detail.setStyleSheet(styles.FONT_SUBHEAD)
        success_inner.addWidget(self._success_detail)

        self._stack.addWidget(success_card)

        # -- Page 2: error ----------------------------------------------
        error_card = NeoCard()
        error_inner = QVBoxLayout(error_card)
        error_inner.setContentsMargins(40, 40, 40, 40)
        error_inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        error_icon = QLabel("\u274C")
        error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_icon.setStyleSheet("font-size: 52px; background: transparent;")
        error_inner.addWidget(error_icon)

        error_inner.addSpacing(8)

        self._error_msg = QLabel("")
        self._error_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_msg.setWordWrap(True)
        self._error_msg.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {styles.ACCENT_RED}; background: transparent; font-family: 'Nunito Sans', 'Segoe UI', sans-serif;")
        error_inner.addWidget(self._error_msg)

        self._stack.addWidget(error_card)

        return container

    # -- Bottom tray ----------------------------------------------------

    def _build_bottom_tray(self) -> QWidget:
        tray = _BottomTray()
        lay = QHBoxLayout(tray)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(16)

        # Webcam preview (inset frame)
        self._webcam_frame = _WebcamFrame()
        lay.addWidget(self._webcam_frame)

        # Event log
        self._event_log = EventLogWidget()
        lay.addWidget(self._event_log, stretch=1)

        return tray

    # ================================================================= Threads

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

    # ================================================================= Timers

    def _start_timers(self) -> None:
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timer.timeout.connect(self._do_heartbeat)
        self._heartbeat_timer.start(HEARTBEAT_INTERVAL_MS)
        QTimer.singleShot(INITIAL_HEARTBEAT_DELAY_MS, self._do_heartbeat)

        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_offline_queue)
        self._flush_timer.start(QUEUE_FLUSH_INTERVAL_MS)

    # ================================================================= Scan handling

    def _parse_uri(self, uri: str) -> dict:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        return {
            "action": parsed.netloc,
            "serial": params.get("serial", [""])[0],
            "payload": params.get("payload", [""])[0],
            "code": params.get("code", [""])[0],
        }

    def _on_nfc_scan(self, uri: str) -> None:
        parts = self._parse_uri(uri)
        self._do_scan(serial=parts["serial"], method="nfc",
                       nfc_payload=uri, totp_code=None, selfie_b64=None)

    def _on_qr_scan(self, uri: str, selfie_b64: str) -> None:
        parts = self._parse_uri(uri)
        self._do_scan(serial=parts["serial"], method="qr",
                       nfc_payload=None, totp_code=parts["code"],
                       selfie_b64=selfie_b64 or None)

    def _do_scan(self, serial, method, nfc_payload, totp_code, selfie_b64) -> None:
        """Submit the scan to the backend in a background thread.

        The GUI stays responsive while the HTTP request is in flight.
        A QTimer poll (every 50 ms) picks up the result and updates the UI
        on the main thread once the future completes.
        """
        # Show a "processing" state immediately
        self._idle_label.setText("Processing…")
        self._idle_sub.setText("")

        future = self._scan_pool.submit(
            self._scan_worker, serial, method, nfc_payload, totp_code, selfie_b64,
        )

        # Poll for completion via a single-shot timer chain (keeps us on the
        # main thread for all Qt widget updates).
        def _check_future():
            if not future.done():
                QTimer.singleShot(50, _check_future)
                return
            try:
                result_type, payload = future.result()
            except Exception as exc:
                self._handle_scan_error(exc, serial, method, nfc_payload, totp_code, selfie_b64, "checkin")
                QTimer.singleShot(SUCCESS_DISPLAY_MS, self._return_to_idle)
                return

            if result_type == "checkin":
                name = payload.get("member_name", "Member")
                self._show_success(name, "Checked In")
                self._event_log.add_event(f"\u2714  {name} checked in", success=True)
            elif result_type == "checkout":
                name = payload.get("member_name", "Member")
                dur = payload.get("duration_minutes", 0)
                self._show_success(name, f"Checked Out  \u2022  {dur} min")
                self._event_log.add_event(f"\u2714  {name} out ({dur}m)", success=True)
            elif result_type == "error":
                err = payload
                self._handle_scan_error(err, serial, method, nfc_payload, totp_code, selfie_b64, "checkin")

            QTimer.singleShot(SUCCESS_DISPLAY_MS, self._return_to_idle)

        QTimer.singleShot(50, _check_future)

    # Worker that runs in a background thread (NO Qt widget access here)
    def _scan_worker(self, serial, method, nfc_payload, totp_code, selfie_b64):
        """Blocking API calls — runs in ThreadPoolExecutor, returns (type, payload)."""
        try:
            result = self.api.checkin(serial, nfc_payload, totp_code, method, selfie_b64)
            return ("checkin", result)
        except ApiError as checkin_err:
            if checkin_err.status_code == 409:
                try:
                    result = self.api.checkout(serial, nfc_payload, totp_code, method, selfie_b64)
                    return ("checkout", result)
                except Exception as checkout_err:
                    return ("error", checkout_err)
            return ("error", checkin_err)
        except Exception as exc:
            return ("error", exc)

    def _handle_scan_error(self, err, serial, method, nfc_payload, totp_code, selfie_b64, action) -> None:
        err_text = str(err)
        if self._online:
            self._show_error(f"Scan failed: {err_text[:80]}")
            self._event_log.add_event(f"\u2718  Error: {err_text[:50]}", success=False)
        else:
            self.offline.queue_event({
                "serial": serial, "nfc_payload": nfc_payload,
                "totp_code": totp_code, "method": method,
                "selfie_base64": selfie_b64, "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._show_error("Offline  \u2022  Scan queued")
            self._event_log.add_event("\u23F3  Queued offline scan", success=False)
            self._update_queue_pill()

    # ================================================================= Display states

    def _show_success(self, name: str, detail: str) -> None:
        self._success_name.setText(name)
        self._success_detail.setText(detail)
        self._stack.setCurrentIndex(1)

    def _show_error(self, message: str) -> None:
        self._error_msg.setText(message)
        self._stack.setCurrentIndex(2)

    def _return_to_idle(self) -> None:
        self._idle_label.setText("Ready to Scan")
        self._idle_sub.setText("Tap your NFC pass or show a QR code")
        self._stack.setCurrentIndex(0)
        self._qr_thread.resume()

    # ================================================================= Webcam

    def _on_frame(self, qimg: QImage) -> None:
        self._webcam_frame.set_pixmap(QPixmap.fromImage(qimg))

    # ================================================================= Status

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
        except Exception as exc:
            self._event_log.add_event(f"\u26A0  Cache refresh failed: {exc}", success=False)

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
            self._event_log.add_event(f"\u2191  Synced {processed} offline events", success=True)
        except Exception as exc:
            self._event_log.add_event(f"\u26A0  Queue flush failed: {exc}", success=False)

    def _update_queue_pill(self) -> None:
        count = self.offline.queue_count
        if count > 0:
            self.pill_queue.set_error(f"Queue: {count}")
        else:
            self.pill_queue.set_active("Queue: 0")

    # ================================================================= Simulator (debug only)

    def _open_simulator(self) -> None:
        """Open the scan simulator dialog (debug mode)."""
        dlg = SimulatorDialog(self.api, self)
        dlg.scan_requested.connect(self._on_simulated_scan)
        dlg.exec()

    def _on_simulated_scan(self, serial: str, method: str) -> None:
        """Handle a simulated scan from the dialog."""
        self._event_log.add_event(f"\U0001F9EA  SIM: {method} scan for {serial[:8]}…", success=True)
        self._do_scan(
            serial=serial,
            method=method,
            nfc_payload=f"meridian://scan?serial={serial}&payload=SIM" if method == "nfc" else None,
            totp_code="000000" if method == "qr" else None,
            selfie_b64=None,
        )

    # ================================================================= Settings (PIN-locked)

    def _open_settings(self) -> None:
        """Authenticate as admin via backend login before opening settings."""
        login_dlg = AdminLoginDialog(self.api, self)
        if not login_dlg.exec() or not login_dlg.authenticated:
            if not login_dlg.authenticated and login_dlg.result():
                self._event_log.add_event("\u26D4  Settings: access denied", success=False)
            return

        self._event_log.add_event("\U0001F513  Admin authenticated — settings opened", success=True)
        dlg = SettingsDialog(self.config, self.api, self)
        if dlg.exec():
            self._nfc_thread.stop()
            self._qr_thread.stop()
            self._scan_pool.shutdown(wait=False)
            self.api.close()
            self.offline.close()
            self.api = ApiClient(self.config)
            self.offline = OfflineManager(self.config.offline_cache_path, self.config.api_key or "dev")
            self._scan_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            self._start_threads()

    # ================================================================= Cleanup

    def closeEvent(self, event) -> None:
        self._scan_pool.shutdown(wait=False)
        self._nfc_thread.stop()
        self._qr_thread.stop()
        self.api.close()
        self.offline.close()
        super().closeEvent(event)
