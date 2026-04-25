"""Add LiteAPI fields to booking_items and relax room check constraint.

Revision ID: 008
Revises: 007
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_item",
        sa.Column("liteapi_prebook_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("liteapi_booking_id", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_booking_item_liteapi_booking_id",
        "booking_item",
        ["liteapi_booking_id"],
    )

    # Relax the room check constraint to allow LiteAPI rooms (room_id IS NULL when liteapi_prebook_id is set)
    op.drop_constraint("ck_booking_item_target", "booking_item", type_="check")
    op.create_check_constraint(
        "ck_booking_item_target",
        "booking_item",
        "(item_type = 'room' AND (room_id IS NOT NULL OR liteapi_prebook_id IS NOT NULL) AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'tour' AND tour_schedule_id IS NOT NULL AND room_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_booking_item_target", "booking_item", type_="check")
    op.create_check_constraint(
        "ck_booking_item_target",
        "booking_item",
        "(item_type = 'room' AND room_id IS NOT NULL AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'tour' AND tour_schedule_id IS NOT NULL AND room_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
    )
    op.drop_constraint("uq_booking_item_liteapi_booking_id", "booking_item", type_="unique")
    op.drop_column("booking_item", "liteapi_booking_id")
    op.drop_column("booking_item", "liteapi_prebook_id")
