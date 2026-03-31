"""Auth router — login, refresh, logout, register.

- POST /auth/login      — email + password → access + refresh tokens
- POST /auth/refresh    — refresh cookie   → new access token
- POST /auth/logout     — clears refresh cookie
- POST /auth/register   — admin only; creates member, generates TOTP secret, issues pass serial
"""

from __future__ import annotations

import uuid

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import pgp_decrypt, pgp_encrypt
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_member,
    get_refresh_token_payload,
    hash_password,
    require_admin,
    verify_password,
)
from app.models.member import DevicePlatform, Member, MemberRole
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.audit import log_event

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password. Returns access token in body,
    refresh token as an httpOnly cookie."""

    from app.core.security import hash_email
    hashed_email = hash_email(body.email)

    result = await db.execute(
        select(Member).where(Member.email_hash == hashed_email, Member.is_active == True)  # noqa: E712
    )
    member = result.scalar_one_or_none()

    authenticated_member: Member | None = None
    if member is not None and verify_password(body.password, member.password_hashed):
        authenticated_member = member

    if authenticated_member is None:
        # Log failed attempt
        await log_event(
            db,
            event_type="auth_login_failed",
            detail={"email_hash": hashed_email},
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        subject=str(authenticated_member.id),
        role=authenticated_member.role.value,
    )
    refresh_token = create_refresh_token(subject=str(authenticated_member.id))

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    payload: dict = Depends(get_refresh_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Exchange a valid refresh token for a new access token."""
    member_id = payload.get("sub")
    result = await db.execute(
        select(Member).where(Member.id == member_id, Member.is_active == True)  # noqa: E712
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Member not found or inactive")

    access_token = create_access_token(
        subject=str(member.id),
        role=member.role.value,
    )

    # Rotate refresh token
    new_refresh = create_refresh_token(subject=str(member.id))
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )

    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear the refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/auth")


# ---------------------------------------------------------------------------
# POST /auth/register  (admin only)
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Create a new member. Admin only.

    Generates a TOTP secret and a unique pass serial number.
    """
    # Check for duplicate member_number
    existing = await db.execute(
        select(Member).where(Member.member_number == body.member_number)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Member number {body.member_number} already exists",
        )

    # Encrypt PII
    from app.core.security import hash_email
    name_enc = await pgp_encrypt(db, body.name)
    email_enc = await pgp_encrypt(db, body.email)
    email_hash_val = hash_email(body.email)
    phone_enc = await pgp_encrypt(db, body.phone) if body.phone else None

    # Generate TOTP secret and encrypt it
    totp_secret = pyotp.random_base32()
    totp_enc = await pgp_encrypt(db, totp_secret)

    # Generate pass serial
    pass_serial = uuid.uuid4()

    # Parse role
    role = MemberRole(body.role)

    # Parse season_id
    season_id = uuid.UUID(body.season_id) if body.season_id else None

    member = Member(
        member_number=body.member_number,
        name_encrypted=name_enc,
        email_encrypted=email_enc,
        email_hash=email_hash_val,
        phone_encrypted=phone_enc,
        role=role,
        password_hashed=hash_password(body.password),
        totp_secret_encrypted=totp_enc,
        pass_serial=pass_serial,
        device_platform=DevicePlatform.none,
        season_id=season_id,
    )
    db.add(member)
    await db.flush()

    # Audit log
    await log_event(
        db,
        event_type="member_created",
        actor_id=admin.id,
        target_id=member.id,
        detail={"member_number": body.member_number, "role": body.role},
        ip_address=request.client.host if request.client else None,
    )

    return RegisterResponse(
        id=str(member.id),
        member_number=member.member_number,
        role=member.role.value,
        pass_serial=str(pass_serial),
    )
