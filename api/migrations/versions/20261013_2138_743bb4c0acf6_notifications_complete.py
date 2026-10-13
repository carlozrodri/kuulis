"""Notifications (doc 14): categories, preferences, campaigns and phone channels.

Revision ID: 743bb4c0acf6
Revises: 492b5fdff479
Create Date: 2026-10-13 21:38:06.943192+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "743bb4c0acf6"
down_revision: Union[str, Sequence[str], None] = "492b5fdff479"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORY = postgresql.ENUM(
    "transactional", "safety", "support", "marketing", name="notification_category"
)


def upgrade() -> None:
    """Upgrade schema."""
    CATEGORY.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "campaigns",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "pending_approval",
                "scheduled",
                "sending",
                "sent",
                "cancelled",
                name="campaign_status",
            ),
            nullable=False,
        ),
        sa.Column("segment", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("title_es", sa.String(length=120), nullable=False),
        sa.Column("body_es", sa.Text(), nullable=False),
        sa.Column("title_en", sa.String(length=120), nullable=True),
        sa.Column("body_en", sa.Text(), nullable=True),
        sa.Column("deep_link", sa.String(length=300), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_campaigns_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_index(op.f("ix_campaigns_status"), "campaigns", ["status"], unique=False)
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("marketing_push", sa.Boolean(), nullable=False),
        sa.Column("marketing_email", sa.Boolean(), nullable=False),
        sa.Column("quiet_start", sa.String(length=5), nullable=True),
        sa.Column("quiet_end", sa.String(length=5), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
        sa.UniqueConstraint("user_id", name=op.f("uq_notification_preferences_user_id")),
    )
    op.create_table(
        "campaign_recipients",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "skipped", name="campaign_recipient_status"),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("skip_reason", sa.String(length=32), nullable=True),
        sa.Column("notification_id", sa.Uuid(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pushed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("delivered", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("emailed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_campaign_recipients_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"],
            ["notifications.id"],
            name=op.f("fk_campaign_recipients_notification_id_notifications"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_campaign_recipients_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaign_recipients")),
        sa.UniqueConstraint(
            "campaign_id", "user_id", name=op.f("uq_campaign_recipients_campaign_id")
        ),
    )
    op.create_index(
        "ix_campaign_recipients_pending",
        "campaign_recipients",
        ["campaign_id", "status"],
        unique=False,
    )
    op.add_column(
        "devices",
        sa.Column(
            "channels",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column("devices", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "notifications",
        sa.Column(
            "category",
            postgresql.ENUM(name="notification_category", create_type=False),
            server_default="transactional",
            nullable=False,
        ),
    )
    op.add_column("notifications", sa.Column("deep_link", sa.String(length=300), nullable=True))
    op.create_index("ix_notifications_created", "notifications", ["created_at"], unique=False)
    # Existing rows: the category from the payload type; phones count as seen when last updated.
    op.execute(
        "UPDATE notifications SET category = CASE "
        "WHEN data->>'type' = 'safety' THEN 'safety'::notification_category "
        "WHEN data->>'type' IN ('support', 'report', 'lost_item') "
        "THEN 'support'::notification_category "
        "ELSE 'transactional'::notification_category END"
    )
    op.execute("UPDATE devices SET last_seen_at = updated_at WHERE last_seen_at IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_notifications_created", table_name="notifications")
    op.drop_column("notifications", "deep_link")
    op.drop_column("notifications", "category")
    op.drop_column("devices", "last_seen_at")
    op.drop_column("devices", "channels")
    op.drop_index("ix_campaign_recipients_pending", table_name="campaign_recipients")
    op.drop_table("campaign_recipients")
    op.drop_table("notification_preferences")
    op.drop_index(op.f("ix_campaigns_status"), table_name="campaigns")
    op.drop_table("campaigns")
    for name in ("campaign_recipient_status", "campaign_status", "notification_category"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
