"""Hour cap evaluation and warning service.

Called after every checkout to check daily, weekly, and season hour caps.
Creates hour_warnings records and returns notification info.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hour_warning import HourWarning, WarningType
from app.models.session import Session, SessionStatus
from app.models.season import Season
from app.services.hours import compute_member_hours


async def evaluate_hour_caps(
    db: AsyncSession,
    member_id: uuid.UUID,
    season: Season,
) -> list[dict]:
    """Evaluate hour caps after a checkout.

    Checks daily, weekly, and season caps. Creates hour_warnings records
    for 80% and 100% thresholds if they don't already exist.

    Returns a list of warning dicts with keys:
        {"warning_type": str, "hours": float, "cap": float, "message": str}
    """
    now = datetime.now(timezone.utc)
    today_utc = now.date()
    today_start = datetime.combine(today_utc, datetime.min.time()).replace(tzinfo=timezone.utc)

    weekday = now.weekday()  # 0=Mon
    week_start = datetime.combine(
        today_utc - timedelta(days=weekday),
        datetime.min.time(),
    ).replace(tzinfo=timezone.utc)

    warnings_to_send: list[dict] = []

    # Calculate hours for each period
    hours_today, hours_week, hours_season = await compute_member_hours(db, member_id, season, now)

    # Check each cap
    cap_checks = [
        ("daily", hours_today, float(season.daily_hour_cap), WarningType.daily_80pct, WarningType.daily_cap, "daily"),
        ("weekly", hours_week, float(season.weekly_hour_cap), WarningType.weekly_80pct, WarningType.weekly_cap, "weekly"),
        ("season", hours_season, float(season.season_hour_cap), WarningType.season_80pct, WarningType.season_cap, "season"),
    ]

    for label, hours, cap, warn_80_type, warn_100_type, period in cap_checks:
        # 80% threshold
        if hours >= cap * 0.8 and hours < cap:
            exists = await _warning_exists(db, member_id, season.id, warn_80_type, period, today_start if period == "daily" else (week_start if period == "weekly" else None))
            if not exists:
                warning = HourWarning(
                    member_id=member_id,
                    season_id=season.id,
                    warning_type=warn_80_type,
                    triggered_at=now,
                )
                db.add(warning)
                warnings_to_send.append({
                    "warning_type": warn_80_type.value,
                    "hours": round(hours, 1),
                    "cap": cap,
                    "message": f"You've logged {hours:.1f} hours {label} — approaching your {label} limit of {cap:.0f} hours.",
                })

        # 100% threshold
        if hours >= cap:
            exists = await _warning_exists(db, member_id, season.id, warn_100_type, period, today_start if period == "daily" else (week_start if period == "weekly" else None))
            if not exists:
                warning = HourWarning(
                    member_id=member_id,
                    season_id=season.id,
                    warning_type=warn_100_type,
                    triggered_at=now,
                )
                db.add(warning)
                warnings_to_send.append({
                    "warning_type": warn_100_type.value,
                    "hours": round(hours, 1),
                    "cap": cap,
                    "message": f"You've reached your {label} hour limit. Future sessions {label} will be flagged for review.",
                    "notify_admins": True,
                })

    await db.flush()
    return warnings_to_send


async def _warning_exists(
    db: AsyncSession,
    member_id: uuid.UUID,
    season_id: uuid.UUID,
    warning_type: WarningType,
    period: str,
    period_start: datetime | None,
) -> bool:
    """Check if a warning of this type already exists for the current period."""
    filters = [
        HourWarning.member_id == member_id,
        HourWarning.season_id == season_id,
        HourWarning.warning_type == warning_type,
    ]
    if period_start:
        filters.append(HourWarning.triggered_at >= period_start)

    result = await db.execute(select(HourWarning.id).where(and_(*filters)).limit(1))
    return result.scalar_one_or_none() is not None
