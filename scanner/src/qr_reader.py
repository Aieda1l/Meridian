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
    """Captures webcam frames, decodes QR codes, optionally grabs a selfie."""

    frame_ready = pyqtSignal(QImage)
    qr_detected = pyqtSignal(str, str)  # (uri, selfie_base64)

    def __init__(self, webcam_index: int = 0, selfie_enabled: bool = True) -> None:
        super().__init__()
        self._running = True
        self._paused = False
        self._lock = threading.Lock()
        self._webcam_index = webcam_index
        self._selfie_enabled = selfie_enabled

    def run(self) -> None:
        cap = cv2.VideoCapture(self._webcam_index)
        cap.set(cv2.CAP_PROP_FPS, 15)

        while self._running:
            with self._lock:
                paused = self._paused

            if paused:
                time.sleep(0.1)
                continue

            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            decoded = pyzbar.decode(frame)
            for obj in decoded:
                qr_data = obj.data.decode("utf-8", errors="ignore")
                if not qr_data.startswith("frcattend://"):
                    continue

                # Highlight QR on frame
                points = obj.polygon
                if points:
                    pts = np.array([(p.x, p.y) for p in points], dtype=np.int32)
                    cv2.polylines(frame, [pts], True, (91, 141, 239), 2)

                selfie_b64 = ""
                if self._selfie_enabled:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    selfie_b64 = base64.b64encode(buf).decode()

                self.qr_detected.emit(qr_data, selfie_b64)
                with self._lock:
                    self._paused = True
                break

            # Convert to QImage for the preview widget
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.frame_ready.emit(qimg.copy())

            time.sleep(1.0 / 15)

        cap.release()

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def stop(self) -> None:
        self._running = False
        self.wait(5000)
