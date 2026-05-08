"""Widen liteapi_prebook_id and liteapi_booking_id from VARCHAR(255) to TEXT.

LiteAPI prebook IDs are base64-encoded blobs that regularly exceed 255 characters.

Revision ID: 016
Revises: 015
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "booking_item",
        "liteapi_prebook_id",
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "booking_item",
        "liteapi_booking_id",
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Truncate silently on downgrade — any stored value > 255 chars will error.
    op.alter_column(
        "booking_item",
        "liteapi_prebook_id",
        type_=sa.String(255),
        existing_nullable=True,
    )
    op.alter_column(
        "booking_item",
        "liteapi_booking_id",
        type_=sa.String(255),
        existing_nullable=True,
    )
