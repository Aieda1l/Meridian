"""Pydantic schemas for the geofence router."""
from __future__ import annotations
from pydantic import BaseModel, Field


class GeofenceExitRequest(BaseModel):
    member_id: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float = Field(..., ge=0)


class GeofenceReturnRequest(BaseModel):
    member_id: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float = Field(..., ge=0)


class GeofenceConfigResponse(BaseModel):
    polygon: list[dict[str, float]]
    grace_period_seconds: int
    buffer_meters: int
