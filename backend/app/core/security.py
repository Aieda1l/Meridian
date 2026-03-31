"""Authentication & authorization utilities.

- JWT creation/verification (HS256, 15-min access + 7-day refresh)
- Password hashing (bcrypt via passlib)
- FastAPI dependencies for member JWT auth and scanner API-key auth
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.member import Member, MemberRole
from app.models.scanner import Scanner

# ---------------------------------------------------------------------------
# Email Hashing (Deterministic for O(1) lookups)
# ---------------------------------------------------------------------------

def hash_email(email: str) -> str:
    """Deterministically hash an email for O(1) DB lookups using the JWT_SECRET as a pepper."""
    # Convert email to lowercase and strip whitespace for consistent hashing
    normalized = email.strip().lower()
    return hmac.new(
        settings.JWT_SECRET.encode(),
        normalized.encode(),
        hashlib.sha256,
    ).hexdigest()

# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(subject: str, role: str, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies — member JWT auth
# ---------------------------------------------------------------------------

async def _extract_bearer(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth[7:]


async def get_current_member(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Member:
    """Dependency: returns the authenticated Member from the JWT bearer token."""
    token = await _extract_bearer(request)
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    member_id = payload.get("sub")
    if not member_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(Member).where(Member.id == member_id, Member.is_active == True))  # noqa: E712
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found or inactive")
    return member


async def require_admin(
    member: Annotated[Member, Depends(get_current_member)],
) -> Member:
    """Dependency: requires the authenticated member to have admin role."""
    if member.role != MemberRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return member


async def require_admin_or_mentor(
    member: Annotated[Member, Depends(get_current_member)],
) -> Member:
    """Dependency: requires admin or mentor role."""
    if member.role not in (MemberRole.admin, MemberRole.mentor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or mentor access required")
    return member


# ---------------------------------------------------------------------------
# FastAPI dependency — scanner API-key auth
# ---------------------------------------------------------------------------

_SCANNER_AUTH_CACHE_PREFIX = "scanner_auth:"
_SCANNER_AUTH_CACHE_TTL = 3600  # 1 hour

async def get_current_scanner(
    x_scanner_key: Annotated[str, Header()],
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
) -> Scanner:
    """Dependency: authenticates a scanner via its API key in X-Scanner-Key header.

    Uses a Redis cache keyed by the SHA-256 hash of the API key (never the raw
    key) to bypass O(n) bcrypt on subsequent requests.  Cache entries expire
    after 1 hour.
    """
    key_hash = hashlib.sha256(x_scanner_key.encode()).hexdigest()
    cache_key = f"{_SCANNER_AUTH_CACHE_PREFIX}{key_hash}"

    # Check Redis cache first
    cached_id = await redis_client.get(cache_key)
    if cached_id:
        cached_id_str = cached_id if isinstance(cached_id, str) else cached_id.decode()
        result = await db.execute(select(Scanner).where(Scanner.id == cached_id_str))
        scanner = result.scalar_one_or_none()
        if scanner:
            return scanner
        # Stale cache entry — scanner was deleted; fall through to re-check
        await redis_client.delete(cache_key)

    # Cache miss: iterate all scanners and bcrypt-compare
    result = await db.execute(select(Scanner))
    scanners = result.scalars().all()

    for scanner in scanners:
        if bcrypt.checkpw(x_scanner_key.encode(), scanner.api_key_hashed.encode()):
            await redis_client.setex(cache_key, _SCANNER_AUTH_CACHE_TTL, str(scanner.id))
            return scanner

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid scanner API key",
    )


# ---------------------------------------------------------------------------
# Refresh token extraction (from httpOnly cookie)
# ---------------------------------------------------------------------------

async def get_refresh_token_payload(
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    """Dependency: extracts and validates the refresh token from an httpOnly cookie."""
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload
