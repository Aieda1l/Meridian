"""Season model - defines competition seasons with hour caps."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Date, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .member import Member
    from .session import Session
    from .hour_warning import HourWarning


class Season(TimestampMixin, Base):
    __tablename__ = "seasons"

    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    daily_hour_cap: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="12.0"
    )
    weekly_hour_cap: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default="60.0"
    )
    season_hour_cap: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, server_default="500.0"
    )

    # Relationships
    members: Mapped[List["Member"]] = relationship(back_populates="season")
    sessions: Mapped[List["Session"]] = relationship(back_populates="season")
    hour_warnings: Mapped[List["HourWarning"]] = relationship(back_populates="season")

    __table_args__ = (
        Index(
            "ix_seasons_active_unique",
            "is_active",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
        ),
    )

    def __repr__(self) -> str:
        return f"<Season(id={self.id}, name={self.name!r}, is_active={self.is_active})>"
