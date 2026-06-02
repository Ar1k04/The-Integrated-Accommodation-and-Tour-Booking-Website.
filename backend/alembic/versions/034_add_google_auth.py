"""Add Google OAuth support to users (google_id, nullable password).

Revision ID: 034
Revises: 033
Create Date: 2026-06-02

Adds "Login with Google". A Google-only account has no local password, so
``hashed_password`` becomes nullable, and ``google_id`` stores the Google
``sub`` claim (unique, indexed) so repeat logins resolve to the same user.
Email/password accounts keep ``hashed_password`` set and ``google_id`` NULL.
"""
import sqlalchemy as sa
from alembic import op


revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_id", sa.String(length=255), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Password-only accounts are unaffected; Google-only accounts (NULL password)
    # would block re-adding NOT NULL, so backfill an empty placeholder first.
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "google_id")
