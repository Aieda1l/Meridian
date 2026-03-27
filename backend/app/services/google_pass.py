"""Google Wallet pass generation via REST API.

Creates JWT-signed pass objects for Google Wallet using a service account.
"""
from __future__ import annotations

import json
import time
from base64 import b64decode

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from app.core.config import settings

GOOGLE_WALLET_API = "https://walletobjects.googleapis.com/walletobjects/v1"
SCOPES = ["https://www.googleapis.com/auth/wallet_object.issuer"]


def _get_credentials():
    """Load Google service account credentials from env."""
    sa_json = json.loads(b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON_B64))
    return service_account.Credentials.from_service_account_info(sa_json, scopes=SCOPES)


def build_pass_object(
    *,
    issuer_id: str,
    member_name: str,
    member_number: str,
    pass_serial: str,
    team_name: str,
    team_number: str,
    status_text: str = "Not checked in",
) -> dict:
    """Build a Google Wallet Generic Pass object."""
    return {
        "id": f"{issuer_id}.{pass_serial}",
        "classId": f"{issuer_id}.frc_attendance",
        "state": "ACTIVE",
        "header": {
            "defaultValue": {"language": "en", "value": team_name}
        },
        "subheader": {
            "defaultValue": {"language": "en", "value": f"FRC {team_number}"}
        },
        "textModulesData": [
            {"id": "member_name", "header": "MEMBER", "body": member_name},
            {"id": "member_id", "header": "ID", "body": member_number},
            {"id": "status", "header": "STATUS", "body": status_text},
        ],
        "barcode": {
            "type": "QR_CODE",
            "value": f"frcattend://totp?serial={pass_serial}&code=PLACEHOLDER",
            "alternateText": "Scan to check in",
        },
        "heroImage": {
            "sourceUri": {"uri": settings.TEAM_LOGO_URL or "https://via.placeholder.com/1032x336"},
            "contentDescription": {"defaultValue": {"language": "en", "value": "Team Logo"}},
        },
    }


async def create_or_update_pass(
    *,
    issuer_id: str,
    member_name: str,
    member_number: str,
    pass_serial: str,
    team_name: str,
    team_number: str,
    status_text: str = "Not checked in",
) -> dict:
    """Create or update a Google Wallet pass object via REST API.

    Returns the API response dict.
    """
    credentials = _get_credentials()
    credentials.refresh(GoogleAuthRequest())

    pass_object = build_pass_object(
        issuer_id=issuer_id,
        member_name=member_name,
        member_number=member_number,
        pass_serial=pass_serial,
        team_name=team_name,
        team_number=team_number,
        status_text=status_text,
    )

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }

    object_id = f"{issuer_id}.{pass_serial}"

    async with httpx.AsyncClient() as client:
        # Try to update first
        resp = await client.get(
            f"{GOOGLE_WALLET_API}/genericObject/{object_id}",
            headers=headers,
        )
        if resp.status_code == 200:
            resp = await client.put(
                f"{GOOGLE_WALLET_API}/genericObject/{object_id}",
                headers=headers,
                json=pass_object,
            )
        else:
            resp = await client.post(
                f"{GOOGLE_WALLET_API}/genericObject",
                headers=headers,
                json=pass_object,
            )
        resp.raise_for_status()
        return resp.json()


def generate_add_to_wallet_url(issuer_id: str, pass_serial: str) -> str:
    """Generate the 'Add to Google Wallet' JWT link.

    Returns a URL that the member can tap to add the pass.
    """
    import jwt as pyjwt

    credentials = _get_credentials()

    claims = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "origins": [],
        "typ": "savetowallet",
        "payload": {
            "genericObjects": [
                {"id": f"{issuer_id}.{pass_serial}"}
            ]
        },
        "iat": int(time.time()),
    }

    token = pyjwt.encode(claims, credentials._signer.key, algorithm="RS256")
    return f"https://pay.google.com/gp/v/save/{token}"
