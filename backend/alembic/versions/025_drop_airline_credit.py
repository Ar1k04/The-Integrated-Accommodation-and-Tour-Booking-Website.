"""Drop airline_credit table — feature rolled back.

Revision ID: 025
Revises: 024
Create Date: 2026-05-24

The airline credits feature was rolled back per user direction. This migration
drops the table created in 024. Downgrade re-creates it identically (matches
024's upgrade) so we can restore the feature later without rewriting history.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_airline_credit_expires", table_name="airline_credit")
    op.drop_index("ix_airline_credit_iata", table_name="airline_credit")
    op.drop_index("ix_airline_credit_user_status", table_name="airline_credit")
    op.drop_table("airline_credit")


def downgrade() -> None:
    op.create_table(
        "airline_credit",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("duffel_credit_id", sa.String(100), nullable=True),
        sa.Column("airline_iata", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("redemption_code", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.Date, nullable=False),
        sa.Column("issued_at", sa.Date, nullable=False),
        sa.Column("credit_type", sa.String(20), nullable=False, server_default="eticket"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("passenger_name", sa.String(255), nullable=False),
        sa.Column("raw", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "credit_type IN ('eticket', 'mco', 'emd')",
            name="ck_airline_credit_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'spent', 'invalidated', 'expired')",
            name="ck_airline_credit_status",
        ),
        sa.UniqueConstraint("duffel_credit_id", name="uq_airline_credit_duffel_id"),
    )
    op.create_index(
        "ix_airline_credit_user_status", "airline_credit", ["user_id", "status"]
    )
    op.create_index("ix_airline_credit_iata", "airline_credit", ["airline_iata"])
    op.create_index("ix_airline_credit_expires", "airline_credit", ["expires_at"])
