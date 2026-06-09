"""Allow LiteAPI hotels and Viator tours in wishlists.

Revision ID: 040
Revises: 039
Create Date: 2026-06-09

The wishlist originally only referenced internal hotels/tours (FK to hotels.id /
tours.id). External LiteAPI hotels and Viator tours have no internal row, so we
store their external identifier (liteapi_hotel_id / viator_product_code) plus a
small display snapshot (name/city/country/image) captured at save time. The
single-target check is widened from 2 to exactly-one-of-4 columns.
"""
from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wishlists", sa.Column("liteapi_hotel_id", sa.String(255), nullable=True))
    op.add_column("wishlists", sa.Column("viator_product_code", sa.String(255), nullable=True))
    op.add_column("wishlists", sa.Column("item_name", sa.String(255), nullable=True))
    op.add_column("wishlists", sa.Column("item_city", sa.String(100), nullable=True))
    op.add_column("wishlists", sa.Column("item_country", sa.String(100), nullable=True))
    op.add_column("wishlists", sa.Column("item_image", sa.Text(), nullable=True))

    op.drop_constraint("wishlist_single_target", "wishlists", type_="check")
    op.create_check_constraint(
        "wishlist_single_target",
        "wishlists",
        "(CASE WHEN hotel_id IS NOT NULL THEN 1 ELSE 0 END"
        " + CASE WHEN tour_id IS NOT NULL THEN 1 ELSE 0 END"
        " + CASE WHEN liteapi_hotel_id IS NOT NULL THEN 1 ELSE 0 END"
        " + CASE WHEN viator_product_code IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )


def downgrade() -> None:
    op.drop_constraint("wishlist_single_target", "wishlists", type_="check")
    op.create_check_constraint(
        "wishlist_single_target",
        "wishlists",
        "(hotel_id IS NOT NULL AND tour_id IS NULL) OR (hotel_id IS NULL AND tour_id IS NOT NULL)",
    )
    op.drop_column("wishlists", "item_image")
    op.drop_column("wishlists", "item_country")
    op.drop_column("wishlists", "item_city")
    op.drop_column("wishlists", "item_name")
    op.drop_column("wishlists", "viator_product_code")
    op.drop_column("wishlists", "liteapi_hotel_id")
