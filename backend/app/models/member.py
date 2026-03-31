"""Member model - team members with encrypted PII."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Index, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .season import Season
    from .session import Session
    from .hour_warning import HourWarning
    from .admin_event import AdminEvent


class MemberRole(enum.Enum):
    student = "student"
    mentor = "mentor"
    admin = "admin"


class DevicePlatform(enum.Enum):
    ios = "ios"
    android = "android"
    none = "none"


class Member(TimestampMixin, Base):
    __tablename__ = "members"

    member_number: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False
    )
    name_encrypted: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True
    )
    email_encrypted: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True
    )
    email_hash: Mapped[Optional[str]] = mapped_column(
        String, index=True, nullable=True
    )
    phone_encrypted: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, name="member_role", create_constraint=True),
        nullable=False,
    )
    password_hashed: Mapped[str] = mapped_column(String, nullable=False)
    totp_secret_encrypted: Mapped[Optional[bytes]] = mapped_column(
        LargeBinary, nullable=True
    )
    pass_serial: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=True
    )
    pass_auth_token_hashed: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    device_push_token: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    device_platform: Mapped[DevicePlatform] = mapped_column(
        Enum(DevicePlatform, name="device_platform", create_constraint=True),
        nullable=False,
        server_default="none",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    photo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    season_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("seasons.id"), nullable=True
    )

    # Relationships
    season: Mapped[Optional["Season"]] = relationship(back_populates="members")
    sessions: Mapped[List["Session"]] = relationship(back_populates="member")
    hour_warnings: Mapped[List["HourWarning"]] = relationship(
        back_populates="member"
    )
    admin_events: Mapped[List["AdminEvent"]] = relationship(
        back_populates="actor"
    )

    __table_args__ = (
        Index("ix_members_member_number", "member_number"),
        Index("ix_members_season_id", "season_id"),
        Index("ix_members_role", "role"),
        Index("ix_members_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Member(id={self.id}, member_number={self.member_number!r}, role={self.role})>"
