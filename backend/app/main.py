"""Meridian — FRC Team Attendance System API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routers.admin import router as admin_router
from app.api.routers.auth import router as auth_router
from app.api.routers.geofence import router as geofence_router
from app.api.routers.members import router as members_router
from app.api.routers.passes import router as passes_router
from app.api.routers.scanner import router as scanner_router
from app.api.routers.sessions import router as sessions_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.redis import redis as redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    # Startup: verify Redis connectivity
    await redis_client.ping()
    yield
    # Shutdown: close Redis connection pool
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
        allow_methods=["*"],
        allow_headers=["*"],
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
