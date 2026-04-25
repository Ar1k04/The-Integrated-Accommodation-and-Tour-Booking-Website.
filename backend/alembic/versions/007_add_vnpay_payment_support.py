"""Add VNPay support to payments table.

Revision ID: 007
Revises: 006
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider", sa.String(20), nullable=False, server_default="stripe"),
    )
    op.add_column(
        "payments",
        sa.Column("vnpay_transaction_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "vnpay_transaction_id")
    op.drop_column("payments", "provider")
