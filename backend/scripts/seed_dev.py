#!/usr/bin/env python3
"""Bootstrap a fresh Meridian database with a dev admin, season, and scanner.

Usage:
    cd backend
    python -m scripts.seed_dev          # uses .env in cwd
    python -m scripts.seed_dev --reset  # drops & recreates seed data

Requires: the database to be migrated (alembic upgrade head) and .env loaded.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import date, timedelta

import bcrypt
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# ---------------------------------------------------------------------------
# Ensure the backend package is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")

from app.core.config import settings
from app.models.base import Base
from app.models.member import Member, MemberRole, DevicePlatform
from app.models.scanner import Scanner
from app.models.season import Season

# ---------------------------------------------------------------------------
# Seed data — edit these to taste
# ---------------------------------------------------------------------------

ADMIN_MEMBER_NUMBER = "0001"
ADMIN_NAME = "Dev Admin"
ADMIN_EMAIL = "admin@meridian.local"
ADMIN_PASSWORD = "admin"  # change in production!

SCANNER_ID = "MAIN_ENTRANCE"
SCANNER_NAME = "Main Entrance Scanner"
SCANNER_API_KEY = "12345"  # raw key — will be bcrypt-hashed

SEASON_NAME = "2025-2026 Season"

# A second demo member for testing checkin/checkout flows
DEMO_MEMBER_NUMBER = "0042"
DEMO_NAME = "Demo Student"
DEMO_EMAIL = "demo@meridian.local"
DEMO_PASSWORD = "demo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def _pgp_encrypt(db: AsyncSession, plaintext: str) -> bytes:
    result = await db.execute(
        text("SELECT pgp_sym_encrypt(:data, :key)"),
        {"data": plaintext, "key": settings.PGP_SYM_KEY},
    )
    return result.scalar_one()


async def _pgp_encrypt_totp(db: AsyncSession, secret: str) -> bytes:
    """Encrypt a TOTP secret the same way the app stores it."""
    return await _pgp_encrypt(db, secret)


# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------

async def seed(reset: bool = False) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        if reset:
            print("Resetting seed data …")
            await db.execute(delete(Scanner).where(Scanner.id == SCANNER_ID))
            await db.execute(delete(Member).where(Member.member_number == ADMIN_MEMBER_NUMBER))
            await db.execute(delete(Member).where(Member.member_number == DEMO_MEMBER_NUMBER))
            # Only delete the season we created (by name) to avoid nuking user data
            await db.execute(delete(Season).where(Season.name == SEASON_NAME))
            await db.commit()
            print("  done.")

        # ------ Season ------
        row = (await db.execute(select(Season).where(Season.is_active == True))).scalar_one_or_none()  # noqa: E712
        if row:
            season = row
            print(f"Active season already exists: {season.name!r} (id={season.id})")
        else:
            season = Season(
                name=SEASON_NAME,
                start_date=date.today() - timedelta(days=30),
                end_date=date.today() + timedelta(days=180),
                is_active=True,
            )
            db.add(season)
            await db.flush()
            print(f"Created season: {season.name!r} (id={season.id})")

        # ------ Admin member ------
        exists = (await db.execute(
            select(Member).where(Member.member_number == ADMIN_MEMBER_NUMBER)
        )).scalar_one_or_none()

        if exists:
            print(f"Admin member already exists: #{ADMIN_MEMBER_NUMBER} (id={exists.id})")
        else:
            totp_secret = "JBSWY3DPEHPK3PXP"  # well-known base32 test secret
            admin = Member(
                member_number=ADMIN_MEMBER_NUMBER,
                name_encrypted=await _pgp_encrypt(db, ADMIN_NAME),
                email_encrypted=await _pgp_encrypt(db, ADMIN_EMAIL),
                role=MemberRole.admin,
                password_hashed=_hash(ADMIN_PASSWORD),
                totp_secret_encrypted=await _pgp_encrypt_totp(db, totp_secret),
                pass_serial=uuid.uuid4(),
                is_active=True,
                season_id=season.id,
            )
            db.add(admin)
            await db.flush()
            print(f"Created admin: #{ADMIN_MEMBER_NUMBER} / {ADMIN_EMAIL} / pw={ADMIN_PASSWORD!r}")
            print(f"  TOTP secret (for Authenticator apps): {totp_secret}")
            print(f"  pass_serial: {admin.pass_serial}")

        # ------ Demo student member ------
        exists = (await db.execute(
            select(Member).where(Member.member_number == DEMO_MEMBER_NUMBER)
        )).scalar_one_or_none()

        if exists:
            print(f"Demo member already exists: #{DEMO_MEMBER_NUMBER} (id={exists.id})")
        else:
            demo_totp = "KVKFKRCPNZQUYMLXOVYDSQKGOJRXIMZO"  # another test secret
            demo = Member(
                member_number=DEMO_MEMBER_NUMBER,
                name_encrypted=await _pgp_encrypt(db, DEMO_NAME),
                email_encrypted=await _pgp_encrypt(db, DEMO_EMAIL),
                role=MemberRole.student,
                password_hashed=_hash(DEMO_PASSWORD),
                totp_secret_encrypted=await _pgp_encrypt_totp(db, demo_totp),
                pass_serial=uuid.uuid4(),
                is_active=True,
                season_id=season.id,
            )
            db.add(demo)
            await db.flush()
            print(f"Created demo student: #{DEMO_MEMBER_NUMBER} / {DEMO_EMAIL} / pw={DEMO_PASSWORD!r}")
            print(f"  TOTP secret: {demo_totp}")
            print(f"  pass_serial: {demo.pass_serial}")

        # ------ Scanner ------
        exists = (await db.execute(
            select(Scanner).where(Scanner.id == SCANNER_ID)
        )).scalar_one_or_none()

        if exists:
            print(f"Scanner already exists: {SCANNER_ID!r}")
        else:
            scanner = Scanner(
                id=SCANNER_ID,
                name=SCANNER_NAME,
                api_key_hashed=_hash(SCANNER_API_KEY),
            )
            db.add(scanner)
            await db.flush()
            print(f"Created scanner: {SCANNER_ID!r}  (api_key={SCANNER_API_KEY!r})")

        await db.commit()

    await engine.dispose()
    print("\nSeed complete. You can now log in to the admin panel or test the scanner API.")
    print(f"  Scanner X-Scanner-Key header value: {SCANNER_API_KEY}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Meridian dev database")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate seed data")
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()
