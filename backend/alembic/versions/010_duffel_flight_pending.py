"""Add Duffel pending state to flight_booking: nullable duffel_order_id, pending status, passenger_details JSONB.

Revision ID: 010
Revises: 009
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("flight_booking", "duffel_order_id", nullable=True)

    op.drop_constraint("ck_flight_booking_status", "flight_booking", type_="check")
    op.create_check_constraint(
        "ck_flight_booking_status",
        "flight_booking",
        "status IN ('pending', 'confirmed', 'cancelled', 'refunded')",
    )

    op.add_column(
        "flight_booking",
        sa.Column("passenger_details", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("flight_booking", "passenger_details")

    op.drop_constraint("ck_flight_booking_status", "flight_booking", type_="check")
    op.create_check_constraint(
        "ck_flight_booking_status",
        "flight_booking",
        "status IN ('confirmed', 'cancelled', 'refunded')",
    )

    # Restore NOT NULL — set NULLs to a placeholder first
    op.execute("UPDATE flight_booking SET duffel_order_id = 'LEGACY-' || id::text WHERE duffel_order_id IS NULL")
    op.alter_column("flight_booking", "duffel_order_id", nullable=False)
