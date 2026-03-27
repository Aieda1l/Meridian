"""Scanner model - NFC/QR check-in stations."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .session import Session


class Scanner(Base):
    __tablename__ = "scanners"

    # Scanner uses a human-readable string PK, not UUID
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    api_key_hashed: Mapped[str] = mapped_column(String, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    offline_cache_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(back_populates="scanner")

    def __repr__(self) -> str:
        return f"<Scanner(id={self.id!r}, name={self.name!r})>"
