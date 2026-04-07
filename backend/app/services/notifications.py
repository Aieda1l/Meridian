"""Notification creation service."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member, MemberRole
from app.models.notification import Notification


async def create_notification(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    related_session_id: uuid.UUID | None = None,
    detail: dict[str, Any] | None = None,
) -> Notification:
    """Create a single notification record."""
    notif = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        body=body,
        related_session_id=related_session_id,
        detail=detail,
    )
    db.add(notif)
    await db.flush()
    return notif


async def notify_all_admins(
    db: AsyncSession,
    *,
    notification_type: str,
    title: str,
    body: str,
    detail: dict[str, Any] | None = None,
) -> list[Notification]:
    """Create a notification for every active admin member."""
    result = await db.execute(
        select(Member.id).where(
            Member.role == MemberRole.admin,
            Member.is_active.is_(True),
        )
    )
    admin_ids = result.scalars().all()

    notifications = []
    for admin_id in admin_ids:
        notif = await create_notification(
            db,
            recipient_id=admin_id,
            notification_type=notification_type,
            title=title,
            body=body,
            detail=detail,
        )
        notifications.append(notif)
    return notifications
