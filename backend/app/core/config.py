"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Meridian FRC Attendance System configuration.

    All values are loaded from environment variables or a .env file located
    in the backend/ directory.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str  # e.g. postgresql+asyncpg://user:pass@host:5432/meridian
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT / Auth ──────────────────────────────────────────────────────
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── pgcrypto symmetric encryption key ───────────────────────────────
    PGP_SYM_KEY: str = ""

    # ── Apple Wallet pass signing (base64-encoded PEM / DER) ───────────
    APPLE_PASS_CERT_B64: str = ""
    APPLE_PASS_KEY_B64: str = ""
    APPLE_PASS_WWDR_B64: str = ""
    APPLE_PASS_TYPE_ID: str = ""
    APPLE_TEAM_ID: str = ""

    # ── Google Wallet service-account (base64-encoded JSON) ─────────────
    GOOGLE_SERVICE_ACCOUNT_JSON_B64: str = ""

    # ── APNs (Apple Push Notification service) ──────────────────────────
    APNS_KEY_B64: str = ""
    APNS_KEY_ID: str = ""
    APNS_TEAM_ID: str = ""
    APNS_TOPIC: str = ""

    # ── FCM (Firebase Cloud Messaging) ──────────────────────────────────
    FCM_PROJECT_ID: str = ""

    # ── Scanner ────────────────────────────────────────────────────────
    SCANNER_API_KEY: str = ""

    # ── NFC ──────────────────────────────────────────────────────────────
    NFC_HMAC_SECRET: str = ""

    # ── Google Wallet issuer ─────────────────────────────────────────────
    GOOGLE_WALLET_ISSUER_ID: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── Team branding (optional) ────────────────────────────────────────
    TEAM_NAME: str = "FRC Team"
    TEAM_NUMBER: str = ""
    TEAM_LOGO_URL: str = ""

    # ── Cron / auto-timeout ─────────────────────────────────────────────
    CRON_SECRET: str = ""

    # ── Geofence ────────────────────────────────────────────────────────
    GEOFENCE_POLYGON: list[dict[str, float]] = []

    @field_validator("GEOFENCE_POLYGON", mode="before")
    @classmethod
    def _parse_geofence_polygon(cls, v: Any) -> list[dict[str, float]]:
        if isinstance(v, str):
            if not v.strip():
                return []
            return json.loads(v)
        return v

    GEOFENCE_BUFFER_METERS: int = 150
    GEOFENCE_GRACE_PERIOD_SECONDS: int = 90


# Singleton – import this from anywhere.
settings = Settings()  # type: ignore[call-arg]
