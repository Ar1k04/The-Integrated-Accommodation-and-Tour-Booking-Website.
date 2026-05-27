"""Refresh `cities.hotel_count` from the live hotels table.

Drives the ranking signal for autocomplete — without it, "Paris, FR" loses
to "Paris, TX" alphabetically. Joins on the unaccented lowercase city name
+ country code (resolved via the countries table) so that "Ha Noi" and
"Hà Nội" map to the same row.

Run nightly via cron, ideally right after sync_liteapi_locations.
Idempotent.

Usage:
    docker exec travel_backend python -m scripts.refresh_city_hotel_count
"""
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("refresh_city_hotel_count")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Reset everything to 0 first so cities that lost all hotels drop in rank.
        await db.execute(text("UPDATE cities SET hotel_count = 0"))

        # Aggregate hotels by (normalized city name, country code) — match the
        # hotels.country column against countries.name (case + diacritic insensitive)
        # to resolve to a 2-letter code, then join to cities by name_norm + code.
        result = await db.execute(
            text(
                """
                WITH hotel_agg AS (
                    SELECT
                        f_unaccent(h.city) AS city_norm,
                        co.code            AS country_code,
                        COUNT(*)           AS cnt
                    FROM hotels h
                    JOIN countries co
                      -- Space-insensitive so "Vietnam" matches LiteAPI's
                      -- "Viet Nam"; also accept a raw 2-letter code.
                      ON replace(f_unaccent(co.name), ' ', '') = replace(f_unaccent(h.country), ' ', '')
                      OR co.code = UPPER(h.country)
                    GROUP BY 1, 2
                )
                UPDATE cities c
                   SET hotel_count = ha.cnt
                  FROM hotel_agg ha
                 WHERE c.name_norm = ha.city_norm
                   AND c.country_code = ha.country_code
                """
            )
        )
        await db.commit()
        logger.info("Refreshed hotel_count for %d city rows.", result.rowcount or 0)


if __name__ == "__main__":
    asyncio.run(main())
