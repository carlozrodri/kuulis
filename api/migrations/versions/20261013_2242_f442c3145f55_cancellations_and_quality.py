"""cancellations and quality (doc 15): cancellation log, reassignment, quality stats and pauses

Revision ID: f442c3145f55
Revises: 743bb4c0acf6
Create Date: 2026-10-13 22:42:45.889245+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f442c3145f55"
down_revision: Union[str, Sequence[str], None] = "743bb4c0acf6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Created explicitly: several tables share them (ride_status already exists).
QUALITY_ROLE = postgresql.ENUM("driver", "passenger", name="quality_role", create_type=False)
QUALITY_LEVEL = postgresql.ENUM(
    "ok", "warn", "low_priority", "review", name="quality_level", create_type=False
)
PAUSE_REASON = postgresql.ENUM(
    "cancel_burst", "decline_streak", "no_shows", name="pause_reason", create_type=False
)
CANCEL_SIDE = postgresql.ENUM("passenger", "driver", name="cancel_side", create_type=False)
CANCEL_REASON = postgresql.ENUM(
    "driver_late",
        "changed_plans",
        "driver_asked",
        "vehicle_mismatch",
        "wrong_pickup",
        "no_show",
        "wrong_address",
        "no_helmet",
        "vehicle_problem",
        "safety_concern",
        "other",
    name="cancel_reason",
    create_type=False,
)
RIDE_STATUS = postgresql.ENUM(name="ride_status", create_type=False)
NEW_TYPES = (QUALITY_ROLE, QUALITY_LEVEL, PAUSE_REASON, CANCEL_SIDE, CANCEL_REASON)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    for enum_type in NEW_TYPES:
        enum_type.create(bind, checkfirst=True)
    op.create_table(
        "quality_pauses",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", QUALITY_ROLE, nullable=False),
        sa.Column(
            "reason",
            PAUSE_REASON,
            nullable=False,
        ),
        sa.Column("until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lifted_by_id", sa.Uuid(), nullable=True),
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
            ["lifted_by_id"],
            ["users.id"],
            name=op.f("fk_quality_pauses_lifted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_quality_pauses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_pauses")),
    )
    op.create_index(
        "ix_quality_pauses_user_until", "quality_pauses", ["user_id", "until"], unique=False
    )
    op.create_table(
        "quality_stats",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", QUALITY_ROLE, nullable=False),
        sa.Column("offers", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("accepted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rides", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("cancels", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("no_shows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("acceptance_rate", sa.Float(), nullable=True),
        sa.Column("cancel_rate", sa.Float(), nullable=True),
        sa.Column("rating_avg", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "level",
            QUALITY_LEVEL,
            nullable=False,
        ),
        sa.Column(
            "reasons",
            postgresql.ARRAY(sa.String(length=20)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "warned_level",
            QUALITY_LEVEL,
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
            name=op.f("fk_quality_stats_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quality_stats")),
        sa.UniqueConstraint("user_id", "role", name=op.f("uq_quality_stats_user_id")),
    )
    op.create_index("ix_quality_stats_role_level", "quality_stats", ["role", "level"], unique=False)
    op.create_table(
        "ride_cancellations",
        sa.Column("ride_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("passenger_id", sa.Uuid(), nullable=False),
        sa.Column("side", CANCEL_SIDE, nullable=False),
        sa.Column(
            "reason_code",
            CANCEL_REASON,
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "stage",
            RIDE_STATUS,
            nullable=False,
        ),
        sa.Column("counted", sa.Boolean(), nullable=False),
        sa.Column("reassigned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            ["passenger_id"],
            ["users.id"],
            name=op.f("fk_ride_cancellations_passenger_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ride_id"],
            ["rides.id"],
            name=op.f("fk_ride_cancellations_ride_id_rides"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ride_cancellations_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ride_cancellations")),
    )
    op.create_index(
        "ix_ride_cancellations_passenger_reason",
        "ride_cancellations",
        ["passenger_id", "reason_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ride_cancellations_ride_id"), "ride_cancellations", ["ride_id"], unique=False
    )
    op.create_index(
        "ix_ride_cancellations_user_created",
        "ride_cancellations",
        ["user_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "rides",
        sa.Column(
            "cancel_reason_code",
            CANCEL_REASON,
            nullable=True,
        ),
    )
    op.add_column(
        "rides",
        sa.Column("reassign_count", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("rides", sa.Column("reassigned_from_driver_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_rides_reassigned_from_driver_id_users"),
        "rides",
        "users",
        ["reassigned_from_driver_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_rides_reassigned_from_driver_id_users"), "rides", type_="foreignkey"
    )
    op.drop_column("rides", "reassigned_from_driver_id")
    op.drop_column("rides", "reassign_count")
    op.drop_column("rides", "cancel_reason_code")
    op.drop_index("ix_ride_cancellations_user_created", table_name="ride_cancellations")
    op.drop_index(op.f("ix_ride_cancellations_ride_id"), table_name="ride_cancellations")
    op.drop_index("ix_ride_cancellations_passenger_reason", table_name="ride_cancellations")
    op.drop_table("ride_cancellations")
    op.drop_index("ix_quality_stats_role_level", table_name="quality_stats")
    op.drop_table("quality_stats")
    op.drop_index("ix_quality_pauses_user_until", table_name="quality_pauses")
    op.drop_table("quality_pauses")
    bind = op.get_bind()
    for enum_type in NEW_TYPES:
        enum_type.drop(bind, checkfirst=True)
