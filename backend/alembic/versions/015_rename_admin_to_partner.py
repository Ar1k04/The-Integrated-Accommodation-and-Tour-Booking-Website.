"""Rename user roles: admin -> partner, superadmin -> admin.

Aligns role names with the project proposal:
  Guest / Customer / Partner (hotel-tour owners) / Admin (platform admin)

Revision ID: 015
Revises: 014
Create Date: 2026-04-27
"""
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE users SET role = CASE
            WHEN role = 'superadmin' THEN 'admin'
            WHEN role = 'admin'      THEN 'partner'
            ELSE role
        END
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE users SET role = CASE
            WHEN role = 'admin'   THEN 'superadmin'
            WHEN role = 'partner' THEN 'admin'
            ELSE role
        END
    """)
