"""denied_status_and_notifications
Revision ID: 004_denied_status_and_notifications
Revises: 003_add_email_hash
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_denied_and_notifs"
down_revision = "003_add_email_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add 'denied' to the session_status enum.
    #    ALTER TYPE ... ADD VALUE cannot run inside a transaction,
    #    so we commit the current transaction first.
    op.execute("COMMIT")
    op.execute("ALTER TYPE session_status ADD VALUE IF NOT EXISTS 'denied'")

    # 2. Create the notifications table (idempotent — check if it already exists)
    conn = op.get_bind()
    table_exists = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications')")
    ).scalar()

    if not table_exists:
        op.create_table(
            "notifications",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("recipient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=False),
            sa.Column("notification_type", sa.String(64), nullable=False),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("related_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("detail", postgresql.JSONB(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.PrimaryKeyConstraint("id"),
        )

    # 3. Create indexes (use IF NOT EXISTS via raw SQL for idempotency)
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_recipient_id ON notifications (recipient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_created_at ON notifications (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_notifications_recipient_unread ON notifications (recipient_id, is_read) WHERE is_read = false")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing values from enums,
    # so we do not attempt to remove 'denied' from session_status.
    op.drop_table("notifications")
