"""Session model - attendance check-in/check-out records."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .member import Member
    from .season import Season
    from .scanner import Scanner


class CheckInMethod(enum.Enum):
    nfc = "nfc"
    qr = "qr"


class CheckOutMethod(enum.Enum):
    nfc = "nfc"
    qr = "qr"
    geofence = "geofence"
    auto_timeout = "auto_timeout"
    self_report = "self_report"
    admin = "admin"


class SessionStatus(enum.Enum):
    open = "open"
    closed = "closed"
    flagged = "flagged"
    approved = "approved"


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("members.id"), nullable=False
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id"), nullable=False
    )
    scanner_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("scanners.id"), nullable=True
    )
    check_in_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    check_out_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    check_in_method: Mapped[CheckInMethod] = mapped_column(
        Enum(CheckInMethod, name="check_in_method", create_constraint=True),
        nullable=False,
    )
    check_out_method: Mapped[Optional[CheckOutMethod]] = mapped_column(
        Enum(CheckOutMethod, name="check_out_method", create_constraint=True),
        nullable=True,
    )
    selfie_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status", create_constraint=True),
        nullable=False,
    )
    flag_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    self_report_checkout_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    geofence_exit_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    member: Mapped["Member"] = relationship(back_populates="sessions")
    season: Mapped["Season"] = relationship(back_populates="sessions")
    scanner: Mapped[Optional["Scanner"]] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_member_id", "member_id"),
        Index("ix_sessions_season_id", "season_id"),
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_member_season", "member_id", "season_id"),
        Index("ix_sessions_check_in_at", "check_in_at"),
        Index(
            "ix_sessions_open_member",
            "member_id",
            postgresql_where=(status == SessionStatus.open.value),
        ),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, member_id={self.member_id}, status={self.status})>"
