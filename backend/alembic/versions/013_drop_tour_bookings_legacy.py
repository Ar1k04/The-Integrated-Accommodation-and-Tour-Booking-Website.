"""Drop legacy tour_bookings table.

All tour_bookings data was migrated into booking + booking_item in migration 006.
Tour bookings now flow exclusively through the polymorphic booking_item table.

Revision ID: 013
Revises: 012
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_tour_bookings_tour_id", table_name="tour_bookings")
    op.drop_index("ix_tour_bookings_user_id", table_name="tour_bookings")
    op.drop_table("tour_bookings")


def downgrade() -> None:
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
