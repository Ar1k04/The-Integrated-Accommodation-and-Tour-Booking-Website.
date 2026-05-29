"""Add trigram GIN index on cities.name_norm for focused fuzzy match.

Revision ID: 031
Revises: 030
Create Date: 2026-05-29

After migration 030 broadened `search_text` to include `admin1` and
`alt_names`, the trigram `%` operator on `search_text` started missing
typo cases ("hanio" no longer matches "Hanoi") because the longer text
dilutes the similarity score below the 0.3 threshold.

Solution: index `name_norm` for trigram matching too, and have the fuzzy
arm operate on that focused field. The prefix and word-boundary arms keep
using `search_text` (admin1 + alt_names still searchable). Locations route
is updated to switch the `%` operator and similarity() to name_norm.
"""
from alembic import op


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_cities_name_norm_trgm ON cities USING gin (name_norm gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cities_name_norm_trgm")
