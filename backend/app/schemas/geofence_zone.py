"""Pydantic schemas for geofence zone management."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class GeofenceZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    polygon: list[dict[str, float]]  # [{lat, lng}, ...]
    color: str = Field(default="#3388ff", pattern=r"^#[0-9a-fA-F]{6}$")
    scanner_ids: list[str] = []


class GeofenceZoneUpdate(BaseModel):
    name: str | None = None
    polygon: list[dict[str, float]] | None = None
    color: str | None = None
    scanner_ids: list[str] | None = None


class GeofenceZoneOut(BaseModel):
    id: str
    name: str
    polygon: list[dict[str, float]]
    color: str
    scanner_ids: list[str]
    created_at: datetime
    updated_at: datetime
