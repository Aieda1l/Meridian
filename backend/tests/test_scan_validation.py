from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock

import pyotp
import pytest

from app.services import scan_validation


class FakeRedis:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.last_setex: tuple[str, int, str] | None = None

    async def get(self, key: str):
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.last_setex = (key, ttl, value)


@pytest.mark.asyncio
async def test_validate_nfc_payload_accepts_valid_hmac(monkeypatch) -> None:
    serial = "member-pass-123"
    member_secret = "member-secret"
    server_secret = "server-secret"

    monkeypatch.setattr(scan_validation, "pgp_decrypt", AsyncMock(return_value=member_secret))
    monkeypatch.setattr(scan_validation.settings, "NFC_HMAC_SECRET", server_secret)

    signature = hmac.new(
        server_secret.encode(),
        f"{serial}:{member_secret}".encode(),
        hashlib.sha256,
    ).hexdigest()
    payload = f"frcattend://checkin?serial={serial}&payload={signature}"

    assert await scan_validation.validate_nfc_payload(
        pass_serial=serial,
        nfc_payload=payload,
        member_totp_secret_encrypted=b"ciphertext",
        db=object(),
    )


@pytest.mark.asyncio
async def test_validate_nfc_payload_rejects_malformed_signature(monkeypatch) -> None:
    monkeypatch.setattr(scan_validation, "pgp_decrypt", AsyncMock(return_value="member-secret"))
    monkeypatch.setattr(scan_validation.settings, "NFC_HMAC_SECRET", "server-secret")

    assert not await scan_validation.validate_nfc_payload(
        pass_serial="member-pass-123",
        nfc_payload="frcattend://checkin?serial=member-pass-123&payload=too-short",
        member_totp_secret_encrypted=b"ciphertext",
        db=object(),
    )


@pytest.mark.asyncio
async def test_validate_totp_code_accepts_fresh_code_and_marks_replay(monkeypatch) -> None:
    serial = "member-pass-123"
    member_secret = pyotp.random_base32()
    code = pyotp.TOTP(member_secret).now()
    redis = FakeRedis()

    monkeypatch.setattr(scan_validation, "pgp_decrypt", AsyncMock(return_value=member_secret))

    assert await scan_validation.validate_totp_code(
        code=code,
        member_totp_secret_encrypted=b"ciphertext",
        db=object(),
        redis_client=redis,
        pass_serial=serial,
    )
    assert redis.last_setex == (f"totp_used:{serial}:{code}", 90, "1")


@pytest.mark.asyncio
async def test_validate_totp_code_rejects_replayed_code(monkeypatch) -> None:
    serial = "member-pass-123"
    member_secret = pyotp.random_base32()
    code = pyotp.TOTP(member_secret).now()
    redis = FakeRedis({f"totp_used:{serial}:{code}": "1"})

    monkeypatch.setattr(scan_validation, "pgp_decrypt", AsyncMock(return_value=member_secret))

    assert not await scan_validation.validate_totp_code(
        code=code,
        member_totp_secret_encrypted=b"ciphertext",
        db=object(),
        redis_client=redis,
        pass_serial=serial,
    )
