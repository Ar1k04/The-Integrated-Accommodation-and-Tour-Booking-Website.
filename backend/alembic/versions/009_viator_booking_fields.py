"""Add Viator fields to booking_items and relax tour check constraint.

Revision ID: 009
Revises: 008
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "booking_item",
        sa.Column("viator_product_code", sa.String(100), nullable=True),
    )
    op.add_column(
        "booking_item",
        sa.Column("viator_booking_ref", sa.String(255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_booking_item_viator_booking_ref",
        "booking_item",
        ["viator_booking_ref"],
    )

    # Relax the tour check constraint to allow Viator tours (tour_schedule_id IS NULL when viator_product_code is set)
    op.drop_constraint("ck_booking_item_target", "booking_item", type_="check")
    op.create_check_constraint(
        "ck_booking_item_target",
        "booking_item",
        "(item_type = 'room' AND (room_id IS NOT NULL OR liteapi_prebook_id IS NOT NULL) AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'tour' AND (tour_schedule_id IS NOT NULL OR viator_product_code IS NOT NULL) AND room_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_booking_item_target", "booking_item", type_="check")
    op.create_check_constraint(
        "ck_booking_item_target",
        "booking_item",
        "(item_type = 'room' AND (room_id IS NOT NULL OR liteapi_prebook_id IS NOT NULL) AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'tour' AND tour_schedule_id IS NOT NULL AND room_id IS NULL AND flight_booking_id IS NULL) "
        "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
    )
    op.drop_constraint("uq_booking_item_viator_booking_ref", "booking_item", type_="unique")
    op.drop_column("booking_item", "viator_booking_ref")
    op.drop_column("booking_item", "viator_product_code")
