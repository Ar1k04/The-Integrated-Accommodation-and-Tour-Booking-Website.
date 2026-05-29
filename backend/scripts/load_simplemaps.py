"""Load all cities (global) from the SimpleMaps World Cities (basic, free) CSV.

User downloads the CSV manually from https://simplemaps.com/data/world-cities
(versioned filename makes scripted download fragile) and places `worldcities.csv`
under `backend/data/`. This loader reads the whole file, filters to rows whose
country code exists in our `countries` table (skips Kosovo/Curaçao/etc. that
LiteAPI doesn't provide), and upserts into `cities` with provenance
`external_id = "sm:<id>"`.

Idempotent. Re-running upserts existing rows by `external_id`.

Usage:
    docker exec travel_backend python -m scripts.load_simplemaps \
        --csv backend/data/worldcities.csv

Attribution required by SimpleMaps license (CC BY 4.0).
"""
import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.city import City

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("load_simplemaps")

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_CHUNK = 1000


def _row_to_city(row: dict) -> dict:
    """Map one SimpleMaps CSV row → cities table dict."""
    capital = (row.get("capital") or "").strip().lower()
    feature_code = "PPLC" if capital == "primary" else ("PPLA" if capital == "admin" else "PPL")

    name = (row["city"] or "").strip()
    ascii_name = (row.get("city_ascii") or "").strip()
    # Keep the ASCII form as an alias when it differs (e.g. "Cần Thơ"/"Can Tho",
    # "Köln"/"Koln"). The generated search_text already unaccents, but the alias
    # also lets trigram fuzzy match the romanization directly.
    alt = ascii_name if ascii_name and ascii_name != name else None

    try:
        population = int(float(row.get("population") or 0))
    except (TypeError, ValueError):
        population = 0
    try:
        lat = float(row["lat"]) if row.get("lat") else None
        lng = float(row["lng"]) if row.get("lng") else None
    except (TypeError, ValueError):
        lat = lng = None

    admin = (row.get("admin_name") or "").strip() or None
    iso2 = (row.get("iso2") or "").strip().upper()

    return {
        "external_id": f"sm:{row['id']}",
        "name": name,
        "country_code": iso2,
        "state": admin,
        "latitude": lat,
        "longitude": lng,
        "population": population,
        "source": "simplemaps",
        "feature_code": feature_code,
        "admin1": admin,
        "alt_names": alt,
    }


async def main(csv_path: Path) -> None:
    if not csv_path.exists():
        logger.error(
            "CSV not found: %s\n"
            "Download from https://simplemaps.com/data/world-cities (Basic, free)\n"
            "and place `worldcities.csv` at that path.",
            csv_path,
        )
        sys.exit(2)

    rows: list[dict] = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            iso2 = (r.get("iso2") or "").strip().upper()
            if len(iso2) == 2 and r.get("city") and r.get("id"):
                rows.append(_row_to_city(r))

    if not rows:
        logger.warning("CSV contained no usable rows — nothing to load.")
        return

    async with AsyncSessionLocal() as db:
        # Filter to country codes our `countries` table actually knows about.
        # SimpleMaps includes a few codes LiteAPI omits (XK Kosovo, etc.); we
        # skip those rather than inflate the country master list.
        result = await db.execute(text("SELECT code FROM countries"))
        valid_codes = {r[0] for r in result.all()}
        before = len(rows)
        rows = [r for r in rows if r["country_code"] in valid_codes]
        skipped = before - len(rows)
        if skipped:
            logger.warning(
                "Skipped %d cities whose country_code is not in `countries` (e.g. XK).",
                skipped,
            )

        total = 0
        for start in range(0, len(rows), _CHUNK):
            chunk = rows[start : start + _CHUNK]
            stmt = pg_insert(City).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=[City.external_id],
                set_={
                    "name": stmt.excluded.name,
                    "country_code": stmt.excluded.country_code,
                    "state": stmt.excluded.state,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "population": stmt.excluded.population,
                    "source": stmt.excluded.source,
                    "feature_code": stmt.excluded.feature_code,
                    "admin1": stmt.excluded.admin1,
                    "alt_names": stmt.excluded.alt_names,
                },
            )
            await db.execute(stmt)
            total += len(chunk)
            if total % 10000 == 0 or total == len(rows):
                logger.info("  upserted %d / %d", total, len(rows))
        await db.commit()
        logger.info("Upserted %d cities from SimpleMaps.", total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/worldcities.csv"),
        help="Path to SimpleMaps worldcities.csv (relative to /app inside the container).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.csv))
