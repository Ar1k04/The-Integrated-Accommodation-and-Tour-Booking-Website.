"""Add viator_product_code to reviews for Viator tour reviews.

Revision ID: 018
Revises: 017
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("viator_product_code", sa.String(100), nullable=True))

    op.drop_constraint("review_single_target", "reviews", type_="check")
    op.create_check_constraint(
        "review_single_target",
        "reviews",
        "(hotel_id IS NOT NULL AND tour_id IS NULL AND viator_product_code IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NOT NULL AND viator_product_code IS NULL) "
        "OR (hotel_id IS NULL AND tour_id IS NULL AND viator_product_code IS NOT NULL)",
    )
    op.create_index("ix_reviews_viator_product_code", "reviews", ["viator_product_code"])


def downgrade() -> None:
    op.drop_index("ix_reviews_viator_product_code", table_name="reviews")
    op.drop_constraint("review_single_target", "reviews", type_="check")
    op.create_check_constraint(
        "review_single_target",
        "reviews",
        "(hotel_id IS NOT NULL AND tour_id IS NULL) OR (hotel_id IS NULL AND tour_id IS NOT NULL)",
    )
    op.drop_column("reviews", "viator_product_code")
