"""Add flags + duration_minutes columns to tours.

Revision ID: 037
Revises: 036
Create Date: 2026-06-04

Partner-created tours can now declare supplier feature flags (a subset of
Viator's product flags, e.g. FREE_CANCELLATION) and a minute-precise run-time,
so they match the same "Features" and "Duration" filters as Viator products on
the Tours page. Both nullable so existing rows keep working: duration_minutes
falls back to duration_days at filter time; flags defaults to an empty list.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tours", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "tours",
        sa.Column("flags", JSONB(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("tours", "flags")
    op.drop_column("tours", "duration_minutes")
