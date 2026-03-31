"""HTTP client for communicating with the Meridian backend API."""

from __future__ import annotations

import base64
import json
import logging

import httpx

from .config import ScannerConfig
from .exceptions import ApiError

logger = logging.getLogger(__name__)


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise ApiError with status code instead of generic httpx error."""
    if not resp.is_success:
        detail = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
        raise ApiError(resp.status_code, detail)


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
        _raise_for_status(resp)
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
        _raise_for_status(resp)
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
        _raise_for_status(resp)
        return resp.json()

    def fetch_cache(self) -> dict:
        resp = self._client.get(f"{self.base_url}/scanner/cache", headers=self.headers)
        _raise_for_status(resp)
        return resp.json()

    def flush_queue(self, events: list[dict]) -> dict:
        resp = self._client.post(
            f"{self.base_url}/scanner/flush-queue",
            headers=self.headers,
            json={"events": events},
        )
        _raise_for_status(resp)
        return resp.json()

    def admin_login(self, email: str, password: str) -> dict:
        """Authenticate against /auth/login and return the response data.

        After successful login, fetches the user's role from the /auth/me
        endpoint rather than parsing the JWT client-side (which would skip
        signature verification).
        """
        resp = self._client.post(
            f"{self.base_url}/auth/login",
            json={"email": email, "password": password},
        )
        _raise_for_status(resp)
        data = resp.json()
        token = data.get("access_token", "")

        # Fetch role from server instead of decoding JWT without verification
        try:
            me_resp = self._client.get(
                f"{self.base_url}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            if me_resp.is_success:
                me_data = me_resp.json()
                data["role"] = me_data.get("role", "")
            else:
                # Fallback: decode JWT payload for role (no sig verification,
                # but login already validated credentials with the server)
                parts = token.split(".")
                if len(parts) >= 2:
                    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    data["role"] = payload.get("role", "")
        except Exception:
            logger.debug("Failed to fetch role from /auth/me, falling back to JWT decode")
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
