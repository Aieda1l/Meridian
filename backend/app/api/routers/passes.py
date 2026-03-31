"""Passes router — Apple PassKit web service protocol, Android, and download.

Apple endpoints follow the protocol spec exactly:
- POST   /passes/register/{deviceId}/{passTypeId}/{serialNumber} — device registration
- DELETE /passes/register/{deviceId}/{passTypeId}/{serialNumber} — device unregistration
- GET    /passes/latest/{passTypeId}/{serialNumber} — pass update fetch
- GET    /passes/devices/{deviceId}/registrations/{passTypeId} — list updated passes
- POST   /passes/log — error logging
- POST   /passes/android/register — Google Wallet device registration
- GET    /passes/download/{memberId} — authenticated download of .pkpass or add-to-wallet link
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.encryption import pgp_decrypt
from app.core.security import get_current_member
from app.models.member import DevicePlatform, Member
from app.services.apple_pass import generate_nfc_payload, generate_pkpass
from app.services.audit import log_event
from app.services.google_pass import create_or_update_pass, generate_add_to_wallet_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/passes", tags=["passes"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class DeviceRegistrationBody(BaseModel):
    pushToken: str


class AndroidRegisterBody(BaseModel):
    member_id: uuid.UUID
    push_token: str


class SerialListResponse(BaseModel):
    serialNumbers: list[str]
    lastUpdated: str


class AppleLogBody(BaseModel):
    logs: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_member_by_serial(
    db: AsyncSession, serial_number: str
) -> Member | None:
    """Look up a member by their pass_serial UUID string."""
    try:
        serial_uuid = uuid.UUID(serial_number)
    except ValueError:
        return None
    result = await db.execute(
        select(Member).where(Member.pass_serial == serial_uuid, Member.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


def _verify_apple_auth(request: Request, member: Member) -> None:
    """Validate the ApplePass authorization header against the stored bcrypt hash.

    Raises HTTPException 401 on failure.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("ApplePass "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing ApplePass authorization",
        )
    token = auth_header[len("ApplePass "):]

    if not member.pass_auth_token_hashed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pass has no auth token configured",
        )

    if not bcrypt.checkpw(token.encode(), member.pass_auth_token_hashed.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid pass auth token",
        )


async def _generate_pkpass_for_member(
    db: AsyncSession, member: Member, *, status_text: str = "Not checked in"
) -> bytes:
    """Build a .pkpass file for the given member, decrypting PII as needed."""
    name = await pgp_decrypt(db, member.name_encrypted) if member.name_encrypted else ""
    serial_str = str(member.pass_serial)

    # Decrypt TOTP secret to derive NFC payload
    totp_secret = ""
    if member.totp_secret_encrypted:
        totp_secret = await pgp_decrypt(db, member.totp_secret_encrypted)

    nfc_payload = generate_nfc_payload(serial_str, totp_secret)

    web_service_url = settings.APPLE_PASS_WEB_SERVICE_URL

    return generate_pkpass(
        member_name=name,
        member_number=member.member_number,
        pass_serial=serial_str,
        auth_token="",  # raw token not stored; placeholder for bundle
        nfc_payload=nfc_payload,
        web_service_url=web_service_url,
        status_text=status_text,
    )


# ---------------------------------------------------------------------------
# Apple PassKit web service: device registration
# ---------------------------------------------------------------------------

