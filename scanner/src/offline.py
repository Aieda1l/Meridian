"""Offline mode — AES-GCM encrypted member cache and SQLite event queue."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 10_000


class OfflineManager:
    """Manages encrypted member cache and an offline event queue."""

    def __init__(self, cache_path: str, api_key: str):
        self.cache_path = os.path.abspath(cache_path)
        self._salt_path = os.path.splitext(self.cache_path)[0] + ".salt"
        self._salt = self._load_or_create_salt()
        self._key = self._derive_key(api_key, self._salt)
        self._db_path = os.path.splitext(self.cache_path)[0] + "_queue.db"
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._init_queue_db()

    # -- key derivation --------------------------------------------------

    def _load_or_create_salt(self) -> bytes:
        """Load an existing random salt or generate a new one."""
        if os.path.exists(self._salt_path):
            with open(self._salt_path, "rb") as f:
                salt = f.read()
            if len(salt) == 16:
                return salt
        salt = os.urandom(16)
        with open(self._salt_path, "wb") as f:
            f.write(salt)
        return salt

    @staticmethod
    def _derive_key(api_key: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
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
        try:
            with open(self.cache_path, "rb") as f:
                raw = f.read()
            nonce, ct = raw[:12], raw[12:]
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, ct, None)
            return json.loads(plaintext)
        except Exception:
            logger.warning("Failed to decrypt offline cache — file may be corrupted or key changed")
            return None

    # -- sqlite queue -----------------------------------------------------

    def _init_queue_db(self) -> None:
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS offline_queue (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                payload   TEXT    NOT NULL,
                timestamp TEXT    NOT NULL,
                synced    INTEGER DEFAULT 0
            )"""
        )
        self._conn.commit()

    def queue_event(self, payload: dict) -> None:
        if self.queue_count >= MAX_QUEUE_SIZE:
            logger.warning("Offline queue full (%d events) — dropping oldest unsynced event", MAX_QUEUE_SIZE)
            self._conn.execute(
                "DELETE FROM offline_queue WHERE id = ("
                "  SELECT id FROM offline_queue WHERE synced=0 ORDER BY id LIMIT 1"
                ")"
            )
        self._conn.execute(
            "INSERT INTO offline_queue (payload, timestamp) VALUES (?, ?)",
            (json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def get_pending_events(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, payload, timestamp FROM offline_queue WHERE synced=0 ORDER BY id"
        ).fetchall()
        return [{"id": r[0], "payload": json.loads(r[1]), "timestamp": r[2]} for r in rows]

    def mark_synced(self, event_ids: list[int]) -> None:
        if not event_ids:
            return
        placeholders = ",".join("?" * len(event_ids))
        self._conn.execute(f"UPDATE offline_queue SET synced=1 WHERE id IN ({placeholders})", event_ids)
        self._conn.commit()

    @property
    def queue_count(self) -> int:
        count = self._conn.execute("SELECT COUNT(*) FROM offline_queue WHERE synced=0").fetchone()[0]
        return count

    def close(self) -> None:
        """Close the persistent SQLite connection."""
        self._conn.close()
