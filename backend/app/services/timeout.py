"""Background auto-timeout and geofence grace-period service."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from redis.asyncio import Redis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.geofence import GRACE_KEY_PREFIX
from app.core.config import settings
from app.models.session import CheckOutMethod, Session, SessionStatus
from app.services.audit import log_event
from app.services.checkout import close_session

logger = logging.getLogger("meridian.autotimeout")

LOCK_KEY = "meridian:autotimeout_lock"
LOCK_TTL = 20  # seconds


async def run_auto_timeout(db: AsyncSession, redis_client: Redis) -> List[str]:
    """Execute the auto-timeout loop strictly using a Redis lock & row-level locking.
    
    Returns a list of actively closed session IDs.
    """
    # 1. Acquire Distributed Redis Lock
    lock_acquired = await redis_client.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL)
    if not lock_acquired:
        # Another instance (e.g. background loop & cron overlapping) is already processing this.
        return []

    now = datetime.now(timezone.utc)
    closed_ids: List[str] = []

    try:
        # ── 1. Auto-timeout: open sessions older than 12 hours ────────────────
        cutoff = now - timedelta(hours=12)
        result = await db.execute(
            select(Session.id).where(
                and_(
                    Session.status == SessionStatus.open,
                    Session.check_in_at <= cutoff,
                )
            )
        )
        stale_session_ids = result.scalars().all()

        for sid in stale_session_ids:
            # Row-level lock: ensure the session wasn't closed manually right as we loop
            res = await db.execute(
                select(Session)
                .where(Session.id == sid, Session.status == SessionStatus.open)
                .with_for_update(nowait=True)
            )
            locked_session = res.scalar_one_or_none()
            if locked_session:
                close_session(locked_session, CheckOutMethod.auto_timeout, now, flag_reason="auto_timeout")
                closed_ids.append(str(locked_session.id))

        # ── 2. Geofence grace period expiry ───────────────────────────────────
        geo_result = await db.execute(
            select(Session.id, Session.member_id).where(
                and_(
                    Session.status == SessionStatus.open,
                    Session.geofence_exit_at.is_not(None),
                )
            )
        )
        geo_sessions = geo_result.all()

        for sid, member_id in geo_sessions:
            grace_key = f"{GRACE_KEY_PREFIX}{member_id}"
            key_exists = await redis_client.exists(grace_key)

            if not key_exists:
                # Row-level lock: double check session hasn't manually recovered/checked-out
                # and geofence_exit_at hasn't been cleared by geofence/return endpoint.
                res = await db.execute(
                    select(Session)
                    .where(
                        Session.id == sid,
                        Session.status == SessionStatus.open,
                        Session.geofence_exit_at.is_not(None),
                    )
                    .with_for_update(nowait=True)
                )
                locked_session = res.scalar_one_or_none()
                if locked_session and locked_session.geofence_exit_at is not None:
                    checkout_time = locked_session.geofence_exit_at + timedelta(
                        seconds=settings.GEOFENCE_GRACE_PERIOD_SECONDS
                    )
                    if checkout_time > now:
                        checkout_time = now

                    close_session(locked_session, CheckOutMethod.geofence, checkout_time)
                    closed_ids.append(str(locked_session.id))
                    
                    await log_event(
                        db,
                        event_type="geofence_checkout",
                        actor_id=locked_session.member_id,
                        detail={"session_id": str(locked_session.id), "source": "auto_timeout"},
                    )

        if closed_ids:
            await db.commit()
            logger.info("Auto-timeout closed %d session(s): %s", len(closed_ids), closed_ids)

    except Exception:
        logger.exception("Auto-timeout execution error")
        await db.rollback()
    finally:
        # Unlock for concurrent safety
        await redis_client.delete(LOCK_KEY)

    return closed_ids
