"""Add device_fingerprint column to members for anti-cheat binding.
Revision ID: 005_device_fp
Revises: 004_denied_and_notifs
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa

revision = "005_device_fp"
down_revision = "004_denied_and_notifs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("members", sa.Column("device_fingerprint", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "device_fingerprint")
