"""Meridian — FRC Team Attendance System API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.geofence import GRACE_KEY_PREFIX as GEO_GRACE_PREFIX
from app.api.routers.geofence import router as geofence_router
from app.api.routers.members import router as members_router
from app.api.routers.passes import router as passes_router
from app.api.routers.scanner import router as scanner_router
from app.api.routers.sessions import router as sessions_router
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.rate_limit import limiter
from app.core.redis import redis as redis_client
from app.services.audit import log_event

logger = logging.getLogger("meridian.autotimeout")

AUTOTIMEOUT_INTERVAL = 30  # seconds


async def _auto_timeout_loop():
    """Background loop that closes stale sessions and expired geofence grace periods.
    
    Delegates to the concurrency-safe run_auto_timeout function.
    """
    from app.services.timeout import run_auto_timeout
    
    current_interval = AUTOTIMEOUT_INTERVAL
    while True:
        await asyncio.sleep(current_interval)
        try:
            async with async_session_factory() as db:
                await run_auto_timeout(db, redis_client)
                await db.commit()
            current_interval = AUTOTIMEOUT_INTERVAL  # Reset on success
        except Exception:
            logger.exception("Auto-timeout loop error, retrying in %ds", current_interval)
            current_interval = min(current_interval * 2, 300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup: verify Redis connectivity
    await redis_client.ping()
    task = asyncio.create_task(_auto_timeout_loop())
    yield
    # Shutdown: cancel background task and close Redis
    task.cancel()
    await redis_client.aclose()


app = FastAPI(
    title="Meridian",
    description="FRC Team Attendance Tracking System",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow admin dashboard and PWA origins
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Scanner-Key", "X-Cron-Secret"],
    )


# Routers
app.include_router(auth_router)
app.include_router(members_router)
app.include_router(passes_router)
app.include_router(scanner_router)
app.include_router(geofence_router)
app.include_router(sessions_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meridian"}
