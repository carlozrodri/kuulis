"""rider improvements (doc 23): ride for someone else and note for the driver, live link for the
person riding, icon of saved places

Revision ID: 5c1e7a2d9b40
Revises: 26634e27a681
Create Date: 2026-10-17 11:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5c1e7a2d9b40"
down_revision: Union[str, Sequence[str], None] = "26634e27a681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("rides", sa.Column("rider_name", sa.String(length=60), nullable=True))
    op.add_column("rides", sa.Column("rider_phone", sa.String(length=16), nullable=True))
    op.add_column("rides", sa.Column("note", sa.String(length=140), nullable=True))
    op.add_column(
        "ride_share_links",
        sa.Column("for_rider", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("saved_places", sa.Column("icon", sa.String(length=16), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("saved_places", "icon")
    op.drop_column("ride_share_links", "for_rider")
    op.drop_column("rides", "note")
    op.drop_column("rides", "rider_phone")
    op.drop_column("rides", "rider_name")
