"""Helpers for pgcrypto PII encryption/decryption via raw SQL.

These functions execute pgp_sym_encrypt / pgp_sym_decrypt using the
symmetric key from the PGP_SYM_KEY environment variable. They are
designed to be used inside SQLAlchemy async sessions.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings


async def pgp_encrypt(db: AsyncSession, plaintext: str) -> bytes:
    """Encrypt *plaintext* using pgcrypto's pgp_sym_encrypt and return raw bytes."""
    result = await db.execute(
        text("SELECT pgp_sym_encrypt(:data, :key)"),
        {"data": plaintext, "key": settings.PGP_SYM_KEY},
    )
    return result.scalar_one()


async def pgp_decrypt(db: AsyncSession, ciphertext: bytes) -> str:
    """Decrypt *ciphertext* using pgcrypto's pgp_sym_decrypt and return plaintext."""
    result = await db.execute(
        text("SELECT pgp_sym_decrypt(:data, :key)"),
        {"data": ciphertext, "key": settings.PGP_SYM_KEY},
    )
    return result.scalar_one()
