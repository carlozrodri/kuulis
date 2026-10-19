"""marketing production plantilla

Revision ID: a3f1c9e2b7d4
Revises: 07b842dcf508
Create Date: 2026-10-19 20:20:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a3f1c9e2b7d4"
down_revision: Union[str, Sequence[str], None] = "07b842dcf508"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen marketing_contents.production so it fits "plantilla"."""
    op.alter_column(
        "marketing_contents",
        "production",
        existing_type=sa.String(length=8),
        type_=sa.String(length=16),
        existing_nullable=False,
        existing_server_default="ia",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE marketing_contents SET production = 'ia' WHERE production = 'plantilla'")
    op.alter_column(
        "marketing_contents",
        "production",
        existing_type=sa.String(length=16),
        type_=sa.String(length=8),
        existing_nullable=False,
        existing_server_default="ia",
    )
