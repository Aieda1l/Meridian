"""Pydantic schemas for geofence zone management."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


def _validate_polygon(polygon: list[dict[str, float]]) -> list[dict[str, float]]:
    """Validate polygon has at least 3 points with valid coordinates."""
    if len(polygon) < 3:
        raise ValueError("Polygon must have at least 3 points")
    for i, pt in enumerate(polygon):
        lat = pt.get("lat")
        lng = pt.get("lng")
        if lat is None or lng is None:
            raise ValueError(f"Point {i} must have 'lat' and 'lng' keys")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Point {i}: lat must be between -90 and 90, got {lat}")
        if not (-180 <= lng <= 180):
            raise ValueError(f"Point {i}: lng must be between -180 and 180, got {lng}")
    return polygon


class GeofenceZoneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    polygon: list[dict[str, float]]  # [{lat, lng}, ...]
    color: str = Field(default="#3388ff", pattern=r"^#[0-9a-fA-F]{6}$")
    scanner_ids: list[str] = []

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: list[dict[str, float]]) -> list[dict[str, float]]:
        return _validate_polygon(v)


class GeofenceZoneUpdate(BaseModel):
    name: str | None = None
    polygon: list[dict[str, float]] | None = None
    color: str | None = None
    scanner_ids: list[str] | None = None

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, v: list[dict[str, float]] | None) -> list[dict[str, float]] | None:
        if v is not None:
            return _validate_polygon(v)
        return v


class GeofenceZoneOut(BaseModel):
    id: str
    name: str
    polygon: list[dict[str, float]]
    color: str
    scanner_ids: list[str]
    created_at: datetime
    updated_at: datetime
