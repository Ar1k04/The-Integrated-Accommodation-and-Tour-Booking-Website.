"""Add partner_status column to users (partner approval workflow).

Revision ID: 033
Revises: 032
Create Date: 2026-06-02

Partners now require admin approval before they can use the staff dashboard
(UC_A_PARTNERS). ``partner_status`` ∈ {pending, approved, rejected}; NULL for
non-partner accounts. New partner registrations start ``pending``; existing
partners are backfilled to ``approved`` so they are not locked out.

Note: we deliberately do NOT reuse ``is_active`` for this — an inactive user is
rejected at authentication (403), but a pending partner must still be able to
log in to see the "awaiting approval" screen.
"""
import sqlalchemy as sa
from alembic import op


revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("partner_status", sa.String(length=20), nullable=True))
    # Existing partners keep working — mark them approved.
    op.execute("UPDATE users SET partner_status = 'approved' WHERE role = 'partner'")


def downgrade() -> None:
    op.drop_column("users", "partner_status")