@router.post(
    "/register/{device_id}/{pass_type_id}/{serial_number}",
    status_code=status.HTTP_201_CREATED,
)
async def apple_register_device(
    device_id: str,
    pass_type_id: str,
    serial_number: str,
    body: DeviceRegistrationBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a device to receive push updates for a pass."""
    member = await _get_member_by_serial(db, serial_number)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found")

    _verify_apple_auth(request, member)

    # Check for device binding conflict
    if (
        member.device_push_token is not None
        and member.device_push_token != body.pushToken
    ):
        await log_event(
            db,
            event_type="device_binding_conflict",
            target_id=member.id,
            detail={
                "device_id": device_id,
                "existing_token": member.device_push_token[:8] + "...",
                "new_token": body.pushToken[:8] + "...",
            },
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pass is already bound to a different device",
        )

    # Bind the device
    member.device_push_token = body.pushToken
    member.device_platform = DevicePlatform.ios
    await db.flush()

    await log_event(
        db,
        event_type="apple_device_registered",
        target_id=member.id,
        detail={"device_id": device_id, "pass_type_id": pass_type_id},
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Apple PassKit web service: device unregistration
# ---------------------------------------------------------------------------

@router.delete(
    "/register/{device_id}/{pass_type_id}/{serial_number}",
    status_code=status.HTTP_200_OK,
)
async def apple_unregister_device(
    device_id: str,
    pass_type_id: str,
    serial_number: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Unregister a device from push updates for a pass."""
    member = await _get_member_by_serial(db, serial_number)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found")

    _verify_apple_auth(request, member)

    member.device_push_token = None
    await db.flush()

    await log_event(
        db,
        event_type="apple_device_unregistered",
        target_id=member.id,
        detail={"device_id": device_id, "pass_type_id": pass_type_id},
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Apple PassKit web service: fetch latest pass
# ---------------------------------------------------------------------------

@router.get("/latest/{pass_type_id}/{serial_number}")
async def apple_get_latest_pass(
    pass_type_id: str,
    serial_number: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Return the latest .pkpass file for the given serial.

    Supports If-Modified-Since header; returns 304 if unchanged.
    """
    member = await _get_member_by_serial(db, serial_number)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pass not found")

    _verify_apple_auth(request, member)

    # Check If-Modified-Since
    if_modified_since = request.headers.get("If-Modified-Since")
    if if_modified_since and member.updated_at:
        try:
            client_date = datetime.strptime(if_modified_since, "%a, %d %b %Y %H:%M:%S %Z").replace(
                tzinfo=timezone.utc
            )
            if member.updated_at <= client_date:
                return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        except ValueError:
            pass  # Ignore malformed date headers

    pkpass_bytes = await _generate_pkpass_for_member(db, member)

    return Response(
        content=pkpass_bytes,
        media_type="application/vnd.apple.pkpass",
        headers={
            "Content-Disposition": f'attachment; filename="{serial_number}.pkpass"',
            "Last-Modified": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        },
    )


# ---------------------------------------------------------------------------
# Apple PassKit web service: list updated passes for a device
# ---------------------------------------------------------------------------

@router.get("/devices/{device_id}/registrations/{pass_type_id}")
async def apple_list_updated_passes(
    device_id: str,
    pass_type_id: str,
    passesUpdatedSince: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Return serial numbers of passes updated since the given tag.

    The ``passesUpdatedSince`` query param is an opaque tag (ISO timestamp).
    """
    query = select(Member).where(
        Member.device_push_token.is_not(None),
        Member.device_platform == DevicePlatform.ios,
        Member.is_active == True,  # noqa: E712
        Member.pass_serial.is_not(None),
    )

    if passesUpdatedSince:
        try:
            since = datetime.fromisoformat(passesUpdatedSince)
            query = query.where(Member.updated_at > since)
        except ValueError:
            pass  # Ignore malformed timestamps

    result = await db.execute(query)
    members = result.scalars().all()

    if not members:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    serials = [str(m.pass_serial) for m in members]
    last_updated = max(m.updated_at for m in members if m.updated_at)

    return SerialListResponse(
        serialNumbers=serials,
        lastUpdated=last_updated.isoformat() if last_updated else datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Apple PassKit web service: error log
# ---------------------------------------------------------------------------

@router.post("/log", status_code=status.HTTP_200_OK)
async def apple_log_errors(
    body: AppleLogBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive error logs from Apple PassKit and persist to audit trail."""
    for entry in body.logs:
        logger.warning("Apple PassKit log: %s", entry)

    await log_event(
        db,
        event_type="apple_passkit_error",
        detail={"logs": body.logs},
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Android device registration
# ---------------------------------------------------------------------------

@router.post("/android/register", status_code=status.HTTP_201_CREATED)
async def android_register_device(
    body: AndroidRegisterBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Register an Android device for push notifications."""
    if current_member.id != body.member_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only register your own device"
        )
    result = await db.execute(
        select(Member).where(Member.id == body.member_id, Member.is_active == True)  # noqa: E712
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Check for device binding conflict
    if (
        member.device_push_token is not None
        and member.device_push_token != body.push_token
    ):
        await log_event(
            db,
            event_type="device_binding_conflict",
            target_id=member.id,
            detail={
                "platform": "android",
                "existing_token": member.device_push_token[:8] + "...",
                "new_token": body.push_token[:8] + "...",
            },
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member is already bound to a different device",
        )

    member.device_push_token = body.push_token
    member.device_platform = DevicePlatform.android
    await db.flush()

    await log_event(
        db,
        event_type="android_device_registered",
        target_id=member.id,
        detail={"member_id": str(body.member_id)},
        ip_address=request.client.host if request.client else None,
    )

    return Response(status_code=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Authenticated pass download (member JWT)
# ---------------------------------------------------------------------------

@router.get("/download/{member_id}")
async def download_pass(
    member_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Download a .pkpass (iOS) or get an add-to-wallet URL (Android).

    Requires member JWT. Members can only download their own pass.
    """
    if current.id != member_id and current.role.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only download your own pass",
        )

    result = await db.execute(
        select(Member).where(Member.id == member_id, Member.is_active == True)  # noqa: E712
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if not member.pass_serial:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member does not have a pass provisioned",
        )

    # Determine platform from User-Agent or existing binding
    user_agent = (request.headers.get("User-Agent") or "").lower()
    is_android = "android" in user_agent or member.device_platform == DevicePlatform.android

    if is_android:
        # Google Wallet flow
        serial_str = str(member.pass_serial)
        name = await pgp_decrypt(db, member.name_encrypted) if member.name_encrypted else ""

        # Ensure the pass object exists in Google Wallet
        await create_or_update_pass(
            issuer_id=settings.GOOGLE_WALLET_ISSUER_ID,  # issuer from settings
            member_name=name,
            member_number=member.member_number,
            pass_serial=serial_str,
            team_name=settings.TEAM_NAME,
            team_number=settings.TEAM_NUMBER,
        )

        wallet_url = generate_add_to_wallet_url(
            issuer_id=settings.GOOGLE_WALLET_ISSUER_ID,
            pass_serial=serial_str,
        )
        return {"platform": "android", "add_to_wallet_url": wallet_url}
    else:
        # Apple Wallet flow
        pkpass_bytes = await _generate_pkpass_for_member(db, member)

        return Response(
            content=pkpass_bytes,
            media_type="application/vnd.apple.pkpass",
            headers={
                "Content-Disposition": f'attachment; filename="{member.pass_serial}.pkpass"',
            },
        )
