"""Sync LiteAPI countries + cities into our local Postgres tables.

Idempotent: re-running it upserts by `code` (countries) and `liteapi_id`
(cities). Expected first-time cost: ~250 country requests, ~30k–50k city
rows, 5–10 minutes total wall-clock.

Usage:
    docker exec travel_backend python -m scripts.sync_liteapi_locations
    docker exec travel_backend python -m scripts.sync_liteapi_locations --countries VN,TH,JP

Optional --countries flag restricts the city pull to a comma-separated list
of ISO-2 codes (useful for quick re-sync of just one region).
"""
import argparse
import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.city import City
from app.models.country import Country
from app.services import liteapi_service
from scripts.dedup_cities import dedup_cities

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sync_liteapi_locations")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Gentle throttle to stay well under LiteAPI's rate limits (10 req/s).
_THROTTLE_SEC = 0.1

# Rows per INSERT — keeps bind-param count (8/row) under Postgres' 65535 cap.
_INSERT_CHUNK = 1000


async def upsert_countries(db: AsyncSession) -> list[str]:
    rows = await liteapi_service.fetch_countries()
    if not rows:
        logger.warning("LiteAPI returned 0 countries — skipping.")
        return []

    stmt = pg_insert(Country).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Country.code],
        set_={"name": stmt.excluded.name},
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("Upserted %d countries.", len(rows))
    return [r["code"] for r in rows]


async def upsert_cities_for_country(db: AsyncSession, country_code: str) -> int:
    rows = await liteapi_service.fetch_cities(country_code)
    if not rows:
        return 0

    # Dedupe by liteapi_id within the batch — Postgres ON CONFLICT DO UPDATE
    # rejects the same conflict target appearing twice in one statement
    # ("cannot affect row a second time"). LiteAPI returns duplicate city names
    # in some countries, which collide on our "CC|name" fallback id.
    deduped = {r["liteapi_id"]: r for r in rows}
    rows = list(deduped.values())

    # Chunk inserts: each row binds 8 params, and Postgres caps a statement at
    # 65535 bind parameters. Large countries (US, FR, GB) have >8k cities, so a
    # single INSERT would overflow. 1000 rows/statement (8k params) stays safe.
    for start in range(0, len(rows), _INSERT_CHUNK):
        chunk = rows[start : start + _INSERT_CHUNK]
        stmt = pg_insert(City).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=[City.liteapi_id],
            set_={
                "name": stmt.excluded.name,
                "country_code": stmt.excluded.country_code,
                "state": stmt.excluded.state,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
            },
        )
        await db.execute(stmt)
    await db.commit()
    return len(rows)


async def main(restrict_codes: list[str] | None = None) -> None:
    async with AsyncSessionLocal() as db:
        all_codes = await upsert_countries(db)
        if not all_codes:
            return

        codes = (
            [c for c in all_codes if c in {x.upper() for x in restrict_codes}]
            if restrict_codes
            else all_codes
        )
        total_cities = 0
        ok_countries = 0
        for i, code in enumerate(codes, 1):
            try:
                n = await upsert_cities_for_country(db, code)
                total_cities += n
                if n > 0:
                    ok_countries += 1
                logger.info("  [%d/%d] %s → %d cities", i, len(codes), code, n)
            except Exception as exc:
                # Roll back the aborted transaction so a single bad country
                # doesn't poison every subsequent upsert on this session.
                await db.rollback()
                logger.warning("  [%d/%d] %s → failed: %s", i, len(codes), code, exc)
            await asyncio.sleep(_THROTTLE_SEC)

        logger.info(
            "Done. %d cities across %d countries (of %d requested).",
            total_cities,
            ok_countries,
            len(codes),
        )

        # Collapse accent/romanization duplicates LiteAPI returns ("Da Nang"
        # vs "Đà Nẵng") so re-syncs stay self-clean.
        removed = await dedup_cities(db)
        logger.info("Deduped %d accent/romanization variant rows.", removed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--countries",
        type=str,
        default=None,
        help="Comma-separated ISO-2 codes to restrict the city sync to (e.g. VN,TH,JP).",
    )
    args = parser.parse_args()
    restrict = [c.strip() for c in args.countries.split(",")] if args.countries else None
    asyncio.run(main(restrict))
