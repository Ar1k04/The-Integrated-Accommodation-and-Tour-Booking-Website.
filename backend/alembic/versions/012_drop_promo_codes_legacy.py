"""Drop legacy promo_codes table and bookings.promo_code_id column.

All promo_codes data was migrated into vouchers in migration 006.
The promo_codes endpoint is removed; vouchers is the canonical path.

Revision ID: 012
Revises: 011
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop FK from bookings → promo_codes (auto-named by PostgreSQL)
    op.drop_constraint("bookings_promo_code_id_fkey", "bookings", type_="foreignkey")
    op.drop_column("bookings", "promo_code_id")

    # Drop the promo_codes table itself
    op.drop_index("ix_promo_codes_code", table_name="promo_codes")
    op.drop_table("promo_codes")


def downgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("current_uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column("min_booking_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promo_codes_code", "promo_codes", ["code"], unique=True)

    op.add_column(
        "bookings",
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "bookings_promo_code_id_fkey",
        "bookings",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
