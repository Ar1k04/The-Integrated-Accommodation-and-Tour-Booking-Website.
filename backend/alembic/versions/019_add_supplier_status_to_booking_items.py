"""Add supplier_status and supplier_status_synced_at to booking_item.

Revision ID: 019
Revises: 018
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_item",
        sa.Column("supplier_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("supplier_status_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("booking_item", "supplier_status_synced_at")
    op.drop_column("booking_item", "supplier_status")
