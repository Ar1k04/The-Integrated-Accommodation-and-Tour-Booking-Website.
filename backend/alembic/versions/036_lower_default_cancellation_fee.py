"""Lower default partner-room cancellation fee 100% -> 20%.

Revision ID: 036
Revises: 035
Create Date: 2026-06-03

A 100% late-cancellation fee made every short-notice partner booking effectively
non-refundable (cancelling after the free window returned nothing). Default to a
20% fee instead so guests still get most of their money back when they miss the
deadline; partners can still raise it per room (up to 100) in the form.

Existing rooms that still carry the original 100 default are reset to 20 — at
this stage no partner has intentionally configured a custom fee. Booking_items
keep their snapshotted value (confirmed bookings are unaffected).
"""
from alembic import op


revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("rooms", "cancellation_fee_percent", server_default="20")
    op.execute("UPDATE rooms SET cancellation_fee_percent = 20 WHERE cancellation_fee_percent = 100")


def downgrade() -> None:
    op.alter_column("rooms", "cancellation_fee_percent", server_default="100")
    op.execute("UPDATE rooms SET cancellation_fee_percent = 100 WHERE cancellation_fee_percent = 20")
