"""Add geofence_zones and scanner_geofence_zones tables.

Revision ID: 002_geofence_zones
Revises: 001_initial
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_geofence_zones"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geofence_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("polygon_json", sa.Text(), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="'#3388ff'"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "scanner_geofence_zones",
        sa.Column("scanner_id", sa.String(), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["geofence_zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scanner_id", "zone_id"),
    )


def downgrade() -> None:
    op.drop_table("scanner_geofence_zones")
    op.drop_table("geofence_zones")
