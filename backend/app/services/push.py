"""Push notification service — APNs and FCM.

Sends push notifications to update wallet passes and notify members/admins.
Uses httpx for async HTTP to both Apple and Google services.
"""
from __future__ import annotations

import json
import time
import uuid
from base64 import b64decode

import httpx
import jwt as pyjwt

from app.core.config import settings


# ---------------------------------------------------------------------------
# APNs (Apple Push Notification service)
# ---------------------------------------------------------------------------

_apns_token_cache: dict[str, tuple[str, float]] = {}


def _get_apns_token() -> str:
    """Generate or return a cached APNs JWT token.

    APNs tokens are valid for up to 60 minutes. We cache them for 50 minutes.
    """
    cached = _apns_token_cache.get("token")
    if cached and time.time() - cached[1] < 3000:  # 50 minutes
        return cached[0]

    key_data = b64decode(settings.APNS_KEY_B64)

    now = int(time.time())
    headers = {
        "alg": "ES256",
        "kid": settings.APNS_KEY_ID,
    }
    payload = {
        "iss": settings.APNS_TEAM_ID,
        "iat": now,
    }

    token = pyjwt.encode(payload, key_data, algorithm="ES256", headers=headers)
    _apns_token_cache["token"] = (token, time.time())
    return token


async def send_apns_push(device_token: str, payload: dict | None = None) -> bool:
    """Send a push notification via APNs.

    For wallet pass updates, the payload is empty (just triggers a pass refresh).
    For other notifications, provide a payload dict with 'aps' key.
    """
    if not settings.APNS_KEY_B64:
        return False

    token = _get_apns_token()

    # Use production APNs endpoint
    url = f"https://api.push.apple.com/3/device/{device_token}"

    headers = {
        "authorization": f"bearer {token}",
        "apns-topic": settings.APNS_TOPIC,
        "apns-push-type": "background" if payload is None else "alert",
    }

    body = payload or {"aps": {"content-available": 1}}

    async with httpx.AsyncClient(http2=True) as client:
        try:
            resp = await client.post(url, headers=headers, json=body, timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# FCM (Firebase Cloud Messaging)
# ---------------------------------------------------------------------------

_fcm_token_cache: dict[str, tuple[str, float]] = {}


async def _get_fcm_token() -> str:
    """Get an OAuth2 access token for FCM using the service account."""
    cached = _fcm_token_cache.get("token")
    if cached and time.time() - cached[1] < 3300:  # 55 minutes
        return cached[0]

    sa_json = json.loads(b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON_B64))

    now = int(time.time())
    payload = {
        "iss": sa_json["client_email"],
        "scope": "https://www.googleapis.com/auth/firebase.messaging",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }

    assertion = pyjwt.encode(payload, sa_json["private_key"], algorithm="RS256")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]

    _fcm_token_cache["token"] = (token, time.time())
    return token


async def send_fcm_push(
    device_token: str,
    *,
    title: str | None = None,
    body: str | None = None,
    data: dict[str, str] | None = None,
) -> bool:
    """Send a push notification via FCM v1 API."""
    if not settings.FCM_PROJECT_ID or not settings.GOOGLE_SERVICE_ACCOUNT_JSON_B64:
        return False

    access_token = await _get_fcm_token()

    url = f"https://fcm.googleapis.com/v1/projects/{settings.FCM_PROJECT_ID}/messages:send"

    message: dict = {
        "token": device_token,
    }

    if title or body:
        message["notification"] = {}
        if title:
            message["notification"]["title"] = title
        if body:
            message["notification"]["body"] = body

    if data:
        message["data"] = data

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"message": message},
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# High-level helpers
# ---------------------------------------------------------------------------

async def notify_member_checkin(device_token: str, platform: str, member_name: str, check_in_time: str) -> bool:
    """Send a check-in notification to the member's device."""
    if platform == "ios":
        # For iOS, send an empty push to trigger wallet pass refresh
        return await send_apns_push(device_token)
    elif platform == "android":
        return await send_fcm_push(
            device_token,
            title="Checked In",
            body=f"Checked in at {check_in_time}",
            data={"type": "checkin", "name": member_name},
        )
    return False


async def notify_member_checkout(
    device_token: str, platform: str, member_name: str, duration_text: str
) -> bool:
    """Send a checkout notification to the member's device."""
    if platform == "ios":
        return await send_apns_push(device_token)
    elif platform == "android":
        return await send_fcm_push(
            device_token,
            title="Checked Out",
            body=f"Checked out — {duration_text} logged",
            data={"type": "checkout", "name": member_name},
        )
    return False


async def notify_hour_warning(
    device_token: str, platform: str, message: str
) -> bool:
    """Send an hour cap warning notification."""
    if platform == "ios":
        return await send_apns_push(
            device_token,
            payload={
                "aps": {
                    "alert": {"title": "Hour Limit Warning", "body": message},
                    "sound": "default",
                },
            },
        )
    elif platform == "android":
        return await send_fcm_push(
            device_token,
            title="Hour Limit Warning",
            body=message,
            data={"type": "hour_warning"},
        )
    return False


async def notify_admins_cap_reached(
    admin_tokens: list[tuple[str, str]],  # list of (token, platform)
    member_name: str,
    warning_message: str,
) -> None:
    """Notify all admin members about a cap being reached."""
    for token, platform in admin_tokens:
        if platform == "ios":
            await send_apns_push(
                token,
                payload={
                    "aps": {
                        "alert": {
                            "title": "Hour Cap Reached",
                            "body": f"{member_name}: {warning_message}",
                        },
                        "sound": "default",
                    },
                },
            )
        elif platform == "android":
            await send_fcm_push(
                token,
                title="Hour Cap Reached",
                body=f"{member_name}: {warning_message}",
                data={"type": "admin_cap_alert"},
            )
