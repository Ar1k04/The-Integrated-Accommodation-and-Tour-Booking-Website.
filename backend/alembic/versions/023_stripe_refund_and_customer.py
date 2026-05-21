"""Stripe refund audit trail, decline diagnostics, and Customer linkage.

Revision ID: 023
Revises: 022
Create Date: 2026-05-21

Adds:
- payments.stripe_refund_id (string, unique, nullable) — Stripe re_xxx for audit
- payments.refunded_amount (numeric, default 0) — running total of refunded amount
- payments.failure_code / decline_code / failure_message (nullable) — populated
  from Stripe's last_payment_error on payment_intent.payment_failed so the
  frontend can show the user *why* their card was declined.
- users.stripe_customer_id (string, unique, nullable) — Stripe cus_xxx linkage.
"""
from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("stripe_refund_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_payments_stripe_refund_id", "payments", ["stripe_refund_id"])

    op.add_column(
        "payments",
        sa.Column(
            "refunded_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column("payments", sa.Column("failure_code", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("decline_code", sa.String(64), nullable=True))
    op.add_column("payments", sa.Column("failure_message", sa.String(500), nullable=True))

    op.add_column("users", sa.Column("stripe_customer_id", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_stripe_customer_id", "users", ["stripe_customer_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_stripe_customer_id", "users", type_="unique")
    op.drop_column("users", "stripe_customer_id")

    op.drop_column("payments", "failure_message")
    op.drop_column("payments", "decline_code")
    op.drop_column("payments", "failure_code")
    op.drop_column("payments", "refunded_amount")

    op.drop_constraint("uq_payments_stripe_refund_id", "payments", type_="unique")
    op.drop_column("payments", "stripe_refund_id")
