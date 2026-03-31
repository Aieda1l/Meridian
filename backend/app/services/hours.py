"""Shared hour computation service."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.season import Season
from app.models.session import Session, SessionStatus


async def compute_member_hours(
    db: AsyncSession,
    member_id: uuid.UUID | str,
    season: Season,
    now: datetime,
) -> tuple[float, float, float]:
    """Return (hours_today, hours_week, hours_season) for a member.
    
    Uses a single optimized query for closed sessions and accurately
    factors in the duration of any currently open session.
    """
    today_utc = now.date()
    today_start = datetime.combine(today_utc, datetime.min.time()).replace(
        tzinfo=timezone.utc
    )

    weekday = now.weekday()
    week_start = datetime.combine(
        today_utc - timedelta(days=weekday),
        datetime.min.time(),
    ).replace(tzinfo=timezone.utc)

    # 1. Sum up all closed/approved duration_minutes in a single query
    result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case((Session.check_in_at >= today_start, Session.duration_minutes), else_=0)
                ),
                0,
            ).label("today"),
            func.coalesce(
                func.sum(
                    case((Session.check_in_at >= week_start, Session.duration_minutes), else_=0)
                ),
                0,
            ).label("week"),
            func.coalesce(func.sum(Session.duration_minutes), 0).label("season"),
        ).where(
            and_(
                Session.member_id == str(member_id),
                Session.season_id == season.id,
                Session.status.in_([SessionStatus.closed, SessionStatus.approved]),
            )
        )
    )
    row = result.one()
    minutes_today = float(row.today)
    minutes_week = float(row.week)
    minutes_season = float(row.season)

    # 2. Add elapsed time for any currently open session
    open_result = await db.execute(
        select(Session.check_in_at).where(
            Session.member_id == str(member_id),
            Session.season_id == season.id,
            Session.status == SessionStatus.open,
        )
    )
    open_check_in = open_result.scalar_one_or_none()

    if open_check_in:
        elapsed_minutes = (now - open_check_in).total_seconds() / 60.0
        today_elapsed = max(0.0, (now - max(open_check_in, today_start)).total_seconds() / 60.0)
        week_elapsed = max(0.0, (now - max(open_check_in, week_start)).total_seconds() / 60.0)
        minutes_today += today_elapsed
        minutes_week += week_elapsed
        minutes_season += elapsed_minutes

    return (
        minutes_today / 60.0,
        minutes_week / 60.0,
        minutes_season / 60.0,
    )
