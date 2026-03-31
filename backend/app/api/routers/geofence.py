"""Geofence router -- exit, return, config.

- POST /geofence/exit   -- PWA reports member left the shop; starts grace period
- POST /geofence/return -- PWA reports member returned during grace period; cancels checkout
- GET  /geofence/config -- returns zone polygons and grace period for PWA
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from shapely.geometry import Point, Polygon

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import get_current_member
from app.models.geofence_zone import GeofenceZone, scanner_geofence_zones
from app.models.member import Member
from app.models.session import CheckOutMethod, Session, SessionStatus
from app.schemas.geofence import (
    GeofenceExitRequest,
    GeofenceReturnRequest,
)
from app.services.audit import log_event

router = APIRouter(prefix="/geofence", tags=["geofence"])

GRACE_KEY_PREFIX = "geofence_grace:"


async def _get_zones_for_scanner(db: AsyncSession, scanner_id: str | None) -> list[dict]:
    """Fetch zone polygons linked to a specific scanner.

    If scanner_id is None or no zones are linked, returns ALL zones.
    Falls back to GEOFENCE_POLYGON env var if no DB zones exist at all.
    """
    all_zones_result = await db.execute(
        select(GeofenceZone).options(selectinload(GeofenceZone.scanners))
    )
    all_zones = all_zones_result.scalars().all()

    if not all_zones:
        # Fallback to env var
        env_polygon = settings.geofence_polygon_list
        if env_polygon:
            return [{"id": "env", "name": "Default", "polygon": env_polygon, "color": "#3388ff"}]
        return []

    def _zone_dict(z: GeofenceZone) -> dict:
        return {
            "id": str(z.id),
            "name": z.name,
            "polygon": json.loads(z.polygon_json),
            "color": z.color,
            "scanner_ids": [s.id for s in z.scanners],
        }

    # If a scanner_id is given, filter to zones linked to that scanner
    if scanner_id:
        linked = [z for z in all_zones if any(s.id == scanner_id for s in z.scanners)]
        if linked:
            return [_zone_dict(z) for z in linked]

    # No scanner filter, or no zones linked to this scanner — return all
    return [_zone_dict(z) for z in all_zones]


def _is_inside_any_polygon(
    zone_polygons: list[dict], latitude: float, longitude: float,
) -> bool:
    """Return True if the point falls inside any zone polygon + buffer."""
    buffer_degrees = settings.GEOFENCE_BUFFER_METERS / 111320
    point = Point(longitude, latitude)
    for zp in zone_polygons:
        coords = [(pt["lng"], pt["lat"]) for pt in zp["polygon"]]
        if len(coords) < 3:
            continue
        poly = Polygon(coords).buffer(buffer_degrees)
        if poly.contains(point):
            return True
    return False


@router.post("/exit")
async def geofence_exit(
    body: GeofenceExitRequest,
    member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Report that a member has left the shop boundary."""

    if str(member.id) != body.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member_id does not match authenticated user",
        )

    result = await db.execute(
        select(Session).where(
            Session.member_id == member.id,
            Session.status == SessionStatus.open,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found",
        )

    # Validate against zones linked to the session's scanner
    zone_polygons = await _get_zones_for_scanner(db, session.scanner_id)
    if not zone_polygons:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No geofence zones configured",
        )

    if _is_inside_any_polygon(zone_polygons, body.latitude, body.longitude):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Location is within shop boundary",
        )

    grace_key = f"{GRACE_KEY_PREFIX}{member.id}"
    await redis.set(
        grace_key,
        str(session.id),
        ex=settings.GEOFENCE_GRACE_PERIOD_SECONDS,
    )

    session.geofence_exit_at = datetime.now(timezone.utc)
    await db.flush()

    await log_event(
        db,
        event_type="geofence_exit",
        actor_id=member.id,
        detail={
            "session_id": str(session.id),
            "latitude": body.latitude,
            "longitude": body.longitude,
            "accuracy_meters": body.accuracy_meters,
        },
    )

    return {
        "status": "grace_period_started",
        "grace_period_seconds": settings.GEOFENCE_GRACE_PERIOD_SECONDS,
    }


@router.post("/return")
async def geofence_return(
    body: GeofenceReturnRequest,
    member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Report that a member has returned during the grace period."""

    if str(member.id) != body.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member_id does not match authenticated user",
        )

    grace_key = f"{GRACE_KEY_PREFIX}{member.id}"
    session_id = await redis.get(grace_key)

    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Grace period has expired",
        )

    # CRITICAL: We DO NOT violently delete the grace_key here!
    # If the background timeout loop iterates simultaneously, we want redis.exists(grace_key)
    # to evaluate True to protect this session from being auto-checked out mid-transaction.
    # The key will safely expire naturally.

    result = await db.execute(
        select(Session).where(
            Session.member_id == member.id,
            Session.status == SessionStatus.open,
        )
    )
    session = result.scalar_one_or_none()
    if session is not None:
        session.geofence_exit_at = None
        await db.flush()

    return {"status": "return_confirmed"}


@router.post("/checkout")
async def geofence_checkout(
    member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Close the member's open session after the grace period expired."""

    result = await db.execute(
        select(Session).where(
            Session.member_id == member.id,
            Session.status == SessionStatus.open,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found",
        )

    from app.services.checkout import close_session
    close_session(session, CheckOutMethod.geofence, datetime.now(timezone.utc), flag_reason="geofence_auto")

    await db.flush()

    # Clean up any lingering grace key
    grace_key = f"{GRACE_KEY_PREFIX}{member.id}"
    await redis.delete(grace_key)

    await log_event(
        db,
        event_type="geofence_checkout",
        actor_id=member.id,
        detail={"session_id": str(session.id)},
    )

    return {
        "status": "checked_out",
        "session_id": str(session.id),
    }


@router.get("/config")
async def geofence_config(
    member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    scanner_id: str | None = Query(None),
):
    """Return zone polygons and grace period configuration for the PWA.

    If scanner_id is provided, only returns zones linked to that scanner.
    """
    zone_polygons = await _get_zones_for_scanner(db, scanner_id)

    # Legacy: flatten all zone polygons into a single list for old clients
    all_points: list[dict[str, float]] = []
    for zp in zone_polygons:
        all_points.extend(zp["polygon"])

    return {
        "polygon": all_points,
        "zones": zone_polygons,
        "grace_period_seconds": settings.GEOFENCE_GRACE_PERIOD_SECONDS,
        "buffer_meters": settings.GEOFENCE_BUFFER_METERS,
    }
