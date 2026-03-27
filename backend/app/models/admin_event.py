"""AdminEvent model - audit log for administrative actions."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .member import Member


class AdminEvent(TimestampMixin, Base):
    __tablename__ = "admin_events"

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)

    # Relationships
    actor: Mapped[Optional["Member"]] = relationship(
        back_populates="admin_events"
    )

    __table_args__ = (
        Index("ix_admin_events_actor_id", "actor_id"),
        Index("ix_admin_events_event_type", "event_type"),
        Index("ix_admin_events_target_id", "target_id"),
        Index("ix_admin_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AdminEvent(id={self.id}, event_type={self.event_type!r}, actor_id={self.actor_id})>"
