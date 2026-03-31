"""Season service module."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.season import Season


async def get_active_season(db: AsyncSession) -> Season:
    """Return the single active season or raise 404."""
    result = await db.execute(select(Season).where(Season.is_active == True))  # noqa: E712
    season = result.scalar_one_or_none()
    if season is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active season configured",
        )
    return season
