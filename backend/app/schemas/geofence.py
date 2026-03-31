"""Pydantic schemas for the geofence router."""
from __future__ import annotations
from pydantic import BaseModel, Field


class GeofenceExitRequest(BaseModel):
    member_id: str
    latitude: float
    longitude: float
    accuracy_meters: float


class GeofenceReturnRequest(BaseModel):
    member_id: str
    latitude: float
    longitude: float
    accuracy_meters: float


class GeofenceConfigResponse(BaseModel):
    polygon: list[dict[str, float]]
    grace_period_seconds: int
    buffer_meters: int
