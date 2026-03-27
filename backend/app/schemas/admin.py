"""Pydantic schemas for the admin router."""
from __future__ import annotations
from datetime import date, datetime
from pydantic import BaseModel, Field


class DashboardMemberStatus(BaseModel):
    member_id: str
    member_name: str
    member_number: str
    check_in_at: datetime
    duration_minutes: int  # elapsed so far


class DashboardResponse(BaseModel):
    active_member_count: int
    checked_in_count: int
    checked_in_members: list[DashboardMemberStatus]
    flagged_session_count: int
    hour_cap_violations_today: int
    scanner_statuses: list[dict]


class SeasonOut(BaseModel):
    id: str
    name: str
    start_date: date
    end_date: date
    is_active: bool
    daily_hour_cap: float
    weekly_hour_cap: float
    season_hour_cap: float
    created_at: datetime


class SeasonCreate(BaseModel):
    name: str = Field(..., min_length=1)
    start_date: date
    end_date: date
    daily_hour_cap: float = 12.0
    weekly_hour_cap: float = 60.0
    season_hour_cap: float = 500.0


class SeasonUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    daily_hour_cap: float | None = None
    weekly_hour_cap: float | None = None
    season_hour_cap: float | None = None


class AuditLogEntry(BaseModel):
    id: str
    actor_id: str | None = None
    event_type: str
    target_id: str | None = None
    detail: dict | None = None
    ip_address: str | None = None
    created_at: datetime


class AuditLogResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
