"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("role", sa.String(20), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("loyalty_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "hotels",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("star_rating", sa.Integer(), server_default="3", nullable=False),
        sa.Column("property_type", sa.String(50), nullable=True),
        sa.Column("amenities", postgresql.JSONB(), nullable=True),
        sa.Column("images", postgresql.JSONB(), nullable=True),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("avg_rating", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_reviews", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hotels_slug", "hotels", ["slug"], unique=True)
    op.create_index("ix_hotels_city", "hotels", ["city"])
    op.create_index("ix_hotels_country", "hotels", ["country"])

    op.create_table(
        "rooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("hotel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("room_type", sa.String(50), nullable=False),
        sa.Column("price_per_night", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_guests", sa.Integer(), server_default="2", nullable=False),
        sa.Column("amenities", postgresql.JSONB(), nullable=True),
        sa.Column("images", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rooms_hotel_id", "rooms", ["hotel_id"])

    op.create_table(
        "tours",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("max_participants", sa.Integer(), nullable=True),
        sa.Column("price_per_person", sa.Numeric(10, 2), nullable=False),
        sa.Column("highlights", postgresql.JSONB(), nullable=True),
        sa.Column("itinerary", postgresql.JSONB(), nullable=True),
        sa.Column("includes", postgresql.JSONB(), nullable=True),
        sa.Column("excludes", postgresql.JSONB(), nullable=True),
        sa.Column("images", postgresql.JSONB(), nullable=True),
        sa.Column("avg_rating", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_reviews", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tours_slug", "tours", ["slug"], unique=True)
    op.create_index("ix_tours_city", "tours", ["city"])

    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("current_uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_booking_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"], unique=True)

    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("guests_count", sa.Integer(), nullable=True),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promo_code_id"], ["promo_codes.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])
    op.create_index("ix_bookings_room_id", "bookings", ["room_id"])
    op.create_index("ix_bookings_check_in", "bookings", ["check_in"])
    op.create_index("ix_bookings_check_out", "bookings", ["check_out"])

    op.create_table(
        "tour_bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tour_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tour_date", sa.Date(), nullable=False),
        sa.Column("participants_count", sa.Integer(), nullable=True),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tour_bookings_user_id", "tour_bookings", ["user_id"])
    op.create_index("ix_tour_bookings_tour_id", "tour_bookings", ["tour_id"])

    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tour_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "(hotel_id IS NOT NULL AND tour_id IS NULL) OR (hotel_id IS NULL AND tour_id IS NOT NULL)",
            name="review_single_target",
        ),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(10), server_default="usd", nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("stripe_payment_intent_id"),
    )

    op.create_table(
        "wishlists",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hotel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tour_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "(hotel_id IS NOT NULL AND tour_id IS NULL) OR (hotel_id IS NULL AND tour_id IS NOT NULL)",
            name="wishlist_single_target",
        ),
    )


def downgrade() -> None:
    op.drop_table("wishlists")
    op.drop_table("payments")
    op.drop_table("reviews")
    op.drop_table("tour_bookings")
    op.drop_table("bookings")
    op.drop_table("promo_codes")
    op.drop_table("tours")
    op.drop_table("rooms")
    op.drop_table("hotels")
    op.drop_table("users")
