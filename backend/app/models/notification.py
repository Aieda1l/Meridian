"""Notification model - in-app messages for members and admins."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .member import Member
    from .session import Session


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    related_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True
    )
    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    recipient: Mapped["Member"] = relationship(back_populates="notifications")
    related_session: Mapped[Optional["Session"]] = relationship()

    __table_args__ = (
        Index("ix_notifications_recipient_id", "recipient_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
        Index("ix_notifications_recipient_unread", "recipient_id", "is_read",
              postgresql_where="is_read = false"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.notification_type}, recipient={self.recipient_id})>"
