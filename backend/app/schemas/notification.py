"""Pydantic schemas for the notifications router."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    recipient_id: str
    notification_type: str
    title: str
    body: str
    is_read: bool
    related_session_id: str | None = None
    detail: dict | None = None
    created_at: datetime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    total: int
    unread_count: int
    page: int
    page_size: int


class UnreadCountOut(BaseModel):
    count: int
