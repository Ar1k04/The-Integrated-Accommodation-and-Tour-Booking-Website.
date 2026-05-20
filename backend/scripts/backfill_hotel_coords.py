"""One-shot script to geocode and fill latitude/longitude on partner hotels
that were created without explicit coordinates.

Usage (Docker):
    docker exec travel_backend python -m scripts.backfill_hotel_coords

Idempotent — only processes rows where either lat or lng is NULL. Respects
Nominatim's 1 req/s rate limit.
"""
import asyncio
import logging
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.hotel import Hotel
from app.services.geocoding_service import geocode_address

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backfill_hotel_coords")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Hotel).where(or_(Hotel.latitude.is_(None), Hotel.longitude.is_(None)))
        )
        hotels = result.scalars().all()
        total = len(hotels)
        if not total:
            logger.info("Nothing to backfill — all hotels already have coordinates.")
            return

        logger.info("Geocoding %d hotels (≈1 req/s, ~%ds total)…", total, total)
        ok = 0
        skipped = 0
        for i, hotel in enumerate(hotels, 1):
            if not (hotel.address or hotel.city or hotel.country):
                skipped += 1
                continue
            coords = await geocode_address(hotel.address, hotel.city, hotel.country)
            if coords:
                hotel.latitude, hotel.longitude = coords
                await db.commit()
                ok += 1
                logger.info("  [%d/%d] %s → %.4f,%.4f", i, total, hotel.name, *coords)
            else:
                logger.info("  [%d/%d] %s → no result", i, total, hotel.name)
            await asyncio.sleep(1.1)  # Nominatim rate limit

        logger.info("Done. geocoded %d/%d (%d skipped: no address)", ok, total, skipped)


if __name__ == "__main__":
    asyncio.run(main())
