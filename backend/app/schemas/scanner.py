"""Pydantic schemas for the scanner router."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    serial: str = Field(..., description="Pass serial number")
    nfc_payload: str | None = Field(None, description="NFC NDEF payload for NFC method")
    totp_code: str | None = Field(None, description="TOTP code for QR method")
    method: str = Field(..., pattern="^(nfc|qr)$")
    selfie_base64: str | None = None


class CheckInResponse(BaseModel):
    success: bool
    member_name: str
    check_in_at: datetime
    session_id: str


class CheckOutResponse(BaseModel):
    success: bool
    member_name: str
    duration_minutes: int
    total_hours_today: float
    total_hours_week: float
    total_hours_season: float


class HeartbeatRequest(BaseModel):
    scanner_id: str
    cache_version: int
    offline_queue_count: int = 0


class HeartbeatResponse(BaseModel):
    cache_stale: bool


class OfflineEvent(BaseModel):
    serial: str
    nfc_payload: str | None = None
    totp_code: str | None = None
    method: str = Field(..., pattern="^(nfc|qr)$")
    selfie_base64: str | None = None
    action: str = Field(..., pattern="^(checkin|checkout)$")
    timestamp: datetime


class FlushQueueRequest(BaseModel):
    events: list[OfflineEvent]


class FlushQueueResponse(BaseModel):
    processed: int
    skipped: int
    errors: list[str]
