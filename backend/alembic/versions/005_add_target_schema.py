"""add target schema tables and columns

Revision ID: 005
Revises: 004
Create Date: 2026-04-21

Sprint 1, step 1: additive schema changes only. Creates the 8 missing tables
from docs/Project.sql (loyalty_tier, loyalty_transaction, vouchers,
voucher_usage, room_availability, tour_schedule, flight_booking, booking_item)
and the new reference columns on existing tables (users.loyalty_tier_id,
hotels.liteapi_hotel_id, rooms.liteapi_room_id, tours.viator_product_code).

Nothing is dropped or renamed here. Data reshape happens in migration 006.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # loyalty_tier ---------------------------------------------------------
    op.create_table(
        "loyalty_tier",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("min_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_loyalty_tier_name"),
    )

    # Seed the four tiers. Points are lifetime-earned buckets.
    op.execute(
        """
        INSERT INTO loyalty_tier (name, min_points, max_points, discount_percent, benefits) VALUES
            ('Bronze',    0,     499,  0.00,  'Welcome tier'),
            ('Silver',    500,   1499, 5.00,  '5% discount on bookings'),
            ('Gold',      1500,  4999, 10.00, '10% discount + priority support'),
            ('Platinum',  5000,  0,    15.00, '15% discount + free cancellation + concierge')
        """
    )

    # users.loyalty_tier_id -----------------------------------------------
    op.add_column(
        "users",
        sa.Column("loyalty_tier_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_users_loyalty_tier_id", "users", ["loyalty_tier_id"])
    op.create_foreign_key(
        "fk_users_loyalty_tier_id", "users", "loyalty_tier",
        ["loyalty_tier_id"], ["id"], ondelete="SET NULL",
    )

    # Default every existing user to Bronze so the column has a value.
    op.execute(
        """
        UPDATE users
        SET loyalty_tier_id = (SELECT id FROM loyalty_tier WHERE name = 'Bronze')
        WHERE loyalty_tier_id IS NULL
        """
    )

    # Catalog external-API id columns -------------------------------------
    op.add_column("hotels", sa.Column("liteapi_hotel_id", sa.String(100), nullable=True))
    op.create_index("ix_hotels_liteapi_hotel_id", "hotels", ["liteapi_hotel_id"])

    op.add_column("rooms", sa.Column("liteapi_room_id", sa.String(100), nullable=True))
    op.create_index("ix_rooms_liteapi_room_id", "rooms", ["liteapi_room_id"])

    op.add_column("tours", sa.Column("viator_product_code", sa.String(100), nullable=True))
    op.create_index("ix_tours_viator_product_code", "tours", ["viator_product_code"])

    # vouchers ------------------------------------------------------------
    op.create_table(
        "vouchers",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("discount_type", sa.String(20), server_default="percentage", nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("min_order_value", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint("discount_type IN ('percentage', 'fixed')", name="ck_vouchers_discount_type"),
        sa.CheckConstraint("status IN ('active', 'expired', 'disabled')", name="ck_vouchers_status"),
    )
    op.create_index("ix_vouchers_code", "vouchers", ["code"], unique=True)
    op.create_index("ix_vouchers_admin_id", "vouchers", ["admin_id"])

    # voucher_usage -------------------------------------------------------
    op.create_table(
        "voucher_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("voucher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["voucher_id"], ["vouchers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("voucher_id", "user_id", name="uq_voucher_user"),
    )

    # room_availability ---------------------------------------------------
    op.create_table(
        "room_availability",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="available", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('available', 'booked', 'blocked')", name="ck_room_availability_status"),
        sa.UniqueConstraint("room_id", "date", name="uq_room_date"),
    )
    op.create_index("ix_room_availability_room_id", "room_availability", ["room_id"])
    op.create_index("ix_room_availability_date", "room_availability", ["date"])

    # tour_schedule -------------------------------------------------------
    op.create_table(
        "tour_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tour_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("available_date", sa.Date(), nullable=False),
        sa.Column("total_slots", sa.Integer(), server_default="0", nullable=False),
        sa.Column("booked_slots", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
        sa.CheckConstraint("booked_slots <= total_slots", name="ck_tour_schedule_capacity"),
        sa.UniqueConstraint("tour_id", "available_date", name="uq_tour_date"),
    )
    op.create_index("ix_tour_schedule_tour_id", "tour_schedule", ["tour_id"])
    op.create_index("ix_tour_schedule_available_date", "tour_schedule", ["available_date"])

    # flight_booking ------------------------------------------------------
    op.create_table(
        "flight_booking",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("duffel_order_id", sa.String(100), nullable=False),
        sa.Column("duffel_booking_ref", sa.String(50), nullable=True),
        sa.Column("airline_name", sa.String(100), nullable=False),
        sa.Column("flight_number", sa.String(20), nullable=False),
        sa.Column("departure_airport", sa.String(10), nullable=False),
        sa.Column("arrival_airport", sa.String(10), nullable=False),
        sa.Column("departure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cabin_class", sa.String(20), nullable=True),
        sa.Column("passenger_name", sa.String(255), nullable=False),
        sa.Column("passenger_email", sa.String(255), nullable=False),
        sa.Column("base_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="VND", nullable=False),
        sa.Column("status", sa.String(20), server_default="confirmed", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("duffel_order_id", name="uq_flight_booking_duffel_order_id"),
        sa.CheckConstraint("status IN ('confirmed', 'cancelled', 'refunded')", name="ck_flight_booking_status"),
    )

    # loyalty_transaction -------------------------------------------------
    op.create_table(
        "loyalty_transaction",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="SET NULL"),
        sa.CheckConstraint("type IN ('earn', 'redeem', 'adjust')", name="ck_loyalty_transaction_type"),
    )
    op.create_index("ix_loyalty_transaction_user_id", "loyalty_transaction", ["user_id"])
    op.create_index("ix_loyalty_transaction_booking_id", "loyalty_transaction", ["booking_id"])

    # booking_item --------------------------------------------------------
    op.create_table(
        "booking_item",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("check_in", sa.Date(), nullable=True),
        sa.Column("check_out", sa.Date(), nullable=True),
        sa.Column("tour_schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("flight_booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tour_schedule_id"], ["tour_schedule.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flight_booking_id"], ["flight_booking.id"], ondelete="SET NULL"),
        sa.CheckConstraint("item_type IN ('room', 'tour', 'flight')", name="ck_booking_item_type"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'cancelled', 'completed')", name="ck_booking_item_status"),
        sa.CheckConstraint(
            "(item_type = 'room' AND room_id IS NOT NULL AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
            "OR (item_type = 'tour' AND tour_schedule_id IS NOT NULL AND room_id IS NULL AND flight_booking_id IS NULL) "
            "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
            name="ck_booking_item_target",
        ),
    )
    op.create_index("ix_booking_item_booking_id", "booking_item", ["booking_id"])
    op.create_index("ix_booking_item_room_id", "booking_item", ["room_id"])
    op.create_index("ix_booking_item_tour_schedule_id", "booking_item", ["tour_schedule_id"])
    op.create_index("ix_booking_item_flight_booking_id", "booking_item", ["flight_booking_id"])

    # reviews.booking_item_id (target schema has it; nullable so existing rows are unaffected)
    op.add_column(
        "reviews",
        sa.Column("booking_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_reviews_booking_item_id", "reviews", ["booking_item_id"])
    op.create_foreign_key(
        "fk_reviews_booking_item_id", "reviews", "booking_item",
        ["booking_item_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_reviews_booking_item_id", "reviews", type_="foreignkey")
    op.drop_index("ix_reviews_booking_item_id", table_name="reviews")
    op.drop_column("reviews", "booking_item_id")

    op.drop_index("ix_booking_item_flight_booking_id", table_name="booking_item")
    op.drop_index("ix_booking_item_tour_schedule_id", table_name="booking_item")
    op.drop_index("ix_booking_item_room_id", table_name="booking_item")
    op.drop_index("ix_booking_item_booking_id", table_name="booking_item")
    op.drop_table("booking_item")

    op.drop_index("ix_loyalty_transaction_booking_id", table_name="loyalty_transaction")
    op.drop_index("ix_loyalty_transaction_user_id", table_name="loyalty_transaction")
    op.drop_table("loyalty_transaction")

    op.drop_table("flight_booking")

    op.drop_index("ix_tour_schedule_available_date", table_name="tour_schedule")
    op.drop_index("ix_tour_schedule_tour_id", table_name="tour_schedule")
    op.drop_table("tour_schedule")

    op.drop_index("ix_room_availability_date", table_name="room_availability")
    op.drop_index("ix_room_availability_room_id", table_name="room_availability")
    op.drop_table("room_availability")

    op.drop_table("voucher_usage")

    op.drop_index("ix_vouchers_admin_id", table_name="vouchers")
    op.drop_index("ix_vouchers_code", table_name="vouchers")
    op.drop_table("vouchers")

    op.drop_index("ix_tours_viator_product_code", table_name="tours")
    op.drop_column("tours", "viator_product_code")

    op.drop_index("ix_rooms_liteapi_room_id", table_name="rooms")
    op.drop_column("rooms", "liteapi_room_id")

    op.drop_index("ix_hotels_liteapi_hotel_id", table_name="hotels")
    op.drop_column("hotels", "liteapi_hotel_id")

    op.drop_constraint("fk_users_loyalty_tier_id", "users", type_="foreignkey")
    op.drop_index("ix_users_loyalty_tier_id", table_name="users")
    op.drop_column("users", "loyalty_tier_id")

    op.drop_table("loyalty_tier")
