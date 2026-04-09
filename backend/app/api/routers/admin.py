"""Admin router — dashboard, seasons, sessions, export, audit log, bulk import.

- GET   /admin/dashboard                       — live dashboard stats
- GET   /admin/seasons                         — list all seasons
- POST  /admin/seasons                         — create new season (deactivates current, rolls over)
- PATCH /admin/seasons/{id}                    — update season
- PATCH /admin/sessions/{id}/force-checkout    — force-close an open session
- POST  /admin/checkout-all                    — close all open sessions
- GET   /admin/export                          — download CSV or PDF report
- GET   /admin/audit-log                       — paginated audit log
- POST  /admin/import-members                  — bulk CSV member import
- GET   /admin/geofence-zones                  — list all geofence zones
- POST  /admin/geofence-zones                  — create a geofence zone
- PATCH /admin/geofence-zones/{id}             — update a geofence zone
- DELETE /admin/geofence-zones/{id}            — delete a geofence zone
"""

from __future__ import annotations

import csv
import io
import secrets
import string
import uuid
from datetime import date, datetime, timedelta, timezone

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.encryption import pgp_decrypt, pgp_encrypt
from app.core.security import get_current_member, hash_email, hash_password, require_admin, require_admin_or_mentor
from app.models.admin_event import AdminEvent
from app.models.geofence_zone import GeofenceZone, scanner_geofence_zones
from app.models.hour_warning import HourWarning
from app.models.member import DevicePlatform, Member, MemberRole
from app.models.scanner import Scanner
from app.models.season import Season
from app.models.session import CheckOutMethod, Session, SessionStatus
from app.schemas.admin import (
    AuditLogEntry,
    AuditLogResponse,
    CheckoutAllResponse,
    DashboardMemberStatus,
    DashboardResponse,
    ForceCheckoutResponse,
    SeasonCreate,
    SeasonOut,
    SeasonUpdate,
)
from app.schemas.geofence_zone import GeofenceZoneCreate, GeofenceZoneOut, GeofenceZoneUpdate
from app.services.audit import log_event
from app.services.export import generate_csv, generate_pdf

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# GET /admin/dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    member: Member = Depends(require_admin_or_mentor),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    """Live dashboard: active members, checked-in list, flags, scanner status."""

    # Active member count
    active_count_result = await db.execute(
        select(func.count()).select_from(Member).where(Member.is_active == True)  # noqa: E712
    )
    active_member_count = active_count_result.scalar_one()

    # Checked-in (open) sessions with member info
    from app.core.config import settings
    open_sessions_result = await db.execute(
        select(
            Session,
            Member,
            func.pgp_sym_decrypt(Member.name_encrypted, settings.PGP_SYM_KEY).label("decrypted_name")
        )
        .join(Member, Session.member_id == Member.id)
        .where(Session.status == SessionStatus.open)
    )
    open_rows = open_sessions_result.all()

    now = datetime.now(timezone.utc)
    checked_in_members: list[DashboardMemberStatus] = []
    for session, mem, dec_name in open_rows:
        name = dec_name if dec_name else ""
        elapsed = int((now - session.check_in_at).total_seconds() / 60)
        checked_in_members.append(
            DashboardMemberStatus(
                member_id=str(mem.id),
                member_name=name,
                member_number=mem.member_number,
                check_in_at=session.check_in_at,
                duration_minutes=elapsed,
            )
        )

    # Flagged session count
    flagged_result = await db.execute(
        select(func.count()).select_from(Session).where(Session.status == SessionStatus.flagged)
    )
    flagged_session_count = flagged_result.scalar_one()

    # Hour-cap violations today
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    violations_result = await db.execute(
        select(func.count())
        .select_from(HourWarning)
        .where(HourWarning.triggered_at >= today_start)
    )
    hour_cap_violations_today = violations_result.scalar_one()

    # Scanner statuses
    scanners_result = await db.execute(select(Scanner))
    scanners = scanners_result.scalars().all()
    scanner_statuses = [
        {
            "id": s.id,
            "name": s.name,
            "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
        }
        for s in scanners
    ]

    return DashboardResponse(
        active_member_count=active_member_count,
        checked_in_count=len(checked_in_members),
        checked_in_members=checked_in_members,
        flagged_session_count=flagged_session_count,
        hour_cap_violations_today=hour_cap_violations_today,
        scanner_statuses=scanner_statuses,
    )


# ---------------------------------------------------------------------------
# GET /admin/seasons
# ---------------------------------------------------------------------------

