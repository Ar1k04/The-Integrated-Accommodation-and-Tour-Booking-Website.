"""Replace LiteAPI-sourced cities with hybrid SimpleMaps (VN) + GeoNames (global).

Revision ID: 030
Revises: 029
Create Date: 2026-05-29

LiteAPI /data/cities was a noisy gazetteer (wards, hamlets, train stations,
duplicate spellings, no coords). Replaced with:
  - SimpleMaps World Cities (basic) — VN cities only (~187 curated rows)
  - GeoNames cities5000 — non-VN cities (~50k clean cities, population ≥ 5000)

This migration repurposes `liteapi_id` → `external_id` (kept as UNIQUE natural
key for upsert, now with provenance prefix `sm:<id>` or `gn:<geonameid>`),
TRUNCATEs existing data (loaders below will repopulate), adds new columns,
and rebuilds the generated `search_text` to include admin1 + alt_names so
trigram matching can also match "Île-de-France" or "서울" or city aliases.
"""
import sqlalchemy as sa
from alembic import op


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Wipe existing 148k LiteAPI rows. Loaders repopulate from new sources.
    op.execute("TRUNCATE TABLE cities")

    # 2. Repurpose liteapi_id as a generic external_id with provenance prefix
    op.execute("ALTER TABLE cities RENAME COLUMN liteapi_id TO external_id")
    op.execute("ALTER TABLE cities RENAME CONSTRAINT uq_cities_liteapi_id TO uq_cities_external_id")

    # 3. New columns
    op.add_column("cities", sa.Column("source", sa.Text(), nullable=False, server_default="legacy"))
    op.add_column(
        "cities",
        sa.Column("population", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("cities", sa.Column("feature_code", sa.Text(), nullable=True))
    op.add_column("cities", sa.Column("admin1", sa.Text(), nullable=True))
    op.add_column("cities", sa.Column("alt_names", sa.Text(), nullable=True))

    # 4. Rebuild generated search_text to include admin1 + alt_names.
    #    Must drop the dependent GIN trigram index first, then the column.
    op.execute("DROP INDEX IF EXISTS ix_cities_search_text_trgm")
    op.drop_column("cities", "search_text")
    op.execute(
        """
        ALTER TABLE cities ADD COLUMN search_text TEXT
        GENERATED ALWAYS AS (
            f_unaccent(name) || ' ' ||
            COALESCE(f_unaccent(admin1), '') || ' ' ||
            COALESCE(f_unaccent(alt_names), '')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_cities_search_text_trgm ON cities USING gin (search_text gin_trgm_ops)"
    )

    # 5. New population ranking index
    op.execute("CREATE INDEX ix_cities_population ON cities (population DESC)")

    # 6. Drop the server_default on source after backfill — loaders set it explicitly.
    op.alter_column("cities", "source", server_default=None)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cities_population")
    op.execute("DROP INDEX IF EXISTS ix_cities_search_text_trgm")
    op.drop_column("cities", "search_text")
    op.drop_column("cities", "alt_names")
    op.drop_column("cities", "admin1")
    op.drop_column("cities", "feature_code")
    op.drop_column("cities", "population")
    op.drop_column("cities", "source")
    op.execute("ALTER TABLE cities RENAME CONSTRAINT uq_cities_external_id TO uq_cities_liteapi_id")
    op.execute("ALTER TABLE cities RENAME COLUMN external_id TO liteapi_id")
    op.execute(
        """
        ALTER TABLE cities ADD COLUMN search_text TEXT
        GENERATED ALWAYS AS (
            f_unaccent(name) || ' ' || COALESCE(f_unaccent(state), '')
        ) STORED
        """
    )
    op.execute(
        "CREATE INDEX ix_cities_search_text_trgm ON cities USING gin (search_text gin_trgm_ops)"
    )
