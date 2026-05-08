"""Drop legacy single-room columns from bookings table.

Data now lives on booking_item (room_id, check_in, check_out, quantity).

Revision ID: 011
Revises: 010
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_bookings_check_in", table_name="bookings")
    op.drop_index("ix_bookings_check_out", table_name="bookings")
    op.drop_index("ix_bookings_room_id", table_name="bookings")
    op.drop_constraint("bookings_room_id_fkey", "bookings", type_="foreignkey")
    op.drop_column("bookings", "room_id")
    op.drop_column("bookings", "check_in")
    op.drop_column("bookings", "check_out")
    op.drop_column("bookings", "guests_count")


def downgrade() -> None:
    op.add_column("bookings", sa.Column("guests_count", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("check_out", sa.Date(), nullable=True))
    op.add_column("bookings", sa.Column("check_in", sa.Date(), nullable=True))
    op.add_column("bookings", sa.Column("room_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "bookings_room_id_fkey", "bookings", "rooms", ["room_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_bookings_room_id", "bookings", ["room_id"])
    op.create_index("ix_bookings_check_in", "bookings", ["check_in"])
    op.create_index("ix_bookings_check_out", "bookings", ["check_out"])
