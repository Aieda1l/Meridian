"""Notifications router — list, read, mark-all-read.

- GET   /notifications              — paginated list for current user
- GET   /notifications/unread-count — badge count
- PATCH /notifications/{id}/read    — mark one as read
- POST  /notifications/mark-all-read — mark all as read
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_member
from app.models.member import Member
from app.models.notification import Notification
from app.schemas.notification import NotificationListOut, NotificationOut, UnreadCountOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return paginated notifications for the current user."""
    filters = [Notification.recipient_id == current.id]
    if unread_only:
        filters.append(Notification.is_read.is_(False))

    where = and_(*filters)

    count_result = await db.execute(select(func.count(Notification.id)).where(where))
    total = count_result.scalar_one()

    unread_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == current.id,
            Notification.is_read.is_(False),
        )
    )
    unread_count = unread_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Notification)
        .where(where)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    notifications = result.scalars().all()

    items = [
        NotificationOut(
            id=str(n.id),
            recipient_id=str(n.recipient_id),
            notification_type=n.notification_type,
            title=n.title,
            body=n.body,
            is_read=n.is_read,
            related_session_id=str(n.related_session_id) if n.related_session_id else None,
            detail=n.detail,
            created_at=n.created_at,
        )
        for n in notifications
    ]

    return NotificationListOut(
        items=items,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Return the number of unread notifications for badge display."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == current.id,
            Notification.is_read.is_(False),
        )
    )
    return UnreadCountOut(count=result.scalar_one())


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == current.id,
        )
    )
    notif = result.scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notif.is_read = True
    await db.flush()

    return NotificationOut(
        id=str(notif.id),
        recipient_id=str(notif.recipient_id),
        notification_type=notif.notification_type,
        title=notif.title,
        body=notif.body,
        is_read=notif.is_read,
        related_session_id=str(notif.related_session_id) if notif.related_session_id else None,
        detail=notif.detail,
        created_at=notif.created_at,
    )


@router.post("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Mark all notifications for the current user as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == current.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.flush()
    return {"status": "ok"}
