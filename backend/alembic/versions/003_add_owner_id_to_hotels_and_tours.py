"""add owner_id to hotels and tours

Revision ID: 003
Revises: 002
Create Date: 2026-03-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotels", sa.Column("owner_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_hotels_owner_id", "hotels", ["owner_id"])
    op.create_foreign_key("fk_hotels_owner_id", "hotels", "users", ["owner_id"], ["id"], ondelete="SET NULL")

    op.add_column("tours", sa.Column("owner_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_tours_owner_id", "tours", ["owner_id"])
    op.create_foreign_key("fk_tours_owner_id", "tours", "users", ["owner_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_tours_owner_id", "tours", type_="foreignkey")
    op.drop_index("ix_tours_owner_id", table_name="tours")
    op.drop_column("tours", "owner_id")

    op.drop_constraint("fk_hotels_owner_id", "hotels", type_="foreignkey")
    op.drop_index("ix_hotels_owner_id", table_name="hotels")
    op.drop_column("hotels", "owner_id")
