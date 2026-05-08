"""Add lifetime_loyalty_points to users and tier_discount to bookings.

Phase 2: lifetime_loyalty_points drives tier recomputation so redeeming
         balance points no longer demotes the user's tier.
Phase 3: tier_discount records the member-discount applied at booking time.

Revision ID: 017
Revises: 016
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: add lifetime_loyalty_points ---
    op.add_column(
        "users",
        sa.Column("lifetime_loyalty_points", sa.Integer(), server_default="0", nullable=False),
    )
    # Backfill from earn transactions
    op.execute(
        """
        UPDATE users u
        SET lifetime_loyalty_points = COALESCE(
            (SELECT SUM(points)
             FROM loyalty_transaction lt
             WHERE lt.user_id = u.id AND lt.type = 'earn'),
            0
        )
        """
    )
    # Recompute every user's tier based on the new lifetime column
    op.execute(
        """
        UPDATE users u
        SET loyalty_tier_id = (
            SELECT lt.id
            FROM loyalty_tier lt
            WHERE lt.min_points <= u.lifetime_loyalty_points
            ORDER BY lt.min_points DESC
            LIMIT 1
        )
        """
    )

    # --- bookings: add tier_discount ---
    op.add_column(
        "bookings",
        sa.Column("tier_discount", sa.Numeric(10, 2), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("bookings", "tier_discount")
    op.drop_column("users", "lifetime_loyalty_points")
