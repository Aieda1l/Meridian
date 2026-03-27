"""Offline mode — AES-GCM encrypted member cache and SQLite event queue."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


class OfflineManager:
    """Manages encrypted member cache and an offline event queue."""

    def __init__(self, cache_path: str, api_key: str):
        self.cache_path = os.path.abspath(cache_path)
        self._key = self._derive_key(api_key)
        self._db_path = os.path.splitext(self.cache_path)[0] + "_queue.db"
        self._init_queue_db()

    # -- key derivation --------------------------------------------------

    @staticmethod
    def _derive_key(api_key: str) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"meridian-scanner-v1",
            iterations=100_000,
        )
        return kdf.derive(api_key.encode())

    # -- encrypted cache --------------------------------------------------

    def save_cache(self, data: dict) -> None:
        plaintext = json.dumps(data).encode()
        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext, None)
        with open(self.cache_path, "wb") as f:
            f.write(nonce + ct)

    def load_cache(self) -> dict | None:
        if not os.path.exists(self.cache_path):
            return None
        with open(self.cache_path, "rb") as f:
            raw = f.read()
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(self._key)
        plaintext = aesgcm.decrypt(nonce, ct, None)
        return json.loads(plaintext)

    # -- sqlite queue -----------------------------------------------------

    def _init_queue_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS offline_queue (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                payload   TEXT    NOT NULL,
                timestamp TEXT    NOT NULL,
                synced    INTEGER DEFAULT 0
            )"""
        )
        conn.commit()
        conn.close()

    def queue_event(self, payload: dict) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT INTO offline_queue (payload, timestamp) VALUES (?, ?)",
            (json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    def get_pending_events(self) -> list[dict]:
        conn = sqlite3.connect(self._db_path)
        rows = conn.execute(
            "SELECT id, payload, timestamp FROM offline_queue WHERE synced=0 ORDER BY id"
        ).fetchall()
        conn.close()
        return [{"id": r[0], "payload": json.loads(r[1]), "timestamp": r[2]} for r in rows]

    def mark_synced(self, event_ids: list[int]) -> None:
        if not event_ids:
            return
        conn = sqlite3.connect(self._db_path)
        placeholders = ",".join("?" * len(event_ids))
        conn.execute(f"UPDATE offline_queue SET synced=1 WHERE id IN ({placeholders})", event_ids)
        conn.commit()
        conn.close()

    @property
    def queue_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        count = conn.execute("SELECT COUNT(*) FROM offline_queue WHERE synced=0").fetchone()[0]
        conn.close()
        return count
