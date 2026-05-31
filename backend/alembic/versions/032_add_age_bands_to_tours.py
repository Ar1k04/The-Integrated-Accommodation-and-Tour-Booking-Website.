"""Add age_bands JSONB column to tours.

Revision ID: 032
Revises: 031
Create Date: 2026-05-31

Partner-created tours now carry supplier-style age bands (mirroring Viator's
``pricingInfo.ageBands[]``) so they share the unified tour detail page,
availability check, and per-band child pricing with Viator products. Each
band: {age_band, start_age, end_age, min_travelers, max_travelers, price}.

Nullable so existing/seeded tours (no bands) keep working via the legacy
default-child-tier pricing fallback in booking_service.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tours", sa.Column("age_bands", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("tours", "age_bands")
