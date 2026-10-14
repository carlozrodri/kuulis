"""payments hardening (doc 17): receipts, monthly closings, fee reductions, top-up disputes

Revision ID: 9200ea8145ce
Revises: ba5c54859172
Create Date: 2026-10-14 12:03:33.231442+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9200ea8145ce"
down_revision: Union[str, Sequence[str], None] = "ba5c54859172"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE report_category ADD VALUE IF NOT EXISTS 'payment'")
    op.execute("CREATE SEQUENCE IF NOT EXISTS wallet_receipt_number_seq")
    op.create_table(
        "monthly_closings",
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("totals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("closed_by_id", sa.Uuid(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("binance_statement_key", sa.String(length=512), nullable=True),
        sa.Column("statement_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("differences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled_by_id", sa.Uuid(), nullable=True),
        sa.Column("reconcile_note", sa.String(length=500), nullable=True),
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
            ["closed_by_id"],
            ["users.id"],
            name=op.f("fk_monthly_closings_closed_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reconciled_by_id"],
            ["users.id"],
            name=op.f("fk_monthly_closings_reconciled_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monthly_closings")),
        sa.UniqueConstraint("month", name=op.f("uq_monthly_closings_month")),
    )
    op.create_table(
        "wallet_receipts",
        sa.Column(
            "number",
            sa.BigInteger(),
            server_default=sa.text("nextval('wallet_receipt_number_seq')"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entry_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind", sa.Enum("top_up", "subscription_fee", name="receipt_kind"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("balance_after", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("concept", sa.String(length=200), nullable=False),
        sa.Column("reference", sa.String(length=64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
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
            ["entry_id"],
            ["wallet_entries.id"],
            name=op.f("fk_wallet_receipts_entry_id_wallet_entries"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_wallet_receipts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_receipts")),
        sa.UniqueConstraint("entry_id", name=op.f("uq_wallet_receipts_entry_id")),
        sa.UniqueConstraint("number", name=op.f("uq_wallet_receipts_number")),
    )
    op.create_index(
        op.f("ix_wallet_receipts_user_id"), "wallet_receipts", ["user_id"], unique=False
    )
    op.add_column(
        "subscription_charges",
        sa.Column("original_fee", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("wallet_top_ups", sa.Column("dispute_report_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_wallet_top_ups_dispute_report_id_reports"),
        "wallet_top_ups",
        "reports",
        ["dispute_report_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Finanzas closes months and uploads the Binance statement.
    op.execute(
        "UPDATE staff_roles SET permissions = array_append(permissions, 'finance.close') "
        "WHERE name = 'finanzas' AND NOT ('finance.close' = ANY(permissions))"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_wallet_top_ups_dispute_report_id_reports"), "wallet_top_ups", type_="foreignkey"
    )
    op.drop_column("wallet_top_ups", "dispute_report_id")
    op.drop_column("subscription_charges", "original_fee")
    op.drop_index(op.f("ix_wallet_receipts_user_id"), table_name="wallet_receipts")
    op.drop_table("wallet_receipts")
    op.drop_table("monthly_closings")
    op.execute("DROP SEQUENCE IF EXISTS wallet_receipt_number_seq")
    op.execute("DROP TYPE IF EXISTS receipt_kind")
    op.execute("UPDATE staff_roles SET permissions = array_remove(permissions, 'finance.close')")
