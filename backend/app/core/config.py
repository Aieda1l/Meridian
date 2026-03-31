"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from typing import Any

from pydantic import field_validator, model_validator
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
    APPLE_PASS_WEB_SERVICE_URL: str = ""

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

    # ── Debug / Development ─────────────────────────────────────────────
    DEBUG_SKIP_SCAN_VALIDATION: bool = False  # skip NFC HMAC + TOTP checks (dev only!)

    # ── CORS ─────────────────────────────────────────────────────────────
    # Stored as a raw string so pydantic-settings doesn't try to JSON-parse
    # the comma-separated value from .env before the validator runs.
    CORS_ORIGINS: str = "http://localhost:3000"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> str:
        if isinstance(v, list):
            return ",".join(v)
        return v

    # ── Team branding (optional) ────────────────────────────────────────
    TEAM_NAME: str = "FRC Team"
    TEAM_NUMBER: str = ""
    TEAM_LOGO_URL: str = ""

    # ── Cron / auto-timeout ─────────────────────────────────────────────
    CRON_SECRET: str = ""

    # ── Geofence ────────────────────────────────────────────────────────
    GEOFENCE_POLYGON: str = ""

    @field_validator("GEOFENCE_POLYGON", mode="before")
    @classmethod
    def _parse_geofence_polygon(cls, v: Any) -> str:
        if isinstance(v, list):
            return json.dumps(v)
        return v

    GEOFENCE_BUFFER_METERS: int = 150
    GEOFENCE_GRACE_PERIOD_SECONDS: int = 90

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS as a list of strings."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def geofence_polygon_list(self) -> list[dict[str, float]]:
        """GEOFENCE_POLYGON as a parsed list of {lat, lng} dicts."""
        if not self.GEOFENCE_POLYGON.strip():
            return []
        return json.loads(self.GEOFENCE_POLYGON)

    @field_validator("PGP_SYM_KEY", "JWT_SECRET", "NFC_HMAC_SECRET", "CRON_SECRET", "SCANNER_API_KEY", mode="after")
    @classmethod
    def _check_not_empty(cls, v: str, info) -> str:
        if not v:
            raise ValueError(f"{info.field_name} must be set and non-empty")
        return v

    @model_validator(mode="after")
    def _block_debug_skip_in_production(self) -> "Settings":
        """Prevent DEBUG_SKIP_SCAN_VALIDATION from being enabled in production.

        Production is detected by the DATABASE_URL not pointing to localhost.
        """
        if self.DEBUG_SKIP_SCAN_VALIDATION:
            db = self.DATABASE_URL
            if "localhost" not in db and "127.0.0.1" not in db:
                raise ValueError(
                    "DEBUG_SKIP_SCAN_VALIDATION must not be enabled in production "
                    "(DATABASE_URL does not point to localhost)"
                )
        return self


# Singleton – import this from anywhere.
settings = Settings()  # type: ignore[call-arg]
