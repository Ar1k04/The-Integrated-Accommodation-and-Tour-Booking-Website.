"""Add subtotal and taxes columns to bookings.

Revision ID: 021
Revises: 020
Create Date: 2026-05-19

Splits the existing single-field total into an explicit breakdown so the
booking confirmation + MyBookings UI can render the same line items the user
saw at checkout (subtotal, taxes, discount, total).

Backfill rule for pre-existing rows:
    subtotal := total_price / (1 + TAX_RATE) − any existing discounts
    taxes    := total_price − subtotal − discounts
Since historical rows have no tax stored, we conservatively set subtotal =
total_price + discount_amount + tier_discount and taxes = 0, which yields
the previous behaviour (total = subtotal − discounts). Going forward all new
bookings will compute the real breakdown.
"""
from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bookings",
        sa.Column("subtotal", sa.Numeric(10, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "bookings",
        sa.Column("taxes", sa.Numeric(10, 2), server_default="0", nullable=False),
    )
    # Backfill existing rows: pre-fix bookings have no separate tax line, so
    # reconstruct subtotal as total + discounts; taxes stay 0.
    op.execute(
        """
        UPDATE bookings
        SET subtotal = COALESCE(total_price, 0)
                     + COALESCE(discount_amount, 0)
                     + COALESCE(tier_discount, 0)
        """
    )


def downgrade() -> None:
    op.drop_column("bookings", "taxes")
    op.drop_column("bookings", "subtotal")
