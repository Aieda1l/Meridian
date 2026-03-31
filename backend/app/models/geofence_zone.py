"""GeofenceZone model — named polygon boundaries linked to scanners."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .scanner import Scanner

# Association table: many-to-many between geofence zones and scanners
scanner_geofence_zones = Table(
    "scanner_geofence_zones",
    Base.metadata,
    Column("scanner_id", String, ForeignKey("scanners.id", ondelete="CASCADE"), primary_key=True),
    Column("zone_id", UUID(as_uuid=True), ForeignKey("geofence_zones.id", ondelete="CASCADE"), primary_key=True),
)


class GeofenceZone(TimestampMixin, Base):
    __tablename__ = "geofence_zones"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # JSON array of {lat, lng} coordinate pairs defining the polygon
    polygon_json: Mapped[str] = mapped_column(Text, nullable=False)
    # Hex color for map display (e.g. "#3388ff")
    color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="'#3388ff'")

    # Many-to-many with scanners
    scanners: Mapped[List["Scanner"]] = relationship(
        secondary=scanner_geofence_zones,
        back_populates="geofence_zones",
    )

    def __repr__(self) -> str:
        return f"<GeofenceZone(id={self.id}, name={self.name!r})>"
