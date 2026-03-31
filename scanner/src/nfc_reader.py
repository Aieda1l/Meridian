"""NFC reader thread using pyscard (PC/SC) for ACR1252U and compatible readers."""

from __future__ import annotations

import time

from PyQt6.QtCore import QThread, pyqtSignal


class NfcReaderThread(QThread):
    """Continuously polls for NFC cards and emits the NDEF URI payload."""

    card_detected = pyqtSignal(str)  # frcattend://... URI
    reader_status = pyqtSignal(bool)  # True = connected

    def __init__(self) -> None:
        super().__init__()
        self._running = True

    def run(self) -> None:  # noqa: C901
        try:
            from smartcard.System import readers  # type: ignore[import-untyped]
            from smartcard.Exceptions import NoCardException, CardConnectionException  # type: ignore[import-untyped]
        except ImportError:
            self.reader_status.emit(False)
            return

        while self._running:
            try:
                reader_list = readers()
                if not reader_list:
                    self.reader_status.emit(False)
                    time.sleep(2)
                    continue

                reader = reader_list[0]
                self.reader_status.emit(True)

                try:
                    connection = reader.createConnection()
                    connection.connect()

                    # Select NDEF application
                    SELECT_NDEF = [0x00, 0xA4, 0x04, 0x00, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
                    data, sw1, sw2 = connection.transmit(SELECT_NDEF)

                    if sw1 == 0x90 and sw2 == 0x00:
                        # Select NDEF file
                        SELECT_FILE = [0x00, 0xA4, 0x00, 0x0C, 0x02, 0x00, 0x01]
                        connection.transmit(SELECT_FILE)

                        # Read binary
                        READ_BINARY = [0x00, 0xB0, 0x00, 0x00, 0x00]
                        data, sw1, sw2 = connection.transmit(READ_BINARY)

                        if data:
                            payload = bytes(data).decode("utf-8", errors="ignore")
                            if "frcattend://" in payload:
                                start = payload.index("frcattend://")
                                end = payload.find("\x00", start)
                                uri = payload[start:end] if end > 0 else payload[start:]
                                self.card_detected.emit(uri.strip())

                    connection.disconnect()
                except (NoCardException, CardConnectionException):
                    pass

                time.sleep(0.5)
            except Exception:
                self.reader_status.emit(False)
                time.sleep(2)

    def stop(self) -> None:
        self._running = False
        self.wait(5000)
