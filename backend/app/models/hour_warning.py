"""HourWarning model - tracks hour-cap threshold notifications."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .member import Member
    from .season import Season


class WarningType(enum.Enum):
    daily_80pct = "daily_80pct"
    daily_cap = "daily_cap"
    weekly_80pct = "weekly_80pct"
    weekly_cap = "weekly_cap"
    season_80pct = "season_80pct"
    season_cap = "season_cap"


class HourWarning(TimestampMixin, Base):
    __tablename__ = "hour_warnings"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id"), nullable=False
    )
    warning_type: Mapped[WarningType] = mapped_column(
        Enum(WarningType, name="warning_type", create_constraint=True),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    notified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="hour_warnings")
    season: Mapped["Season"] = relationship(back_populates="hour_warnings")

    __table_args__ = (
        Index("ix_hour_warnings_member_id", "member_id"),
        Index("ix_hour_warnings_season_id", "season_id"),
        Index("ix_hour_warnings_member_season", "member_id", "season_id"),
    )

    def __repr__(self) -> str:
        return f"<HourWarning(id={self.id}, member_id={self.member_id}, warning_type={self.warning_type})>"
