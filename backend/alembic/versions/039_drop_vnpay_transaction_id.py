"""Drop vnpay_transaction_id from payments (project is Stripe-only).

Revision ID: 039
Revises: 038
Create Date: 2026-06-09

Both MoMo and VNPay were removed; Stripe is the only payment provider. This drops
the now-dormant vnpay_transaction_id column (originally added in migration 007).
The generic `provider` column (also added in 007) is kept — Stripe uses it.
"""
from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("payments", "vnpay_transaction_id")


def downgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("vnpay_transaction_id", sa.String(255), nullable=True),
    )
