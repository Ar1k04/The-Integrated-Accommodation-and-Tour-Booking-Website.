"""Add liteapi_hotel_id to reviews for LiteAPI hotel reviews.

Revision ID: 038
Revises: 037
Create Date: 2026-06-07

LiteAPI hotels have no local hotels row — bookings reference them by the
liteapi_hotel_id string on booking_item. To let guests review a LiteAPI hotel
after a completed stay (and merge those with LiteAPI's own read-only reviews),
reviews now carry the same identifier, mirroring how viator_product_code works
for Viator tours. The single-target check constraint widens to four mutually
exclusive targets.
"""
from alembic import op
import sqlalchemy as sa

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("liteapi_hotel_id", sa.String(100), nullable=True))

    op.drop_constraint("review_single_target", "reviews", type_="check")
    op.create_check_constraint(
        "review_single_target",
        "reviews",
        "(hotel_id IS NOT NULL AND tour_id IS NULL AND viator_product_code IS NULL AND liteapi_hotel_id IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NOT NULL AND viator_product_code IS NULL AND liteapi_hotel_id IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NULL AND viator_product_code IS NOT NULL AND liteapi_hotel_id IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NULL AND viator_product_code IS NULL AND liteapi_hotel_id IS NOT NULL)",
    )
    op.create_index("ix_reviews_liteapi_hotel_id", "reviews", ["liteapi_hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_liteapi_hotel_id", table_name="reviews")
    op.drop_constraint("review_single_target", "reviews", type_="check")
    op.create_check_constraint(
        "review_single_target",
        "reviews",
        "(hotel_id IS NOT NULL AND tour_id IS NULL AND viator_product_code IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NOT NULL AND viator_product_code IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NULL AND viator_product_code IS NOT NULL)",
    )
    op.drop_column("reviews", "liteapi_hotel_id")
