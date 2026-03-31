"""Members router — CRUD, hours, sessions, pass transfer.

All endpoints require JWT auth. Most require admin role.

- GET    /members            — admin; paginated list with decrypted PII
- GET    /members/{id}       — admin or self
- PATCH  /members/{id}       — admin only; update member details
- DELETE /members/{id}       — admin only; soft delete (is_active=false), revokes pass
- POST   /members/{id}/transfer-pass — admin only; clears device binding
- GET    /members/{id}/hours — admin or self; returns hour totals for active season
- GET    /members/{id}/sessions — admin or self; paginated session history
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import String, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import pgp_decrypt, pgp_encrypt
from app.core.security import get_current_member, require_admin
from app.models.member import DevicePlatform, Member, MemberRole
from app.models.season import Season
from app.models.session import Session, SessionStatus
from app.schemas.member import (
    MemberHoursOut,
    MemberListOut,
    MemberOut,
    MemberUpdate,
    SessionListOut,
    SessionOut,
)
from app.services.audit import log_event
from app.services.hours import compute_member_hours
from app.services.season import get_active_season

router = APIRouter(prefix="/members", tags=["members"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _decrypt_member(db: AsyncSession, member: Member) -> MemberOut:
    """Decrypt PII fields and return a MemberOut schema."""
    name = await pgp_decrypt(db, member.name_encrypted) if member.name_encrypted else ""
    email = await pgp_decrypt(db, member.email_encrypted) if member.email_encrypted else ""
    phone = await pgp_decrypt(db, member.phone_encrypted) if member.phone_encrypted else None

    return MemberOut(
        id=str(member.id),
        member_number=member.member_number,
        name=name,
        email=email,
        phone=phone,
        role=member.role.value,
        is_active=member.is_active,
        device_platform=member.device_platform.value,
        pass_serial=str(member.pass_serial) if member.pass_serial else None,
        photo_url=member.photo_url,
        season_id=str(member.season_id) if member.season_id else None,
        created_at=member.created_at,
    )


def _require_admin_or_self(current: Member, target_id: uuid.UUID) -> None:
    """Raise 403 unless the current member is admin or is accessing their own record."""
    if current.role != MemberRole.admin and current.id != target_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own record",
        )


async def _get_member_or_404(db: AsyncSession, member_id: uuid.UUID) -> Member:
    """Fetch a member by UUID or raise 404."""
    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )
    return member





# ---------------------------------------------------------------------------
# GET /members — admin only, paginated list
# ---------------------------------------------------------------------------

@router.get("", response_model=MemberListOut)
async def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Return a paginated list of all members with decrypted PII."""
    # Total count
    count_result = await db.execute(select(func.count(Member.id)))
    total = count_result.scalar_one()

    # Paginated query
    offset = (page - 1) * page_size
    result = await db.execute(
        select(
            Member,
            func.pgp_sym_decrypt(Member.name_encrypted, settings.PGP_SYM_KEY).cast(String).label("name_dec"),
            func.pgp_sym_decrypt(Member.email_encrypted, settings.PGP_SYM_KEY).cast(String).label("email_dec"),
            func.pgp_sym_decrypt(Member.phone_encrypted, settings.PGP_SYM_KEY).cast(String).label("phone_dec"),
        )
        .order_by(Member.member_number)
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    items = []
    for m, name_dec, email_dec, phone_dec in rows:
        items.append(MemberOut(
            id=str(m.id),
            member_number=m.member_number,
            name=name_dec or "",
            email=email_dec or "",
            phone=phone_dec,
            role=m.role.value,
            is_active=m.is_active,
            device_platform=m.device_platform.value,
            pass_serial=str(m.pass_serial) if m.pass_serial else None,
            photo_url=m.photo_url,
            season_id=str(m.season_id) if m.season_id else None,
            created_at=m.created_at,
        ))

    return MemberListOut(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# GET /members/{id} — admin or self
# ---------------------------------------------------------------------------

@router.get("/{member_id}", response_model=MemberOut)
async def get_member(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return a single member with decrypted PII."""
    _require_admin_or_self(current, member_id)
    member = await _get_member_or_404(db, member_id)
    return await _decrypt_member(db, member)


# ---------------------------------------------------------------------------
# PATCH /members/{id} — admin only
# ---------------------------------------------------------------------------

@router.patch("/{member_id}", response_model=MemberOut)
async def update_member(
    member_id: uuid.UUID,
    body: MemberUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Update member details. Re-encrypts any changed PII fields."""
    member = await _get_member_or_404(db, member_id)

    changes: dict[str, str] = {}

    # PII fields — re-encrypt if provided
    if body.name is not None:
        member.name_encrypted = await pgp_encrypt(db, body.name)
        changes["name"] = "updated"

    if body.email is not None:
        from app.core.security import hash_email
        member.email_encrypted = await pgp_encrypt(db, body.email)
        member.email_hash = hash_email(body.email)
        changes["email"] = "updated"

    if body.phone is not None:
        member.phone_encrypted = await pgp_encrypt(db, body.phone)
        changes["phone"] = "updated"

    # Plain fields
    if body.role is not None:
        member.role = MemberRole(body.role)
        changes["role"] = body.role

    if body.is_active is not None:
        member.is_active = body.is_active
        changes["is_active"] = str(body.is_active)

    if body.photo_url is not None:
        member.photo_url = body.photo_url
        changes["photo_url"] = "updated"

    if body.season_id is not None:
        member.season_id = uuid.UUID(body.season_id)
        changes["season_id"] = body.season_id

    await db.flush()

    # Audit log
    await log_event(
        db,
        event_type="member_updated",
        actor_id=admin.id,
        target_id=member.id,
        detail={"fields_changed": changes},
        ip_address=request.client.host if request.client else None,
    )

    return await _decrypt_member(db, member)


# ---------------------------------------------------------------------------
# DELETE /members/{id} — admin only, soft delete
# ---------------------------------------------------------------------------

@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Soft-delete a member: deactivate and revoke pass credentials."""
    member = await _get_member_or_404(db, member_id)

    member.is_active = False
    member.device_push_token = None
    member.pass_auth_token_hashed = None

    await db.flush()

    await log_event(
        db,
        event_type="member_soft_deleted",
        actor_id=admin.id,
        target_id=member.id,
        detail={"member_number": member.member_number},
        ip_address=request.client.host if request.client else None,
    )


# ---------------------------------------------------------------------------
# POST /members/{id}/transfer-pass — admin only
# ---------------------------------------------------------------------------

@router.post("/{member_id}/transfer-pass", status_code=status.HTTP_204_NO_CONTENT)
async def transfer_pass(
    member_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Clear device binding so the member can re-provision their pass on a new device."""
    member = await _get_member_or_404(db, member_id)

    member.device_push_token = None
    member.device_platform = DevicePlatform.none

    await db.flush()

    await log_event(
        db,
        event_type="pass_transfer_authorized",
        actor_id=admin.id,
        target_id=member.id,
        detail={"member_number": member.member_number},
        ip_address=request.client.host if request.client else None,
    )


# ---------------------------------------------------------------------------
# GET /members/{id}/hours — admin or self
# ---------------------------------------------------------------------------

@router.get("/{member_id}/hours", response_model=MemberHoursOut)
async def get_member_hours(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return hour totals for the active season (today, this week, season)."""
    _require_admin_or_self(current, member_id)
    member = await _get_member_or_404(db, member_id)
    season = await get_active_season(db)

    now = datetime.now(timezone.utc)
    hours_today, hours_week, hours_season = await compute_member_hours(
        db, member_id, season, now
    )

    return MemberHoursOut(
        member_id=str(member_id),
        hours_today=round(hours_today, 2),
        hours_this_week=round(hours_week, 2),
        hours_this_season=round(hours_season, 2),
        daily_cap=float(season.daily_hour_cap),
        weekly_cap=float(season.weekly_hour_cap),
        season_cap=float(season.season_hour_cap),
    )


# ---------------------------------------------------------------------------
# GET /members/{id}/sessions — admin or self, paginated
# ---------------------------------------------------------------------------

@router.get("/{member_id}/sessions", response_model=SessionListOut)
async def list_member_sessions(
    member_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return paginated session history for a member."""
    _require_admin_or_self(current, member_id)
    await _get_member_or_404(db, member_id)

    # Base filters
    filters = [Session.member_id == member_id]
    if session_status is not None:
        filters.append(Session.status == SessionStatus(session_status))

    # Total count
    count_result = await db.execute(
        select(func.count(Session.id)).where(and_(*filters))
    )
    total = count_result.scalar_one()

    # Paginated query
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Session)
        .where(and_(*filters))
        .order_by(Session.check_in_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = [
        SessionOut(
            id=str(s.id),
            member_id=str(s.member_id),
            season_id=str(s.season_id),
            scanner_id=s.scanner_id,
            check_in_at=s.check_in_at,
            check_out_at=s.check_out_at,
            duration_minutes=s.duration_minutes,
            check_in_method=s.check_in_method.value,
            check_out_method=s.check_out_method.value if s.check_out_method else None,
            status=s.status.value,
            flag_reason=s.flag_reason,
            created_at=s.created_at,
        )
        for s in sessions
    ]

    return SessionListOut(items=items, total=total, page=page, page_size=page_size)
