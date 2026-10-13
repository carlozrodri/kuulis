"""driver verification (doc 12)

Revision ID: b182bd1900ef
Revises: 70226fd29f1f
Create Date: 2026-10-13 17:26:14.688640+00:00

"""

import hashlib
import hmac
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from kuulis.settings import settings

# revision identifiers, used by Alembic.
revision: str = "b182bd1900ef"
down_revision: Union[str, Sequence[str], None] = "70226fd29f1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VEHICLE_STATUS = postgresql.ENUM("active", "pending", "retired", name="vehicle_status")


def _mark_hash(kind: str, value: str) -> str:
    """Same as apps.drivers.verification.mark_hash (copied: a migration must not change later)."""
    key = hashlib.sha256(b"kuulis:identity-marks:" + settings.SECRET_KEY.encode()).digest()
    normalized = "".join(value.split()).upper()
    return hmac.new(key, f"{kind}:{normalized}".encode(), hashlib.sha256).hexdigest()


def _backfill_marks() -> None:
    """Marks for the drivers and Binance Pay IDs that exist today, so duplicates show at once."""
    bind = op.get_bind()
    rows: list[tuple[uuid.UUID, str, str]] = []
    for user_id, national_id, rif, phone in bind.execute(
        sa.text("SELECT user_id, national_id, rif, phone FROM driver_profiles")
    ):
        if not national_id.startswith("DEL"):  # erased accounts
            rows += [(user_id, "national_id", national_id), (user_id, "rif", rif)]
        rows.append((user_id, "phone", phone))
    rows += [
        (user_id, "plate", plate)
        for user_id, plate in bind.execute(
            sa.text(
                "SELECT p.user_id, v.plate FROM vehicles v "
                "JOIN driver_profiles p ON p.id = v.driver_id"
            )
        )
    ]
    rows += [
        (user_id, "binance_pay_id", pay_id)
        for user_id, pay_id in bind.execute(
            sa.text("SELECT user_id, binance_pay_id FROM wallets WHERE binance_pay_id IS NOT NULL")
        )
    ]
    values = {
        (user_id, kind, _mark_hash(kind, value))
        for user_id, kind, value in rows
        if value and value.strip()
    }
    if values:
        bind.execute(
            sa.text(
                "INSERT INTO identity_marks (id, user_id, kind, value_hash) "
                "VALUES (:id, :user_id, CAST(:kind AS identity_mark_kind), :value_hash) "
                "ON CONFLICT DO NOTHING"
            ),
            [
                {"id": uuid.uuid4(), "user_id": u, "kind": k, "value_hash": h}
                for u, k, h in values
            ],
        )


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres needs the new value committed before it is used; nothing below uses it.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE driver_document_kind ADD VALUE IF NOT EXISTS 'criminal_record'")
    VEHICLE_STATUS.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "identity_marks",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "national_id",
                "rif",
                "plate",
                "phone",
                "binance_pay_id",
                "device",
                name="identity_mark_kind",
            ),
            nullable=False,
        ),
        sa.Column("value_hash", sa.String(length=64), nullable=False),
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
            name=op.f("fk_identity_marks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_identity_marks")),
        sa.UniqueConstraint("user_id", "kind", "value_hash", name="uq_identity_marks_user_value"),
    )
    op.create_index(
        "ix_identity_marks_kind_hash", "identity_marks", ["kind", "value_hash"], unique=False
    )
    op.create_table(
        "driver_checks",
        sa.Column("driver_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "selfie",
                "reverification",
                "document_renewal",
                "vehicle_change",
                name="driver_check_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "requested",
                "pending",
                "approved",
                "rejected",
                "cancelled",
                name="driver_check_status",
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=True),
        sa.Column("vehicle_id", sa.Uuid(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_reason", sa.Text(), nullable=True),
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
            ["assigned_to_id"],
            ["users.id"],
            name=op.f("fk_driver_checks_assigned_to_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["driver_documents.id"],
            name=op.f("fk_driver_checks_document_id_driver_documents"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["driver_profiles.id"],
            name=op.f("fk_driver_checks_driver_id_driver_profiles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name=op.f("fk_driver_checks_reviewed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name=op.f("fk_driver_checks_vehicle_id_vehicles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_driver_checks")),
    )
    op.create_index(
        op.f("ix_driver_checks_driver_id"), "driver_checks", ["driver_id"], unique=False
    )
    op.create_index(
        "ix_driver_checks_status_created", "driver_checks", ["status", "created_at"], unique=False
    )
    op.add_column("driver_documents", sa.Column("expires_on", sa.Date(), nullable=True))
    op.add_column(
        "driver_documents",
        sa.Column(
            "expiry_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.add_column("driver_documents", sa.Column("expiry_notice_days", sa.Integer(), nullable=True))
    op.add_column("driver_documents", sa.Column("superseded_by_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_driver_documents_superseded_by_id_driver_documents"),
        "driver_documents",
        "driver_documents",
        ["superseded_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "driver_profiles", sa.Column("selfie_due_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "driver_profiles",
        sa.Column("induction_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("driver_profiles", sa.Column("induction_by_id", sa.Uuid(), nullable=True))
    op.add_column("driver_profiles", sa.Column("assigned_to_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_driver_profiles_assigned_to_id_users"),
        "driver_profiles",
        "users",
        ["assigned_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_driver_profiles_induction_by_id_users"),
        "driver_profiles",
        "users",
        ["induction_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "vehicles",
        sa.Column(
            "status",
            postgresql.ENUM(name="vehicle_status", create_type=False),
            server_default="active",
            nullable=False,
        ),
    )
    op.drop_constraint(op.f("uq_vehicles_driver_id"), "vehicles", type_="unique")
    op.drop_constraint(op.f("uq_vehicles_plate"), "vehicles", type_="unique")
    op.create_index(op.f("ix_vehicles_driver_id"), "vehicles", ["driver_id"], unique=False)
    op.create_index(
        "uq_vehicles_driver_status",
        "vehicles",
        ["driver_id", "status"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'pending')"),
    )
    op.create_index(
        "uq_vehicles_plate_live",
        "vehicles",
        ["plate"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'pending')"),
    )
    # ### end Alembic commands ###
    _backfill_marks()


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        "uq_vehicles_plate_live",
        table_name="vehicles",
        postgresql_where=sa.text("status IN ('active', 'pending')"),
    )
    op.drop_index(
        "uq_vehicles_driver_status",
        table_name="vehicles",
        postgresql_where=sa.text("status IN ('active', 'pending')"),
    )
    op.drop_index(op.f("ix_vehicles_driver_id"), table_name="vehicles")
    op.create_unique_constraint(
        op.f("uq_vehicles_plate"), "vehicles", ["plate"], postgresql_nulls_not_distinct=False
    )
    op.create_unique_constraint(
        op.f("uq_vehicles_driver_id"),
        "vehicles",
        ["driver_id"],
        postgresql_nulls_not_distinct=False,
    )
    op.execute("DELETE FROM vehicles WHERE status <> 'active'")
    op.drop_column("vehicles", "status")
    op.drop_constraint(
        op.f("fk_driver_profiles_induction_by_id_users"), "driver_profiles", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_driver_profiles_assigned_to_id_users"), "driver_profiles", type_="foreignkey"
    )
    op.drop_column("driver_profiles", "assigned_to_id")
    op.drop_column("driver_profiles", "induction_by_id")
    op.drop_column("driver_profiles", "induction_completed_at")
    op.drop_column("driver_profiles", "selfie_due_at")
    op.drop_constraint(
        op.f("fk_driver_documents_superseded_by_id_driver_documents"),
        "driver_documents",
        type_="foreignkey",
    )
    op.drop_column("driver_documents", "superseded_by_id")
    op.drop_column("driver_documents", "expiry_notice_days")
    op.drop_column("driver_documents", "expiry_confirmed")
    op.drop_column("driver_documents", "expires_on")
    op.drop_index("ix_driver_checks_status_created", table_name="driver_checks")
    op.drop_index(op.f("ix_driver_checks_driver_id"), table_name="driver_checks")
    op.drop_table("driver_checks")
    op.drop_index("ix_identity_marks_kind_hash", table_name="identity_marks")
    op.drop_table("identity_marks")
    # ### end Alembic commands ###
    for name in ("vehicle_status", "driver_check_kind", "driver_check_status", "identity_mark_kind"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
    # 'criminal_record' stays in driver_document_kind: Postgres cannot drop an enum value.
