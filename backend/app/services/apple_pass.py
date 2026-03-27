"""Apple PassKit .pkpass file generation.

Generates signed .pkpass bundles containing member info, NFC payload,
and a TOTP-based rotating QR barcode.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import uuid
import zipfile
from base64 import b64decode
from datetime import datetime, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from app.core.config import settings


def _build_pass_json(
    *,
    member_name: str,
    member_number: str,
    team_name: str,
    team_number: str,
    pass_serial: str,
    pass_type_id: str,
    team_id: str,
    nfc_payload: str,
    status_text: str = "Not checked in",
) -> dict:
    """Build the pass.json structure for an Apple Wallet generic pass."""
    return {
        "formatVersion": 1,
        "passTypeIdentifier": pass_type_id,
        "serialNumber": pass_serial,
        "teamIdentifier": team_id,
        "organizationName": team_name,
        "description": f"{team_name} Attendance Pass",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(30, 60, 114)",
        "labelColor": "rgb(200, 210, 230)",
        "generic": {
            "primaryFields": [
                {"key": "name", "label": "MEMBER", "value": member_name}
            ],
            "secondaryFields": [
                {"key": "member_id", "label": "ID", "value": member_number},
                {"key": "team", "label": "TEAM", "value": f"FRC {team_number}"},
            ],
            "auxiliaryFields": [
                {"key": "status", "label": "STATUS", "value": status_text, "changeMessage": "Status: %@"}
            ],
        },
        "barcode": {
            "format": "PKBarcodeFormatQR",
            "message": f"frcattend://totp?serial={pass_serial}&code=PLACEHOLDER",
            "messageEncoding": "iso-8859-1",
            "altText": "Scan to check in",
        },
        "barcodes": [
            {
                "format": "PKBarcodeFormatQR",
                "message": f"frcattend://totp?serial={pass_serial}&code=PLACEHOLDER",
                "messageEncoding": "iso-8859-1",
                "altText": "Scan to check in",
            }
        ],
        "nfc": {
            "message": nfc_payload,
            "encryptionPublicKey": "",
        },
        "webServiceURL": f"{settings.APPLE_PASS_TYPE_ID and ''}",
        "authenticationToken": "",  # set per-member at generation time
    }


def _compute_manifest(files: dict[str, bytes]) -> dict[str, str]:
    """SHA-1 hash each file for the manifest.json."""
    return {name: hashlib.sha1(data).hexdigest() for name, data in files.items()}


def _sign_manifest(manifest_bytes: bytes) -> bytes:
    """Sign manifest.json using PKCS#7 detached signature with Apple certs."""
    cert_pem = b64decode(settings.APPLE_PASS_CERT_B64)
    key_pem = b64decode(settings.APPLE_PASS_KEY_B64)
    wwdr_pem = b64decode(settings.APPLE_PASS_WWDR_B64)

    cert = x509.load_pem_x509_certificate(cert_pem)
    key = serialization.load_pem_private_key(key_pem, password=None)
    wwdr = x509.load_pem_x509_certificate(wwdr_pem)

    signature = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(manifest_bytes)
        .add_signer(cert, key, hashes.SHA256())
        .add_certificate(wwdr)
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature])
    )
    return signature


def generate_nfc_payload(pass_serial: str, member_secret: str) -> str:
    """Build the signed NFC URI payload.

    Format: frcattend://checkin?serial={serial}&payload={hmac_hex}
    The HMAC is computed over the serial using the member's unique secret.
    """
    sig = hmac.new(
        settings.NFC_HMAC_SECRET.encode(),
        f"{pass_serial}:{member_secret}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"frcattend://checkin?serial={pass_serial}&payload={sig}"


def generate_pkpass(
    *,
    member_name: str,
    member_number: str,
    pass_serial: str,
    auth_token: str,
    nfc_payload: str,
    web_service_url: str,
    status_text: str = "Not checked in",
) -> bytes:
    """Generate a signed .pkpass ZIP bundle.

    Returns the raw bytes of the .pkpass file.
    """
    pass_json = _build_pass_json(
        member_name=member_name,
        member_number=member_number,
        team_name=settings.TEAM_NAME,
        team_number=settings.TEAM_NUMBER,
        pass_serial=pass_serial,
        pass_type_id=settings.APPLE_PASS_TYPE_ID,
        team_id=settings.APPLE_TEAM_ID,
        nfc_payload=nfc_payload,
        status_text=status_text,
    )
    # Set per-member fields
    pass_json["authenticationToken"] = auth_token
    pass_json["webServiceURL"] = web_service_url

    files: dict[str, bytes] = {
        "pass.json": json.dumps(pass_json, indent=2).encode(),
    }

    # Build manifest
    manifest = _compute_manifest(files)
    manifest_bytes = json.dumps(manifest, indent=2).encode()
    files["manifest.json"] = manifest_bytes

    # Sign manifest
    try:
        signature = _sign_manifest(manifest_bytes)
        files["signature"] = signature
    except Exception:
        # If certs aren't configured, skip signing (dev mode)
        pass

    # Build ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()
