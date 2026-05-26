"""Add image_url to booking_item for LiteAPI hotels / Viator tours.

Revision ID: 027
Revises: 026
Create Date: 2026-05-26

LiteAPI/Viator-sourced booking items have no DB hotel/tour row, so the
My Bookings card had no thumbnail. We now copy the supplier's main image URL
onto the booking item at reserve time so the card can render it without an
extra fetch.
"""
from alembic import op
import sqlalchemy as sa


revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_item",
        sa.Column("image_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("booking_item", "image_url")
