"""Pydantic schemas for the auth router."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="Member email address")
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    member_number: str = Field(..., max_length=12, description="Team-assigned ID, e.g. FRC-2025-042")
    name: str = Field(..., min_length=1)
    email: str = Field(..., description="Member email address")
    phone: str | None = None
    password: str = Field(..., min_length=8)
    role: str = Field("student", pattern="^(student|mentor|admin)$")
    season_id: str | None = Field(None, description="UUID of the season to assign")


class RegisterResponse(BaseModel):
    id: str
    member_number: str
    role: str
    pass_serial: str
    message: str = "Member created successfully"
