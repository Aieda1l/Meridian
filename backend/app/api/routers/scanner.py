"""Scanner router — check-in, check-out, cache sync, heartbeat, offline flush.

All endpoints authenticate via the ``X-Scanner-Key`` header using the
``get_current_scanner`` dependency.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import pgp_decrypt
from app.core.rate_limit import limiter
from app.core.redis import get_redis
from app.core.security import get_current_scanner
from app.models.member import Member
from app.models.scanner import Scanner
from app.models.season import Season
from app.models.session import CheckInMethod, CheckOutMethod, Session, SessionStatus
from app.schemas.scanner import (
    CheckInResponse,
    CheckOutResponse,
    FlushQueueRequest,
    FlushQueueResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    OfflineEvent,
    ScanRequest,
)
from app.services.audit import log_event
from app.services.checkout import close_session
from app.services.hour_caps import evaluate_hour_caps
from app.services.hours import compute_member_hours
from app.services.scan_validation import validate_nfc_payload, validate_totp_code
from app.services.season import get_active_season

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_member_by_serial(db: AsyncSession, serial: str) -> Member:
    """Look up an active member by pass serial. Raises 404 if not found."""
    result = await db.execute(
        select(Member).where(
            Member.pass_serial == serial,
            Member.is_active == True,  # noqa: E712
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found for the given pass serial",
        )
    return member



async def _validate_scan(
    body: ScanRequest,
    member: Member,
    db: AsyncSession,
    redis_client: Redis,
) -> None:
    """Run NFC or QR validation. Raises 401 on failure.

    When ``settings.DEBUG_SKIP_SCAN_VALIDATION`` is True the cryptographic
    checks are bypassed — this allows the scanner simulator (and curl) to
    test the full check-in/check-out flow without real NFC hardware or a
    valid TOTP authenticator.
    """
    if settings.DEBUG_SKIP_SCAN_VALIDATION:
        return  # dev mode — accept any scan payload

    if member.totp_secret_encrypted is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member has no TOTP secret configured",
        )

    if body.method == "nfc":
        if body.nfc_payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="nfc_payload is required for NFC method",
            )
        valid = await validate_nfc_payload(
            pass_serial=body.serial,
            nfc_payload=body.nfc_payload,
            member_totp_secret_encrypted=member.totp_secret_encrypted,
            db=db,
        )
    elif body.method == "qr":
        if body.totp_code is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="totp_code is required for QR method",
            )
        valid = await validate_totp_code(
            code=body.totp_code,
            member_totp_secret_encrypted=member.totp_secret_encrypted,
            db=db,
            redis_client=redis_client,
            pass_serial=body.serial,
        )
    else:
        valid = False

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Scan validation failed",
        )


# ---------------------------------------------------------------------------
# POST /scanner/checkin
# ---------------------------------------------------------------------------

@router.post("/checkin", response_model=CheckInResponse)
@limiter.limit("60/minute")
async def scanner_checkin(
    body: ScanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
    scanner: Scanner = Depends(get_current_scanner),
):
    """Process a scanner check-in event."""
    member = await _get_member_by_serial(db, body.serial)
    await _validate_scan(body, member, db, redis_client)

    # Reject duplicate check-in (member already has an open session)
    open_result = await db.execute(
        select(Session).where(
            and_(
                Session.member_id == member.id,
                Session.status == SessionStatus.open,
            )
        )
    )
    if open_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already has an open session",
        )

    season = await get_active_season(db)
    now = datetime.now(timezone.utc)

    new_session = Session(
        member_id=member.id,
        season_id=season.id,
        scanner_id=scanner.id,
        check_in_at=now,
        check_in_method=CheckInMethod(body.method),
        status=SessionStatus.open,
    )

    # Store selfie reference if provided
    if body.selfie_base64:
        new_session.selfie_url = f"selfie://{member.id}/{now.isoformat()}"

    db.add(new_session)

    # Update scanner last_seen_at
    scanner.last_seen_at = now

    await db.flush()

    # Decrypt member name for the response
    member_name = (
        await pgp_decrypt(db, member.name_encrypted)
        if member.name_encrypted
        else ""
    )

    await log_event(
        db,
        event_type="scanner_checkin",
        target_id=member.id,
        detail={
            "scanner_id": scanner.id,
            "method": body.method,
            "session_id": str(new_session.id),
        },
        ip_address=request.client.host if request.client else None,
    )

    return CheckInResponse(
        success=True,
        member_name=member_name,
        check_in_at=now,
        session_id=str(new_session.id),
    )


# ---------------------------------------------------------------------------
# POST /scanner/checkout
# ---------------------------------------------------------------------------

@router.post("/checkout", response_model=CheckOutResponse)
@limiter.limit("60/minute")
async def scanner_checkout(
    body: ScanRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
    scanner: Scanner = Depends(get_current_scanner),
):
    """Process a scanner check-out event."""
    member = await _get_member_by_serial(db, body.serial)
    await _validate_scan(body, member, db, redis_client)

    # Find the open session for this member
    open_result = await db.execute(
        select(Session).where(
            and_(
                Session.member_id == member.id,
                Session.status == SessionStatus.open,
            )
        )
    )
    open_session = open_result.scalar_one_or_none()
    if open_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No open session found for this member",
        )

    now = datetime.now(timezone.utc)

    from app.services.checkout import close_session
    close_session(open_session, CheckOutMethod(body.method), now)

    # Store selfie reference if provided
    if body.selfie_base64:
        open_session.selfie_url = f"selfie://{member.id}/{now.isoformat()}"

    # Update scanner last_seen_at
    scanner.last_seen_at = now

    await db.flush()

    # Decrypt member name
    member_name = (
        await pgp_decrypt(db, member.name_encrypted)
        if member.name_encrypted
        else ""
    )

    # Compute hour totals
    season = await get_active_season(db)
    hours_today, hours_week, hours_season = await compute_member_hours(
        db, member.id, season, now
    )

    # Evaluate hour caps and create warnings if thresholds reached
    # TODO(Phase 11): send push notifications based on hour_warnings
    hour_warnings = await evaluate_hour_caps(db, member.id, season)

    await log_event(
        db,
        event_type="scanner_checkout",
        target_id=member.id,
        detail={
            "scanner_id": scanner.id,
            "method": body.method,
            "session_id": str(open_session.id),
            "duration_minutes": open_session.duration_minutes,
        },
        ip_address=request.client.host if request.client else None,
    )

    return CheckOutResponse(
        success=True,
        member_name=member_name,
        duration_minutes=open_session.duration_minutes,
        total_hours_today=hours_today,
        total_hours_week=hours_week,
        total_hours_season=hours_season,
    )


# ---------------------------------------------------------------------------
# GET /scanner/cache
# ---------------------------------------------------------------------------

@router.get("/cache", response_model=None)
async def scanner_cache(
    db: AsyncSession = Depends(get_db),
    scanner: Scanner = Depends(get_current_scanner),
):
    """Return a signed JSON snapshot of all active members for offline cache."""
    result = await db.execute(
        select(Member).where(Member.is_active == True)  # noqa: E712
    )
    members = result.scalars().all()

    members_data = []
    for m in members:
        entry = {
            "id": str(m.id),
            "pass_serial": str(m.pass_serial) if m.pass_serial else None,
            "member_number": m.member_number,
        }
        members_data.append(entry)

    payload = {
        "cache_version": scanner.offline_cache_version,
        "members": members_data,
    }

    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    signature = hmac.new(
        settings.NFC_HMAC_SECRET.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return JSONResponse(
        content=payload,
        headers={"X-Cache-Signature": signature},
    )


# ---------------------------------------------------------------------------
# POST /scanner/heartbeat
# ---------------------------------------------------------------------------

@router.post("/heartbeat", response_model=HeartbeatResponse)
async def scanner_heartbeat(
    body: HeartbeatRequest,
    db: AsyncSession = Depends(get_db),
    scanner: Scanner = Depends(get_current_scanner),
):
    """Accept a scanner heartbeat and report whether the cache is stale."""
    now = datetime.now(timezone.utc)
    scanner.last_seen_at = now
    await db.flush()

    cache_stale = body.cache_version != scanner.offline_cache_version

    return HeartbeatResponse(cache_stale=cache_stale)


# ---------------------------------------------------------------------------
# POST /scanner/flush-queue
# ---------------------------------------------------------------------------

@router.post("/flush-queue", response_model=FlushQueueResponse)
async def scanner_flush_queue(
    body: FlushQueueRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    scanner: Scanner = Depends(get_current_scanner),
):
    """Process a batch of offline-queued scan events.

    Events are processed in order. Conflicting events (e.g. a check-in when
    an online session already exists for that time window) are skipped.
    """
    processed = 0
    skipped = 0
    errors: list[str] = []

    for idx, event in enumerate(body.events):
        try:
            # Look up member by serial
            result = await db.execute(
                select(Member).where(
                    Member.pass_serial == event.serial,
                    Member.is_active == True,  # noqa: E712
                )
            )
            member = result.scalar_one_or_none()
            if member is None:
                errors.append(f"Event {idx}: member not found for serial {event.serial}")
                skipped += 1
                continue

            season = await get_active_season(db)

            if event.action == "checkin":
                # Check for conflicting open session at that time
                conflict_result = await db.execute(
                    select(Session).where(
                        and_(
                            Session.member_id == member.id,
                            Session.check_in_at <= event.timestamp,
                            (
                                (Session.check_out_at >= event.timestamp)
                                | (Session.status == SessionStatus.open)
                            ),
                        )
                    )
                )
                if conflict_result.scalars().first() is not None:
                    skipped += 1
                    continue

                new_session = Session(
                    member_id=member.id,
                    season_id=season.id,
                    scanner_id=scanner.id,
                    check_in_at=event.timestamp,
                    check_in_method=CheckInMethod(event.method),
                    status=SessionStatus.open,
                )
                if event.selfie_base64:
                    new_session.selfie_url = (
                        f"selfie://{member.id}/{event.timestamp.isoformat()}"
                    )
                db.add(new_session)
                processed += 1

            elif event.action == "checkout":
                # Find the most recent open session for this member
                open_result = await db.execute(
                    select(Session)
                    .where(
                        and_(
                            Session.member_id == member.id,
                            Session.status == SessionStatus.open,
                        )
                    )
                    .order_by(Session.check_in_at.desc())
                )
                open_session = open_result.scalars().first()
                if open_session is None:
                    skipped += 1
                    continue

                close_session(open_session, CheckOutMethod(event.method), event.timestamp)

                if event.selfie_base64:
                    open_session.selfie_url = (
                        f"selfie://{member.id}/{event.timestamp.isoformat()}"
                    )
                processed += 1

        except Exception:
            errors.append(f"Event {idx}: processing error")
            skipped += 1

    await db.flush()

    await log_event(
        db,
        event_type="scanner_flush_queue",
        detail={
            "scanner_id": scanner.id,
            "total_events": len(body.events),
            "processed": processed,
            "skipped": skipped,
            "error_count": len(errors),
        },
        ip_address=request.client.host if request.client else None,
    )

    return FlushQueueResponse(
        processed=processed,
        skipped=skipped,
        errors=errors,
    )
