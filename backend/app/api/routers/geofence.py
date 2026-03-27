"""Geofence router -- exit, return, config.

- POST /geofence/exit   -- PWA reports member left the shop; starts 90s grace period
- POST /geofence/return -- PWA reports member returned during grace period; cancels checkout
- GET  /geofence/config -- returns shop polygon and grace period for PWA to configure
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Point, Polygon

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import get_current_member
from app.models.member import Member
from app.models.session import Session, SessionStatus
from app.schemas.geofence import (
    GeofenceConfigResponse,
    GeofenceExitRequest,
    GeofenceReturnRequest,
)
from app.services.audit import log_event

router = APIRouter(prefix="/geofence", tags=["geofence"])

GRACE_KEY_PREFIX = "geofence_grace:"


def _build_shop_polygon() -> Polygon:
    """Build a Shapely Polygon from the configured geofence coordinates."""
    coords = [(pt["lng"], pt["lat"]) for pt in settings.GEOFENCE_POLYGON]
    return Polygon(coords)


def _is_inside_buffered_polygon(polygon: Polygon, latitude: float, longitude: float) -> bool:
    """Return True if the point falls inside the polygon + buffer zone."""
    # Approximate conversion: 1 degree latitude ~= 111 320 m
    buffer_degrees = settings.GEOFENCE_BUFFER_METERS / 111320
    buffered = polygon.buffer(buffer_degrees)
    point = Point(longitude, latitude)
    return buffered.contains(point)


@router.post("/exit")
async def geofence_exit(
    body: GeofenceExitRequest,
    member: Member = Depends(get_current_member),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """Report that a member has left the shop boundary."""

    # 1. Verify the authenticated member matches the request
    if str(member.id) != body.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member_id does not match authenticated user",
        )

    # 2. Check for an open session
    result = await db.execute(
        select(Session).where(
            Session.member_id == member.id,
            Session.status == SessionStatus.active,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session found",
        )

    # 3. Server-side geofence re-validation
    polygon = _build_shop_polygon()
    if _is_inside_buffered_polygon(polygon, body.latitude, body.longitude):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Location is within shop boundary",
        )

    # 4. Set grace period key in Redis
    grace_key = f"{GRACE_KEY_PREFIX}{member.id}"
    await redis.set(
        grace_key,
        str(session.id),
        ex=settings.GEOFENCE_GRACE_PERIOD_SECONDS,
    )

    # 5. Update session geofence_exit_at
    session.geofence_exit_at = datetime.now(timezone.utc)
    await db.commit()

    # 6. Log to admin events
    await log_event(
        db,
        event_type="geofence_exit",
        member_id=str(member.id),
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

    # 1. Verify member
    if str(member.id) != body.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="member_id does not match authenticated user",
        )

    # 2. Check Redis for grace period key
    grace_key = f"{GRACE_KEY_PREFIX}{member.id}"
    session_id = await redis.get(grace_key)

    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Grace period has expired",
        )

    # 3. Grace period active -- cancel pending checkout
    await redis.delete(grace_key)

    # Clear geofence_exit_at on the session
    result = await db.execute(
        select(Session).where(
            Session.member_id == member.id,
            Session.status == SessionStatus.active,
        )
    )
    session = result.scalar_one_or_none()
    if session is not None:
        session.geofence_exit_at = None
        await db.commit()

    return {"status": "return_confirmed"}


@router.get("/config", response_model=GeofenceConfigResponse)
async def geofence_config(
    member: Member = Depends(get_current_member),
):
    """Return the shop polygon and grace period configuration for the PWA."""
    return GeofenceConfigResponse(
        polygon=settings.GEOFENCE_POLYGON,
        grace_period_seconds=settings.GEOFENCE_GRACE_PERIOD_SECONDS,
        buffer_meters=settings.GEOFENCE_BUFFER_METERS,
    )
