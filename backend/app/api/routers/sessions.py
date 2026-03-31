"""Sessions router — list, detail, approve, self-report, auto-timeout.

- GET   /sessions              — admin only; filterable list
- GET   /sessions/{id}         — admin or session owner
- PATCH /sessions/{id}/approve — admin only; approve flagged session
- PATCH /sessions/{id}/self-report — member only; submit self-reported checkout
- POST  /sessions/auto-timeout — cron endpoint; close stale sessions
"""

from __future__ import annotations

import hmac
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import pgp_decrypt
from app.core.redis import get_redis
from app.core.security import get_current_member, require_admin
from app.models.member import Member, MemberRole
from app.models.session import CheckOutMethod, Session, SessionStatus
from app.schemas.session import (
    AutoTimeoutResponse,
    SessionApproveResponse,
    SessionDetailOut,
    SessionListOut,
    SelfReportRequest,
)
from app.services.audit import log_event
from app.services.checkout import _calculate_duration_minutes

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _session_to_detail(
    db: AsyncSession,
    session: Session,
    *,
    include_name: bool = False,
) -> SessionDetailOut:
    """Convert a Session ORM object to a SessionDetailOut schema.

    If *include_name* is True (admin view), decrypt the member's name.
    """
    member: Member = session.member
    member_name: str | None = None
    if include_name and member.name_encrypted:
        member_name = await pgp_decrypt(db, member.name_encrypted)

    return SessionDetailOut(
        id=str(session.id),
        member_id=str(session.member_id),
        member_name=member_name,
        member_number=member.member_number,
        season_id=str(session.season_id),
        scanner_id=session.scanner_id,
        check_in_at=session.check_in_at,
        check_out_at=session.check_out_at,
        duration_minutes=session.duration_minutes,
        check_in_method=session.check_in_method.value,
        check_out_method=session.check_out_method.value if session.check_out_method else None,
        selfie_url=session.selfie_url,
        status=session.status.value,
        flag_reason=session.flag_reason,
        self_report_checkout_at=session.self_report_checkout_at,
        geofence_exit_at=session.geofence_exit_at,
        created_at=session.created_at,
    )


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID) -> Session:
    """Fetch a session by UUID (eagerly loading member) or raise 404."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Session)
        .options(selectinload(Session.member))
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return session





# ---------------------------------------------------------------------------
# GET /sessions — admin only, filterable paginated list
# ---------------------------------------------------------------------------

@router.get("", response_model=SessionListOut)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    member_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    session_status: str | None = Query(None, alias="status"),
    season_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Return a paginated, filterable list of all sessions (admin only)."""
    from sqlalchemy.orm import selectinload

    filters: list = []

    if member_id is not None:
        filters.append(Session.member_id == member_id)

    if date_from is not None:
        dt_from = datetime.combine(date_from, datetime.min.time()).replace(tzinfo=timezone.utc)
        filters.append(Session.check_in_at >= dt_from)

    if date_to is not None:
        dt_to = datetime.combine(date_to, datetime.max.time()).replace(tzinfo=timezone.utc)
        filters.append(Session.check_in_at <= dt_to)

    if session_status is not None:
        filters.append(Session.status == SessionStatus(session_status))

    if season_id is not None:
        filters.append(Session.season_id == season_id)

    where_clause = and_(*filters) if filters else True  # type: ignore[arg-type]

    # Total count
    count_result = await db.execute(
        select(func.count(Session.id)).where(where_clause)
    )
    total = count_result.scalar_one()

    # Paginated query with member join
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.member))
        .where(where_clause)
        .order_by(Session.check_in_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = [await _session_to_detail(db, s, include_name=True) for s in sessions]

    return SessionListOut(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# GET /sessions/{id} — admin or session owner
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return a single session. Admin sees decrypted member name."""
    session = await _get_session_or_404(db, session_id)

    is_admin = current.role == MemberRole.admin
    is_owner = current.id == session.member_id

    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own sessions",
        )

    return await _session_to_detail(db, session, include_name=is_admin)


# ---------------------------------------------------------------------------
# PATCH /sessions/{id}/approve — admin only
# ---------------------------------------------------------------------------

@router.patch("/{session_id}/approve", response_model=SessionApproveResponse)
async def approve_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: Member = Depends(require_admin),
):
    """Approve a flagged session. If self-reported checkout exists, apply it."""
    session = await _get_session_or_404(db, session_id)

    if session.status != SessionStatus.flagged:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session status is '{session.status.value}', expected 'flagged'",
        )

    session.status = SessionStatus.approved

    # If this is a self-reported checkout, apply its requested checkout time and duration
    if session.flag_reason == "self_reported_checkout" and session.self_report_checkout_at is not None:
        session.check_out_at = session.self_report_checkout_at
        session.duration_minutes = _calculate_duration_minutes(
            session.check_in_at, session.self_report_checkout_at
        )

    await db.flush()

    await log_event(
        db,
        event_type="session_approved",
        actor_id=admin.id,
        target_id=session.id,
        detail={
            "member_id": str(session.member_id),
            "previous_flag_reason": session.flag_reason,
        },
        ip_address=request.client.host if request.client else None,
    )

    return SessionApproveResponse(
        id=str(session.id),
        status=session.status.value,
        message="Session approved",
    )


# ---------------------------------------------------------------------------
# PATCH /sessions/{id}/self-report — member only
# ---------------------------------------------------------------------------

@router.patch("/{session_id}/self-report", response_model=SessionApproveResponse)
async def self_report_checkout(
    session_id: uuid.UUID,
    body: SelfReportRequest,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Submit a self-reported checkout time for review."""
    session = await _get_session_or_404(db, session_id)

    # Must belong to the requesting member
    if session.member_id != current.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only self-report your own sessions",
        )

    # Must be open or flagged with auto_timeout reason
    valid_for_report = (
        session.status == SessionStatus.open
        or (session.status == SessionStatus.flagged and session.flag_reason == "auto_timeout")
    )
    if not valid_for_report:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Self-report is only allowed for open sessions or auto-timed-out sessions",
        )

    now = datetime.now(timezone.utc)

    # checkout_at must be after check_in_at
    if body.checkout_at <= session.check_in_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Checkout time must be after check-in time",
        )

    # checkout_at must be within the last 24 hours
    if body.checkout_at < now - timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Checkout time must be within the last 24 hours",
        )

    # checkout_at must not be in the future
    if body.checkout_at > now:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Checkout time must not be in the future",
        )

    session.self_report_checkout_at = body.checkout_at
    session.check_out_method = CheckOutMethod.self_report
    session.status = SessionStatus.flagged
    session.flag_reason = "self_reported_checkout"
    session.duration_minutes = _calculate_duration_minutes(
        session.check_in_at, body.checkout_at
    )

    await db.flush()

    return SessionApproveResponse(
        id=str(session.id),
        status=session.status.value,
        message="Self-reported checkout submitted for review",
    )


# ---------------------------------------------------------------------------
# POST /sessions/auto-timeout — cron endpoint (X-Cron-Secret auth)
# ---------------------------------------------------------------------------

@router.post("/auto-timeout", response_model=AutoTimeoutResponse)
async def auto_timeout_sessions(
    x_cron_secret: str = Header(..., alias="X-Cron-Secret"),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
):
    """Close stale open sessions and handle geofence grace period expiry.

    Authenticated via X-Cron-Secret header, not JWT.
    """
    if not hmac.compare_digest(x_cron_secret.encode(), settings.CRON_SECRET.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron secret",
        )

    from app.services.timeout import run_auto_timeout
    closed_ids = await run_auto_timeout(db, redis_client)

    return AutoTimeoutResponse(
        timed_out_count=len(closed_ids),
        session_ids=closed_ids,
    )
