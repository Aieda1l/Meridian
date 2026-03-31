"""NFC payload and TOTP code validation for scanner check-ins."""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlparse, parse_qs

import pyotp
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import pgp_decrypt


async def validate_nfc_payload(
    pass_serial: str,
    nfc_payload: str,
    member_totp_secret_encrypted: bytes,
    db: AsyncSession,
) -> bool:
    """Validate NFC payload HMAC signature.

    The NFC payload format is:
    frcattend://checkin?serial={serial}&payload={hmac_hex}

    We recompute the HMAC using the global NFC_HMAC_SECRET and the member's
    TOTP secret (used as the per-member component) and compare.
    """
    # Parse payload using proper URL parsing
    try:
        parsed = urlparse(nfc_payload)
        params = parse_qs(parsed.query)
        hmac_values = params.get("payload")
        if not hmac_values or len(hmac_values) != 1:
            return False
        received_hmac = hmac_values[0]
        # HMAC-SHA256 produces a 64-character hex digest
        if len(received_hmac) != 64:
            return False
    except Exception:
        return False

    # Decrypt member's TOTP secret to use as per-member component
    member_secret = await pgp_decrypt(db, member_totp_secret_encrypted)

    expected = hmac.new(
        settings.NFC_HMAC_SECRET.encode(),
        f"{pass_serial}:{member_secret}".encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(received_hmac, expected)


async def validate_totp_code(
    code: str,
    member_totp_secret_encrypted: bytes,
    db: AsyncSession,
    redis_client: Redis,
    pass_serial: str,
) -> bool:
    """Validate a TOTP code and prevent replay.

    - Decrypts the member's TOTP secret
    - Validates the code with +-1 window for clock drift
    - Checks Redis for replay (30-second TTL cache)
    - Marks the code as used in Redis if valid
    """
    member_secret = await pgp_decrypt(db, member_totp_secret_encrypted)

    totp = pyotp.TOTP(member_secret)
    if not totp.verify(code, valid_window=1):
        return False

    # Check replay prevention
    replay_key = f"totp_used:{pass_serial}:{code}"
    already_used = await redis_client.get(replay_key)
    if already_used:
        return False

    # Mark as used with 90-second TTL
    await redis_client.setex(replay_key, 90, "1")
    return True
