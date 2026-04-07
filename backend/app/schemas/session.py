"""Pydantic schemas for the sessions router."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class SessionDetailOut(BaseModel):
    id: str
    member_id: str
    member_name: str | None = None  # decrypted, admin only
    member_number: str
    season_id: str
    scanner_id: str | None = None
    check_in_at: datetime
    check_out_at: datetime | None = None
    duration_minutes: int | None = None
    check_in_method: str
    check_out_method: str | None = None
    selfie_url: str | None = None
    status: str
    flag_reason: str | None = None
    self_report_checkout_at: datetime | None = None
    geofence_exit_at: datetime | None = None
    created_at: datetime


class SessionListOut(BaseModel):
    items: list[SessionDetailOut]
    total: int
    page: int
    page_size: int


class SelfReportRequest(BaseModel):
    checkout_at: datetime = Field(..., description="Self-reported checkout time (must be after check-in, within 24h)")


class SessionApproveResponse(BaseModel):
    id: str
    status: str
    message: str


class AutoTimeoutResponse(BaseModel):
    timed_out_count: int
    session_ids: list[str]


class SessionDenyRequest(BaseModel):
    reason: str | None = Field(None, max_length=500, description="Optional reason for denying the session")
