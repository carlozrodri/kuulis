"""enable pg_stat_statements

Revision ID: 5d2e8a1c7b40
Revises: f7b3bf4c9a78
Create Date: 2026-10-11 10:30:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5d2e8a1c7b40"
down_revision: Union[str, Sequence[str], None] = "f7b3bf4c9a78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Slow query stats. Collects only when the server preloads the library (docs/deployment.md)."""
    # Never blocks a deploy: without superuser or the contrib files it only leaves a notice.
    op.execute(
        """
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
        EXCEPTION WHEN insufficient_privilege OR undefined_file THEN
            RAISE NOTICE 'pg_stat_statements not available: %', SQLERRM;
        END $$
        """
    )


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_stat_statements")
