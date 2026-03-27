"""Audit event logging service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_event import AdminEvent


async def log_event(
    db: AsyncSession,
    *,
    event_type: str,
    actor_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AdminEvent:
    """Write an immutable audit log entry."""
    event = AdminEvent(
        actor_id=actor_id,
        event_type=event_type,
        target_id=target_id,
        detail=detail or {},
        ip_address=ip_address,
    )
    db.add(event)
    await db.flush()
    return event
