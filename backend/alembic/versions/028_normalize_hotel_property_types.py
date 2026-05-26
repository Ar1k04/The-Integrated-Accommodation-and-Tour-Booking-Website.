"""Normalize partner hotel property_type values to LiteAPI-compatible slugs.

Revision ID: 028
Revises: 027
Create Date: 2026-05-26

Partner-created hotels previously used singular slugs ('hotel', 'resort',
'apartment', 'villa', 'hostel'), which never matched the unified hotel-type
filter that sends LiteAPI's plural slugs ('hotels', 'resorts', 'apartments',
'hostels'). This migration normalizes existing rows so partner and LiteAPI
hotels share the same filter vocabulary.

Mappings:
    hotel     -> hotels
    resort    -> resorts
    apartment -> apartments
    villa     -> residences   (no exact LiteAPI equivalent)
    hostel    -> hostels
"""
from alembic import op


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE hotels SET property_type = CASE property_type
            WHEN 'hotel' THEN 'hotels'
            WHEN 'resort' THEN 'resorts'
            WHEN 'apartment' THEN 'apartments'
            WHEN 'villa' THEN 'residences'
            WHEN 'hostel' THEN 'hostels'
            ELSE property_type
        END
        WHERE property_type IN ('hotel', 'resort', 'apartment', 'villa', 'hostel')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE hotels SET property_type = CASE property_type
            WHEN 'hotels' THEN 'hotel'
            WHEN 'resorts' THEN 'resort'
            WHEN 'apartments' THEN 'apartment'
            WHEN 'residences' THEN 'villa'
            WHEN 'hostels' THEN 'hostel'
            ELSE property_type
        END
        """
    )
