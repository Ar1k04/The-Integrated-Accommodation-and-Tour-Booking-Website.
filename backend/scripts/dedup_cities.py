"""Collapse duplicate cities that differ only by accent/spacing/punctuation.

LiteAPI's /data/cities returns the same place under multiple spellings
("Da Nang" + "Da-Nang" + "Đà Nẵng", "Ha Noi" + "Hanoi", "Sa Pa" + "Sapa").
The dedup key is the unaccented name with all non-alphanumeric chars removed
(spaces, hyphens, punctuation), so every such variant collapses to one key.
This keeps ONE representative per (country_code, key) — preferring the row
that has hotels, then the most-accented spelling, then one with coordinates —
and deletes the rest.

Idempotent. Runs standalone, and also at the tail of
sync_liteapi_locations so re-syncs self-clean.

Usage:
    docker exec travel_backend python -m scripts.dedup_cities
"""
import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dedup_cities")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_DEDUP_SQL = text(
    """
    WITH ranked AS (
        SELECT id,
            ROW_NUMBER() OVER (
                -- key: unaccented, lowercased, stripped of spaces & punctuation
                -- so "Ha Noi"/"Hanoi" and "Da-Nang"/"Đà Nẵng" share a bucket
                PARTITION BY country_code, regexp_replace(name_norm, '[^a-z0-9]', '', 'g')
                ORDER BY
                    hotel_count DESC,
                    -- most accented spelling wins (count non-ASCII chars)
                    (char_length(name) - char_length(regexp_replace(name, '[^[:ascii:]]', '', 'g'))) DESC,
                    (latitude IS NOT NULL) DESC,
                    id ASC
            ) AS rn
        FROM cities
    )
    DELETE FROM cities WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
    """
)


async def dedup_cities(db: AsyncSession) -> int:
    """Delete accent/romanization duplicate city rows. Returns rows removed."""
    result = await db.execute(_DEDUP_SQL)
    await db.commit()
    return result.rowcount or 0


async def main() -> None:
    async with AsyncSessionLocal() as db:
        n = await dedup_cities(db)
        logger.info("Removed %d duplicate city rows (accent/romanization variants).", n)


if __name__ == "__main__":
    asyncio.run(main())
