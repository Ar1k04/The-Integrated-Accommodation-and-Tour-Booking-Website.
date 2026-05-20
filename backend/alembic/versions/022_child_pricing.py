"""Add child pricing fields to rooms and booking_item.

Revision ID: 022
Revises: 021
Create Date: 2026-05-20

Adds:
- rooms.child_age_tiers (JSONB, nullable) — admin override of default tier table
- booking_item.adults_count (int, nullable)
- booking_item.children_count (int, nullable)
- booking_item.children_ages (JSONB, nullable)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("child_age_tiers", JSONB(), nullable=True))

    op.add_column("booking_item", sa.Column("adults_count", sa.Integer(), nullable=True))
    op.add_column("booking_item", sa.Column("children_count", sa.Integer(), nullable=True))
    op.add_column("booking_item", sa.Column("children_ages", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("booking_item", "children_ages")
    op.drop_column("booking_item", "children_count")
    op.drop_column("booking_item", "adults_count")
    op.drop_column("rooms", "child_age_tiers")
