"""Sync LiteAPI countries into our local Postgres `countries` table.

Cities used to be sourced from LiteAPI here too, but `/data/cities` turned out
to be a noisy gazetteer (wards, hamlets, train-stations, duplicate spellings).
We replaced it with a hybrid source — see `scripts.load_simplemaps_vn` (VN) and
`scripts.load_geonames` (global). This script now only refreshes the countries
table, which LiteAPI does serve cleanly and which other LiteAPI calls reference
by ISO-2 code.

Usage:
    docker exec travel_backend python -m scripts.sync_liteapi_locations
"""
import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.country import Country
from app.services import liteapi_service

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sync_liteapi_locations")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def upsert_countries(db: AsyncSession) -> int:
    rows = await liteapi_service.fetch_countries()
    if not rows:
        logger.warning("LiteAPI returned 0 countries — skipping.")
        return 0

    stmt = pg_insert(Country).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Country.code],
        set_={"name": stmt.excluded.name},
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("Upserted %d countries.", len(rows))
    return len(rows)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await upsert_countries(db)


if __name__ == "__main__":
    asyncio.run(main())
