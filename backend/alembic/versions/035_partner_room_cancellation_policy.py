"""Partner room cancellation policy + booking_item fee snapshot.

Revision ID: 035
Revises: 034
Create Date: 2026-06-03

Partner-owned rooms previously had no cancellation policy, so cancelling such a
booking always fell into the "non-refundable" branch and the customer got no
refund. This adds a LiteAPI-style deadline policy to `rooms`:

  * refundable               — whether the room can be cancelled/refunded at all
  * free_cancellation_days   — free cancel up to N days before check-in
  * cancellation_fee_percent — % of the line subtotal kept if cancelled later
                               (100 = no refund past the deadline)

and snapshots the fee % onto booking_item (deadline + refundable columns already
exist from migration 026) so editing the room later can't change what a
confirmed booking owes.

Server defaults make existing rooms refundable with a 1-day free window and a
100% late-cancellation fee, matching the prior implicit behaviour as closely as
possible while now actually issuing refunds for on-time cancellations.
"""
from alembic import op
import sqlalchemy as sa


revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("refundable", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "rooms",
        sa.Column("free_cancellation_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "rooms",
        sa.Column(
            "cancellation_fee_percent",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="100",
        ),
    )
    op.add_column(
        "booking_item",
        sa.Column("cancellation_fee_percent", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("booking_item", "cancellation_fee_percent")
    op.drop_column("rooms", "cancellation_fee_percent")
    op.drop_column("rooms", "free_cancellation_days")
    op.drop_column("rooms", "refundable")
