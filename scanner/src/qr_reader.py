"""QR code reader thread using OpenCV + pyzbar."""

from __future__ import annotations

import base64
import threading
import time

import cv2
import numpy as np
from pyzbar import pyzbar
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage


class QrReaderThread(QThread):
    """Captures webcam frames, decodes QR codes, optionally grabs a selfie.

    Performance notes:
    - Frames are captured at native resolution but QR decoding runs on a
      downscaled copy (640px wide) so pyzbar spends less time per frame.
    - Preview frames are only emitted every ~3 captures (~5 fps preview)
      instead of every frame, reducing cross-thread QImage copies.
    - The selfie JPEG is encoded at 60% quality (still plenty for audit).
    """

    frame_ready = pyqtSignal(QImage)
    qr_detected = pyqtSignal(str, str)  # (uri, selfie_base64)

    _DECODE_WIDTH = 640          # px — scale down before pyzbar
    _PREVIEW_EVERY = 3           # emit 1 preview frame every N captures
    _SELFIE_QUALITY = 60         # JPEG quality for selfie snapshots

    def __init__(self, webcam_index: int = 0, selfie_enabled: bool = True) -> None:
        super().__init__()
        self._running = True
        self._paused = False
        self._lock = threading.Lock()
        self._webcam_index = webcam_index
        self._selfie_enabled = selfie_enabled

    def run(self) -> None:
        cap = cv2.VideoCapture(self._webcam_index)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # Request a moderate capture resolution — most USB cameras default to
        # 640x480 anyway, but explicitly setting it avoids getting a slow
        # 1080p stream from cameras that negotiate high res by default.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        frame_counter = 0

        while self._running:
            with self._lock:
                paused = self._paused

            if paused:
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame_counter += 1

            # Downscale for faster QR decoding if needed
            h_orig, w_orig = frame.shape[:2]
            if w_orig > self._DECODE_WIDTH:
                scale = self._DECODE_WIDTH / w_orig
                small = cv2.resize(frame, (self._DECODE_WIDTH, int(h_orig * scale)),
                                   interpolation=cv2.INTER_NEAREST)
            else:
                small = frame

            decoded = pyzbar.decode(small)
            for obj in decoded:
                qr_data = obj.data.decode("utf-8", errors="ignore")
                if not qr_data.startswith("frcattend://"):
                    continue

                # Highlight QR on the full-res frame (scale points back up)
                points = obj.polygon
                if points:
                    if w_orig > self._DECODE_WIDTH:
                        inv = w_orig / self._DECODE_WIDTH
                        pts = np.array([(int(p.x * inv), int(p.y * inv)) for p in points], dtype=np.int32)
                    else:
                        pts = np.array([(p.x, p.y) for p in points], dtype=np.int32)
                    cv2.polylines(frame, [pts], True, (91, 141, 239), 2)

                selfie_b64 = ""
                if self._selfie_enabled:
                    _, buf = cv2.imencode(".jpg", frame,
                                         [cv2.IMWRITE_JPEG_QUALITY, self._SELFIE_QUALITY])
                    selfie_b64 = base64.b64encode(buf).decode()

                self.qr_detected.emit(qr_data, selfie_b64)
                with self._lock:
                    self._paused = True
                break

            # Emit preview at reduced rate to avoid saturating the GUI thread
            if frame_counter % self._PREVIEW_EVERY == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self.frame_ready.emit(qimg.copy())

        cap.release()

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def stop(self) -> None:
        self._running = False
        self.wait(5000)
