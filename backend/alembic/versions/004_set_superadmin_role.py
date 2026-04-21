"""set superadmin role for longco6868@gmail.com

Revision ID: 004
Revises: 003
Create Date: 2026-03-31

"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUPERADMIN_EMAIL = "longco6868@gmail.com"


def upgrade() -> None:
    op.execute(
        f"UPDATE users SET role = 'superadmin' WHERE email = '{SUPERADMIN_EMAIL}'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE users SET role = 'admin' WHERE email = '{SUPERADMIN_EMAIL}' AND role = 'superadmin'"
    )
