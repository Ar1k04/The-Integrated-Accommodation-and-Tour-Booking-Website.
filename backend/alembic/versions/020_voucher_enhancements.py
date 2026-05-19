"""Voucher enhancements: max discount cap, budget pool, guest-specific, LiteAPI sync fields.

Revision ID: 020
Revises: 019
Create Date: 2026-05-18

Adds the following columns to vouchers (all nullable / defaulted for backward compat):
- maximum_discount_amount: cap for percentage discounts
- currency: ISO 4217 currency code (required by LiteAPI sync)
- budget / budget_used: independent monetary pool
- guest_id: FK to users for guest-specific vouchers
- description / terms_and_conditions: rich text fields
- applicable_to: gates LiteAPI sync to hotel-applicable vouchers
- liteapi_voucher_id / liteapi_sync_status / liteapi_sync_error / liteapi_synced_at: sync state
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vouchers",
        sa.Column("maximum_discount_amount", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "vouchers",
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
    )
    op.add_column(
        "vouchers",
        sa.Column("budget", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "vouchers",
        sa.Column("budget_used", sa.Numeric(12, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "vouchers",
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_vouchers_guest_id", "vouchers", ["guest_id"])
    op.create_foreign_key(
        "fk_vouchers_guest_id_users",
        "vouchers",
        "users",
        ["guest_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("vouchers", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("vouchers", sa.Column("terms_and_conditions", sa.Text(), nullable=True))
    op.add_column(
        "vouchers",
        sa.Column(
            "applicable_to",
            sa.String(length=20),
            server_default="all",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_vouchers_applicable_to",
        "vouchers",
        "applicable_to IN ('all', 'hotel', 'tour', 'flight')",
    )
    op.add_column(
        "vouchers",
        sa.Column("liteapi_voucher_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_vouchers_liteapi_voucher_id",
        "vouchers",
        ["liteapi_voucher_id"],
        unique=True,
    )
    op.add_column(
        "vouchers",
        sa.Column(
            "liteapi_sync_status",
            sa.String(length=20),
            server_default="not_synced",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_vouchers_liteapi_sync_status",
        "vouchers",
        "liteapi_sync_status IN ('not_synced', 'synced', 'failed', 'disabled')",
    )
    op.add_column("vouchers", sa.Column("liteapi_sync_error", sa.Text(), nullable=True))
    op.add_column(
        "vouchers",
        sa.Column("liteapi_synced_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vouchers", "liteapi_synced_at")
    op.drop_column("vouchers", "liteapi_sync_error")
    op.drop_constraint("ck_vouchers_liteapi_sync_status", "vouchers", type_="check")
    op.drop_column("vouchers", "liteapi_sync_status")
    op.drop_index("ix_vouchers_liteapi_voucher_id", table_name="vouchers")
    op.drop_column("vouchers", "liteapi_voucher_id")
    op.drop_constraint("ck_vouchers_applicable_to", "vouchers", type_="check")
    op.drop_column("vouchers", "applicable_to")
    op.drop_column("vouchers", "terms_and_conditions")
    op.drop_column("vouchers", "description")
    op.drop_constraint("fk_vouchers_guest_id_users", "vouchers", type_="foreignkey")
    op.drop_index("ix_vouchers_guest_id", table_name="vouchers")
    op.drop_column("vouchers", "guest_id")
    op.drop_column("vouchers", "budget_used")
    op.drop_column("vouchers", "budget")
    op.drop_column("vouchers", "currency")
    op.drop_column("vouchers", "maximum_discount_amount")
