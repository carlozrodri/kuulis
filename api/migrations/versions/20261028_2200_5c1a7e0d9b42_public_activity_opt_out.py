"""driver opt-out of the public activity map

Revision ID: 5c1a7e0d9b42
Revises: 928564309a6c
Create Date: 2026-10-28 22:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5c1a7e0d9b42"
down_revision: Union[str, Sequence[str], None] = "928564309a6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "driver_profiles",
        sa.Column(
            "hide_from_public_activity",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("driver_profiles", "hide_from_public_activity")
