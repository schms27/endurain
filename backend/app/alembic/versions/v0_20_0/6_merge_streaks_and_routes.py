"""6: merge the weekly streak and segments/routes branches

Revision ID: 9e4b7d2a6c15
Revises: 7c1e5a9d3b42, 5c8d1a3f9b20
Create Date: 2026-10-18 23:45:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "9e4b7d2a6c15"
down_revision: str | Sequence[str] | None = ("7c1e5a9d3b42", "5c8d1a3f9b20")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Join the two v0.20.0 heads; no schema changes."""


def downgrade() -> None:
    """Split back into the two v0.20.0 heads; no schema changes."""
