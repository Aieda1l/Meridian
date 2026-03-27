"""HTTP client for communicating with the Meridian backend API."""

from __future__ import annotations

import httpx

from .config import ScannerConfig


class ApiClient:
    def __init__(self, config: ScannerConfig):
        self.config = config
        self.base_url = config.api_base_url.rstrip("/")
        self.headers = {"X-Scanner-Key": config.api_key}
        self._client = httpx.Client(timeout=10.0)

    # ---------------------------------------------------------------
    # Scanner endpoints
    # ---------------------------------------------------------------

    def checkin(
        self,
        serial: str,
        nfc_payload: str | None,
        totp_code: str | None,
        method: str,
        selfie_b64: str | None = None,
    ) -> dict:
        resp = self._client.post(
            f"{self.base_url}/scanner/checkin",
            headers=self.headers,
            json={
                "serial": serial,
                "nfc_payload": nfc_payload,
                "totp_code": totp_code,
                "method": method,
                "selfie_base64": selfie_b64,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def checkout(
        self,
        serial: str,
        nfc_payload: str | None,
        totp_code: str | None,
        method: str,
        selfie_b64: str | None = None,
    ) -> dict:
        resp = self._client.post(
            f"{self.base_url}/scanner/checkout",
            headers=self.headers,
            json={
                "serial": serial,
                "nfc_payload": nfc_payload,
                "totp_code": totp_code,
                "method": method,
                "selfie_base64": selfie_b64,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, scanner_id: str, cache_version: int, queue_count: int = 0) -> dict:
        resp = self._client.post(
            f"{self.base_url}/scanner/heartbeat",
            headers=self.headers,
            json={
                "scanner_id": scanner_id,
                "cache_version": cache_version,
                "offline_queue_count": queue_count,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_cache(self) -> dict:
        resp = self._client.get(f"{self.base_url}/scanner/cache", headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def flush_queue(self, events: list[dict]) -> dict:
        resp = self._client.post(
            f"{self.base_url}/scanner/flush-queue",
            headers=self.headers,
            json={"events": events},
        )
        resp.raise_for_status()
        return resp.json()

    def admin_login(self, email: str, password: str) -> dict:
        """Authenticate against /auth/login and return the decoded JWT payload.

        Returns dict with 'access_token' and parsed 'role' on success.
        Raises on failure.
        """
        import json
        import base64

        resp = self._client.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token", "")

        # Decode JWT payload (we only need the role claim — no signature
        # verification needed since the server already validated creds).
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            data["role"] = payload.get("role", "")
        return data

    def test_connection(self) -> bool:
        try:
            resp = self._client.post(
                f"{self.base_url}/scanner/heartbeat",
                headers=self.headers,
                json={"scanner_id": self.config.scanner_id, "cache_version": 0, "offline_queue_count": 0},
            )
            return resp.status_code == 200
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()
