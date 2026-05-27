"""Add countries and cities tables for fast local autocomplete.

Revision ID: 029
Revises: 028
Create Date: 2026-05-27

Replaces the slow Nominatim live autocomplete with a local Postgres-backed
search synced from LiteAPI (/data/countries + /data/cities). Installs the
pg_trgm and unaccent extensions, wraps unaccent in an IMMUTABLE helper so
it can be used in generated columns and indexes, and creates two reference
tables with prefix + trigram indexes for sub-5ms autocomplete on ~50k cities.
"""
import sqlalchemy as sa
from alembic import op


revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # IMMUTABLE wrapper so unaccent() can be used in generated columns / indexes.
    # The 2-arg form pins the dictionary, which makes the call deterministic.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION f_unaccent(text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS
        $$ SELECT lower(public.unaccent('public.unaccent', $1)) $$
        """
    )

    op.create_table(
        "countries",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("code", sa.CHAR(2), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "name_norm",
            sa.Text(),
            sa.Computed("f_unaccent(name)", persisted=True),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="uq_countries_code"),
    )
    op.create_index("ix_countries_code", "countries", ["code"], unique=True)

    op.create_table(
        "cities",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("liteapi_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "country_code",
            sa.CHAR(2),
            sa.ForeignKey("countries.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("hotel_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "name_norm",
            sa.Text(),
            sa.Computed("f_unaccent(name)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "search_text",
            sa.Text(),
            sa.Computed(
                "f_unaccent(name) || ' ' || COALESCE(f_unaccent(state), '')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.UniqueConstraint("liteapi_id", name="uq_cities_liteapi_id"),
    )

    # Prefix index on the normalized name — "ha" → "Hanoi" via text_pattern_ops.
    op.execute(
        "CREATE INDEX ix_cities_name_norm_prefix ON cities (name_norm text_pattern_ops)"
    )
    # GIN trigram index for typo-tolerant fallback ("hanio" → "hanoi").
    op.execute(
        "CREATE INDEX ix_cities_search_text_trgm ON cities USING gin (search_text gin_trgm_ops)"
    )
    op.create_index("ix_cities_country_code", "cities", ["country_code"])
    op.create_index(
        "ix_cities_hotel_count",
        "cities",
        [sa.text("hotel_count DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_cities_hotel_count", table_name="cities")
    op.drop_index("ix_cities_country_code", table_name="cities")
    op.execute("DROP INDEX IF EXISTS ix_cities_search_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_cities_name_norm_prefix")
    op.drop_table("cities")
    op.drop_index("ix_countries_code", table_name="countries")
    op.drop_table("countries")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
    # Leave extensions installed — they're cheap and may be used elsewhere.
