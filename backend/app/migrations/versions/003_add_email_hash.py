"""add_email_hash_column
Revision ID: 003_add_email_hash
Revises: 002_geofence_zones
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import asyncio

revision = "003_add_email_hash"
down_revision = "002_geofence_zones"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add column
    op.add_column("members", sa.Column("email_hash", sa.String(), nullable=True))
    op.create_index(op.f("ix_members_email_hash"), "members", ["email_hash"], unique=False)
    
    # 2. Backfill existing members
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    
    from app.core.config import settings
    from app.core.security import hash_email
    
    # Fetch all members to backfill
    result = session.execute(
        sa.text("SELECT id, email_encrypted FROM members WHERE email_encrypted IS NOT NULL")
    ).fetchall()
    
    for row in result:
        member_id, email_encrypted = row
        # decrypt
        decrypted_result = session.execute(
            sa.text("SELECT pgp_sym_decrypt(:data, :key)"),
            {"data": email_encrypted, "key": settings.PGP_SYM_KEY}
        ).scalar()
        
        if decrypted_result:
            hashed = hash_email(decrypted_result)
            session.execute(
                sa.text("UPDATE members SET email_hash = :hashed WHERE id = :id"),
                {"hashed": hashed, "id": member_id}
            )
            
    session.commit()

def downgrade() -> None:
    op.drop_index(op.f("ix_members_email_hash"), table_name="members")
    op.drop_column("members", "email_hash")