@router.get("/seasons", response_model=list[SeasonOut])
async def list_seasons(
    member: Member = Depends(require_admin_or_mentor),
    db: AsyncSession = Depends(get_db),
) -> list[SeasonOut]:
    """Return all seasons ordered by start_date descending."""
    result = await db.execute(select(Season).order_by(Season.start_date.desc()))
    seasons = result.scalars().all()
    return [
        SeasonOut(
            id=str(s.id),
            name=s.name,
            start_date=s.start_date,
            end_date=s.end_date,
            is_active=s.is_active,
            daily_hour_cap=float(s.daily_hour_cap),
            weekly_hour_cap=float(s.weekly_hour_cap),
            season_hour_cap=float(s.season_hour_cap),
            created_at=s.created_at,
        )
        for s in seasons
    ]


# ---------------------------------------------------------------------------
# POST /admin/seasons
# ---------------------------------------------------------------------------

@router.post("/seasons", response_model=SeasonOut, status_code=status.HTTP_201_CREATED)
async def create_season(
    body: SeasonCreate,
    request: Request,
    member: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SeasonOut:
    """Create a new season with rollover logic.

    1. Deactivate the currently active season.
    2. Close all open sessions from the old season.
    3. Create the new season as active.
    4. Write an audit log entry.
    """
    # Find and deactivate the current active season
    old_season_id: str | None = None
    active_result = await db.execute(
        select(Season).where(Season.is_active == True)  # noqa: E712
    )
    old_season = active_result.scalar_one_or_none()
    if old_season:
        old_season_id = str(old_season.id)
        old_season.is_active = False

        # Close all open sessions from the old season
        open_sessions_result = await db.execute(
            select(Session).where(
                and_(
                    Session.season_id == old_season.id,
                    Session.status == SessionStatus.open,
                )
            )
        )
        open_sessions = open_sessions_result.scalars().all()
        now = datetime.now(timezone.utc)
        from app.services.checkout import close_session
        for sess in open_sessions:
            close_session(sess, CheckOutMethod.auto_timeout, now, flag_reason="season_rollover")

    # Create new season
    new_season = Season(
        name=body.name,
        start_date=body.start_date,
        end_date=body.end_date,
        is_active=True,
        daily_hour_cap=body.daily_hour_cap,
        weekly_hour_cap=body.weekly_hour_cap,
        season_hour_cap=body.season_hour_cap,
    )
    db.add(new_season)
    await db.flush()

    # Audit log
    await log_event(
        db,
        event_type="season_created",
        actor_id=member.id,
        target_id=new_season.id,
        detail={"old_season_id": old_season_id, "new_season_name": body.name},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()
    await db.refresh(new_season)

    return SeasonOut(
        id=str(new_season.id),
        name=new_season.name,
        start_date=new_season.start_date,
        end_date=new_season.end_date,
        is_active=new_season.is_active,
        daily_hour_cap=float(new_season.daily_hour_cap),
        weekly_hour_cap=float(new_season.weekly_hour_cap),
        season_hour_cap=float(new_season.season_hour_cap),
        created_at=new_season.created_at,
    )


# ---------------------------------------------------------------------------
# PATCH /admin/seasons/{id}
# ---------------------------------------------------------------------------

@router.patch("/seasons/{season_id}", response_model=SeasonOut)
async def update_season(
    season_id: uuid.UUID,
    body: SeasonUpdate,
    request: Request,
    member: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SeasonOut:
    """Update season fields that are provided."""
    result = await db.execute(select(Season).where(Season.id == season_id))
    season = result.scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    for field, value in update_data.items():
        setattr(season, field, value)

    await log_event(
        db,
        event_type="season_updated",
        actor_id=member.id,
        target_id=season.id,
        detail={"updated_fields": list(update_data.keys())},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()
    await db.refresh(season)

    return SeasonOut(
        id=str(season.id),
        name=season.name,
        start_date=season.start_date,
        end_date=season.end_date,
        is_active=season.is_active,
        daily_hour_cap=float(season.daily_hour_cap),
        weekly_hour_cap=float(season.weekly_hour_cap),
        season_hour_cap=float(season.season_hour_cap),
        created_at=season.created_at,
    )


# ---------------------------------------------------------------------------
# PATCH /admin/sessions/{id}/force-checkout — admin only
# ---------------------------------------------------------------------------

@router.patch("/sessions/{session_id}/force-checkout", response_model=ForceCheckoutResponse)
async def force_checkout_session(
    session_id: uuid.UUID,
    request: Request,
    member: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> ForceCheckoutResponse:
    """Force-checkout an open session. Admin only."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if session.status != SessionStatus.open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Session status is '{session.status.value}', expected 'open'",
        )

    now = datetime.now(timezone.utc)
    from app.services.checkout import close_session
    close_session(session, CheckOutMethod.admin, now)

    await db.flush()

    await log_event(
        db,
        event_type="admin_force_checkout",
        actor_id=member.id,
        target_id=session.id,
        detail={"member_id": str(session.member_id)},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()

    return ForceCheckoutResponse(
        session_id=str(session.id),
        status=session.status.value,
        message="Session closed by admin",
    )


# ---------------------------------------------------------------------------
# POST /admin/checkout-all — admin only
# ---------------------------------------------------------------------------

@router.post("/checkout-all", response_model=CheckoutAllResponse)
async def checkout_all_sessions(
    request: Request,
    member: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CheckoutAllResponse:
    """Close all currently open sessions. Admin only."""
    result = await db.execute(
        select(Session).where(Session.status == SessionStatus.open)
    )
    open_sessions = result.scalars().all()

    now = datetime.now(timezone.utc)
    closed_ids: list[str] = []

    from app.services.checkout import close_session
    for sess in open_sessions:
        close_session(sess, CheckOutMethod.admin, now)
        closed_ids.append(str(sess.id))

    await db.flush()

    await log_event(
        db,
        event_type="admin_checkout_all",
        actor_id=member.id,
        target_id=None,
        detail={"closed_count": len(closed_ids), "session_ids": closed_ids},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()

    return CheckoutAllResponse(closed_count=len(closed_ids), session_ids=closed_ids)


# ---------------------------------------------------------------------------
# GET /admin/export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_report(
    season_id: uuid.UUID = Query(..., description="Season to export"),
    format: str = Query("csv", pattern="^(csv|pdf)$", description="Export format: csv or pdf"),
    member_id: uuid.UUID | None = Query(None, description="Optional member filter"),
    columns: str | None = Query(None, description="Comma-separated column keys to include (default: all)"),
    include_summary: bool = Query(True, description="Include member hour totals summary section"),
    member: Member = Depends(require_admin_or_mentor),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download a CSV or PDF attendance report for a season."""

    # Verify season exists
    season_result = await db.execute(select(Season).where(Season.id == season_id))
    season = season_result.scalar_one_or_none()
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")

    # Build session query
    stmt = (
        select(Session, Member)
        .join(Member, Session.member_id == Member.id)
        .where(Session.season_id == season_id)
        .order_by(Member.member_number, Session.check_in_at)
    )
    if member_id:
        stmt = stmt.where(Session.member_id == member_id)

    result = await db.execute(stmt)
    rows = result.all()

    # Build session dicts and accumulate member totals
    sessions: list[dict] = []
    totals_map: dict[str, dict] = {}  # member_number -> {name, total_minutes}
    name_cache: dict[str, str] = {}

    for sess, mem in rows:
        if mem.id not in name_cache:
            name_cache[mem.id] = await pgp_decrypt(db, mem.name_encrypted) if mem.name_encrypted else ""
        name = name_cache[mem.id]
        dur = sess.duration_minutes or 0

        sessions.append({
            "member_number": mem.member_number,
            "name": name,
            "role": mem.role.value if mem.role else "",
            "date": sess.check_in_at.strftime("%Y-%m-%d"),
            "check_in_time": sess.check_in_at.strftime("%H:%M"),
            "check_out_time": sess.check_out_at.strftime("%H:%M") if sess.check_out_at else "",
            "duration_minutes": dur,
            "method": sess.check_in_method.value if sess.check_in_method else "",
            "status": sess.status.value if sess.status else "",
            "flag_reason": sess.flag_reason or "",
        })

        key = mem.member_number
        if key not in totals_map:
            totals_map[key] = {"member_number": key, "name": name, "total_minutes": 0}
        totals_map[key]["total_minutes"] += dur

    member_totals = list(totals_map.values())

    # Parse column filter — None means "all columns"
    col_set: set[str] | None = None
    if columns:
        col_set = {c.strip() for c in columns.split(",") if c.strip()}

    if format == "pdf":
        content = generate_pdf(sessions, member_totals, season.name,
                               columns=col_set, include_summary=include_summary)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="attendance_{season.name}.pdf"',
            },
        )

    # Default: CSV
    content = generate_csv(sessions, member_totals,
                           columns=col_set, include_summary=include_summary)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="attendance_{season.name}.csv"',
        },
    )


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------

@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    event_type: str | None = Query(None, description="Filter by event type"),
    member: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Paginated audit log. Admin only."""

    # Base query
    where_clauses = []
    if event_type:
        where_clauses.append(AdminEvent.event_type == event_type)

    # Total count
    count_stmt = select(func.count()).select_from(AdminEvent)
    if where_clauses:
        count_stmt = count_stmt.where(*where_clauses)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Paginated results
    offset = (page - 1) * page_size
    items_stmt = (
        select(AdminEvent)
        .order_by(AdminEvent.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if where_clauses:
        items_stmt = items_stmt.where(*where_clauses)

    items_result = await db.execute(items_stmt)
    events = items_result.scalars().all()

    return AuditLogResponse(
        items=[
            AuditLogEntry(
                id=str(e.id),
                actor_id=str(e.actor_id) if e.actor_id else None,
                event_type=e.event_type,
                target_id=str(e.target_id) if e.target_id else None,
                detail=e.detail,
                ip_address=str(e.ip_address) if e.ip_address else None,
                created_at=e.created_at,
            )
            for e in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# POST /admin/import-members — bulk CSV import
# ---------------------------------------------------------------------------

def _generate_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/import-members")
async def import_members(
    file: UploadFile,
    request: Request,
    admin: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-import members from a CSV file.

    Expected columns: member_number, name, email, phone (optional), role (optional).
    Auto-assigns the active season. Generates a random password and TOTP secret
    for each member. Returns created members with their temporary passwords.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # Validate headers
    required = {"member_number", "name", "email"}
    if reader.fieldnames is None or not required.issubset({f.strip().lower() for f in reader.fieldnames}):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must have columns: {', '.join(sorted(required))}. Found: {reader.fieldnames}",
        )

    # Get active season for auto-assignment
    from app.services.season import get_active_season
    try:
        active_season = await get_active_season(db)
        season_id = active_season.id
    except HTTPException:
        season_id = None

    results: list[dict] = []
    errors: list[dict] = []

    for row_num, row in enumerate(reader, start=2):
        # Normalize keys to lowercase
        row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        member_number = row.get("member_number", "")
        name = row.get("name", "")
        email = row.get("email", "")
        phone = row.get("phone", "")
        role_str = row.get("role", "student").lower() or "student"

        if not member_number or not name or not email:
            errors.append({"row": row_num, "error": "Missing required field(s)", "member_number": member_number})
            continue

        # Check for duplicate member_number
        existing = await db.execute(select(Member).where(Member.member_number == member_number))
        if existing.scalar_one_or_none() is not None:
            errors.append({"row": row_num, "error": "Duplicate member_number", "member_number": member_number})
            continue

        # Check for duplicate email
        email_hash_val = hash_email(email)
        existing_email = await db.execute(select(Member).where(Member.email_hash == email_hash_val))
        if existing_email.scalar_one_or_none() is not None:
            errors.append({"row": row_num, "error": "Email already exists", "member_number": member_number})
            continue

        try:
            role = MemberRole(role_str)
        except ValueError:
            role = MemberRole.student

        password = _generate_password()

        name_enc = await pgp_encrypt(db, name)
        email_enc = await pgp_encrypt(db, email)
        phone_enc = await pgp_encrypt(db, phone) if phone else None

        totp_secret = pyotp.random_base32()
        totp_enc = await pgp_encrypt(db, totp_secret)

        pass_serial = uuid.uuid4()

        member = Member(
            member_number=member_number,
            name_encrypted=name_enc,
            email_encrypted=email_enc,
            email_hash=email_hash_val,
            phone_encrypted=phone_enc,
            role=role,
            password_hashed=hash_password(password),
            totp_secret_encrypted=totp_enc,
            pass_serial=pass_serial,
            device_platform=DevicePlatform.none,
            season_id=season_id,
        )
        db.add(member)
        await db.flush()

        results.append({
            "member_number": member_number,
            "name": name,
            "email": email,
            "password": password,
            "pass_serial": str(pass_serial),
        })

    # Audit log
    await log_event(
        db,
        event_type="members_bulk_imported",
        actor_id=admin.id,
        detail={"imported_count": len(results), "error_count": len(errors)},
        ip_address=request.client.host if request.client else None,
    )

    return {"imported": results, "errors": errors, "total_imported": len(results), "total_errors": len(errors)}


# ---------------------------------------------------------------------------
# Geofence Zone CRUD
# ---------------------------------------------------------------------------

def _zone_to_out(zone: GeofenceZone) -> GeofenceZoneOut:
    import json
    return GeofenceZoneOut(
        id=str(zone.id),
        name=zone.name,
        polygon=json.loads(zone.polygon_json),
        color=zone.color,
        scanner_ids=[s.id for s in zone.scanners],
        created_at=zone.created_at,
        updated_at=zone.updated_at,
    )


@router.get("/geofence-zones", response_model=list[GeofenceZoneOut])
async def list_geofence_zones(
    admin: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[GeofenceZoneOut]:
    """Return all geofence zones with their assigned scanners."""
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(GeofenceZone)
        .options(selectinload(GeofenceZone.scanners))
        .order_by(GeofenceZone.name)
    )
    zones = result.scalars().all()
    return [_zone_to_out(z) for z in zones]


@router.post("/geofence-zones", response_model=GeofenceZoneOut, status_code=status.HTTP_201_CREATED)
async def create_geofence_zone(
    body: GeofenceZoneCreate,
    request: Request,
    admin: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> GeofenceZoneOut:
    """Create a new geofence zone."""
    import json
    from sqlalchemy.orm import selectinload

    zone = GeofenceZone(
        name=body.name,
        polygon_json=json.dumps(body.polygon),
        color=body.color,
    )
    db.add(zone)
    await db.flush()

    # Link scanners via association table (avoids lazy-load on async session)
    if body.scanner_ids:
        for sid in body.scanner_ids:
            await db.execute(
                scanner_geofence_zones.insert().values(scanner_id=sid, zone_id=zone.id)
            )

    await log_event(
        db,
        event_type="geofence_zone_created",
        actor_id=admin.id,
        target_id=zone.id,
        detail={"name": body.name, "scanner_ids": body.scanner_ids},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()

    # Re-fetch with scanners eagerly loaded
    result = await db.execute(
        select(GeofenceZone)
        .options(selectinload(GeofenceZone.scanners))
        .where(GeofenceZone.id == zone.id)
    )
    zone = result.scalar_one()
    return _zone_to_out(zone)


@router.patch("/geofence-zones/{zone_id}", response_model=GeofenceZoneOut)
async def update_geofence_zone(
    zone_id: uuid.UUID,
    body: GeofenceZoneUpdate,
    request: Request,
    admin: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> GeofenceZoneOut:
    """Update a geofence zone's name, polygon, color, or scanner assignments."""
    import json
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(GeofenceZone)
        .options(selectinload(GeofenceZone.scanners))
        .where(GeofenceZone.id == zone_id)
    )
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

    if body.name is not None:
        zone.name = body.name
    if body.polygon is not None:
        zone.polygon_json = json.dumps(body.polygon)
    if body.color is not None:
        zone.color = body.color
    if body.scanner_ids is not None:
        # Clear existing associations and re-insert
        await db.execute(
            scanner_geofence_zones.delete().where(scanner_geofence_zones.c.zone_id == zone_id)
        )
        for sid in body.scanner_ids:
            await db.execute(
                scanner_geofence_zones.insert().values(scanner_id=sid, zone_id=zone_id)
            )

    await db.flush()

    await log_event(
        db,
        event_type="geofence_zone_updated",
        actor_id=admin.id,
        target_id=zone.id,
        detail={"name": zone.name},
        ip_address=request.client.host if request.client else None,
    )

    await db.flush()

    # Re-fetch with scanners eagerly loaded
    result = await db.execute(
        select(GeofenceZone)
        .options(selectinload(GeofenceZone.scanners))
        .where(GeofenceZone.id == zone_id)
    )
    zone = result.scalar_one()
    return _zone_to_out(zone)


@router.delete("/geofence-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_geofence_zone(
    zone_id: uuid.UUID,
    request: Request,
    admin: Member = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a geofence zone."""
    result = await db.execute(select(GeofenceZone).where(GeofenceZone.id == zone_id))
    zone = result.scalar_one_or_none()
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

    await log_event(
        db,
        event_type="geofence_zone_deleted",
        actor_id=admin.id,
        target_id=zone.id,
        detail={"name": zone.name},
        ip_address=request.client.host if request.client else None,
    )

    await db.delete(zone)
    await db.flush()
