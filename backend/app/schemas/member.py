"""Pydantic schemas for the members router."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemberOut(BaseModel):
    id: str
    member_number: str
    name: str  # decrypted
    email: str  # decrypted
    phone: str | None = None  # decrypted
    role: str
    is_active: bool
    device_platform: str
    pass_serial: str | None = None
    photo_url: str | None = None
    season_id: str | None = None
    created_at: datetime


class MemberListOut(BaseModel):
    items: list[MemberOut]
    total: int
    page: int
    page_size: int


class MemberUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = Field(None, pattern="^(student|mentor|admin)$")
    is_active: bool | None = None
    photo_url: str | None = None
    season_id: str | None = None


class MemberHoursOut(BaseModel):
    member_id: str
    hours_today: float
    hours_this_week: float
    hours_this_season: float
    daily_cap: float
    weekly_cap: float
    season_cap: float


class SessionOut(BaseModel):
    id: str
    member_id: str
    season_id: str
    scanner_id: str | None = None
    check_in_at: datetime
    check_out_at: datetime | None = None
    duration_minutes: int | None = None
    check_in_method: str
    check_out_method: str | None = None
    status: str
    flag_reason: str | None = None
    created_at: datetime


class SessionListOut(BaseModel):
    items: list[SessionOut]
    total: int
    page: int
    page_size: int
