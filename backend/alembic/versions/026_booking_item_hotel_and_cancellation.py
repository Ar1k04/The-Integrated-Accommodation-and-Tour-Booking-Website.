"""Add LiteAPI hotel / Viator tour summary + cancellation policy to booking_item.

Revision ID: 026
Revises: 025
Create Date: 2026-05-26

Adds four nullable columns so the "My Bookings" UI can:
  * link back to the supplier hotel/tour detail page without a join,
  * show the LiteAPI cancellation deadline that the rate actually grants
    (no more confusion about "can I cancel after 1 hour?").

All columns nullable — historical bookings stay valid.
"""
from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_item",
        sa.Column("liteapi_hotel_id", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("hotel_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("tour_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("cancellation_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("refundable", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("booking_item", "refundable")
    op.drop_column("booking_item", "cancellation_deadline")
    op.drop_column("booking_item", "tour_name")
    op.drop_column("booking_item", "hotel_name")
    op.drop_column("booking_item", "liteapi_hotel_id")
