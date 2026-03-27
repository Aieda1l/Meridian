"""Initial schema - all tables, pgcrypto extension, enums.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto extension for encryption and uuid_generate_v4()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create enum types
    member_role = postgresql.ENUM("student", "mentor", "admin", name="member_role", create_type=False)
    device_platform = postgresql.ENUM("ios", "android", "none", name="device_platform", create_type=False)
    check_in_method = postgresql.ENUM("nfc", "qr", name="check_in_method", create_type=False)
    check_out_method = postgresql.ENUM(
        "nfc", "qr", "geofence", "auto_timeout", "self_report", "admin",
        name="check_out_method", create_type=False,
    )
    session_status = postgresql.ENUM("open", "closed", "flagged", "approved", name="session_status", create_type=False)
    warning_type = postgresql.ENUM(
        "daily_80pct", "daily_cap", "weekly_80pct", "weekly_cap", "season_80pct", "season_cap",
        name="warning_type", create_type=False,
    )

    member_role.create(op.get_bind(), checkfirst=True)
    device_platform.create(op.get_bind(), checkfirst=True)
    check_in_method.create(op.get_bind(), checkfirst=True)
    check_out_method.create(op.get_bind(), checkfirst=True)
    session_status.create(op.get_bind(), checkfirst=True)
    warning_type.create(op.get_bind(), checkfirst=True)

    # --- seasons ---
    op.create_table(
        "seasons",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("daily_hour_cap", sa.Numeric(4, 2), nullable=False, server_default="12.00"),
        sa.Column("weekly_hour_cap", sa.Numeric(4, 2), nullable=False, server_default="60.00"),
        sa.Column("season_hour_cap", sa.Numeric(6, 2), nullable=False, server_default="500.00"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial unique index: only one active season at a time
    op.create_index(
        "ix_seasons_unique_active",
        "seasons",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # --- members ---
    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("member_number", sa.String(12), nullable=False),
        sa.Column("name_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("email_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("phone_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("role", member_role, nullable=False),
        sa.Column("password_hashed", sa.String(), nullable=False),
        sa.Column("totp_secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("pass_serial", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pass_auth_token_hashed", sa.String(), nullable=True),
        sa.Column("device_push_token", sa.String(), nullable=True),
        sa.Column("device_platform", device_platform, nullable=False, server_default="none"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seasons.id"), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("member_number"),
        sa.UniqueConstraint("pass_serial"),
    )
    op.create_index("ix_members_member_number", "members", ["member_number"])
    op.create_index("ix_members_season_id", "members", ["season_id"])
    op.create_index("ix_members_role", "members", ["role"])
    op.create_index("ix_members_is_active", "members", ["is_active"])

    # --- scanners ---
    op.create_table(
        "scanners",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("api_key_hashed", sa.String(), nullable=False),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("offline_cache_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("scanner_id", sa.String(), sa.ForeignKey("scanners.id"), nullable=True),
        sa.Column("check_in_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("check_out_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("check_in_method", check_in_method, nullable=False),
        sa.Column("check_out_method", check_out_method, nullable=True),
        sa.Column("selfie_url", sa.String(), nullable=True),
        sa.Column("status", session_status, nullable=False),
        sa.Column("flag_reason", sa.String(), nullable=True),
        sa.Column("self_report_checkout_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("geofence_exit_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sessions_member_id", "sessions", ["member_id"])
    op.create_index("ix_sessions_season_id", "sessions", ["season_id"])
    op.create_index("ix_sessions_status", "sessions", ["status"])
    op.create_index("ix_sessions_member_season", "sessions", ["member_id", "season_id"])
    op.create_index("ix_sessions_check_in_at", "sessions", ["check_in_at"])
    op.create_index(
        "ix_sessions_open_member",
        "sessions",
        ["member_id"],
        postgresql_where=sa.text("status = 'open'"),
    )

    # --- hour_warnings ---
    op.create_table(
        "hour_warnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("season_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seasons.id"), nullable=False),
        sa.Column("warning_type", warning_type, nullable=False),
        sa.Column("triggered_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hour_warnings_member_id", "hour_warnings", ["member_id"])
    op.create_index("ix_hour_warnings_season_id", "hour_warnings", ["season_id"])

    # --- admin_events (audit log — never delete rows) ---
    op.create_table(
        "admin_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_events_actor_id", "admin_events", ["actor_id"])
    op.create_index("ix_admin_events_event_type", "admin_events", ["event_type"])
    op.create_index("ix_admin_events_target_id", "admin_events", ["target_id"])
    op.create_index("ix_admin_events_created_at", "admin_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("admin_events")
    op.drop_table("hour_warnings")
    op.drop_table("sessions")
    op.drop_table("scanners")
    op.drop_table("members")
    op.drop_table("seasons")

    # Drop enum types
    for name in ("warning_type", "session_status", "check_out_method", "check_in_method", "device_platform", "member_role"):
        op.execute(f"DROP TYPE IF EXISTS {name}")

    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
