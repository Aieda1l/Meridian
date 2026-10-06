"""Make the partial open-session index unique.

Revision ID: 006_unique_open_session
Revises: 005_device_fp
Create Date: 2026-10-06
"""

from alembic import op
import sqlalchemy as sa

revision = "006_unique_open_session"
down_revision = "005_device_fp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_sessions_open_member", table_name="sessions")
    op.create_index(
        "ix_sessions_open_member",
        "sessions",
        ["member_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_open_member", table_name="sessions")
    op.create_index(
        "ix_sessions_open_member",
        "sessions",
        ["member_id"],
        unique=False,
        postgresql_where=sa.text("status = 'open'"),
    )
