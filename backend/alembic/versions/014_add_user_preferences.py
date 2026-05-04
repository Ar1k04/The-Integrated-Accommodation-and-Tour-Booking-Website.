"""Add preferred_locale and preferred_currency to users table.

Supports per-user language and currency display preferences (en/vi, USD/VND).

Revision ID: 014
Revises: 013
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferred_locale", sa.String(2), server_default="en", nullable=False))
    op.add_column("users", sa.Column("preferred_currency", sa.String(3), server_default="USD", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "preferred_currency")
    op.drop_column("users", "preferred_locale")
