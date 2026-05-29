"""Full reload sequence for the cities dataset.

Runs, in order:
  1. load_simplemaps  — global cities from SimpleMaps CSV (user-provided)
  2. refresh_city_hotel_count — recompute hotel_count ranking signal

Assumes migration 030 has been applied (which TRUNCATEd the table). Aborts
early if the SimpleMaps CSV is missing so we never end up with an empty table.

Usage:
    docker exec travel_backend python -m scripts.reload_cities \
        --csv backend/data/worldcities.csv
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from scripts import load_simplemaps
from scripts.refresh_city_hotel_count import main as refresh_main

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("reload_cities")


async def main(csv_path: Path) -> None:
    if not csv_path.exists():
        logger.error(
            "Aborting: SimpleMaps CSV not found at %s. Download from "
            "https://simplemaps.com/data/world-cities and place the CSV there "
            "BEFORE running this script (otherwise the table stays empty).",
            csv_path,
        )
        sys.exit(2)

    logger.info("==> Step 1/2: SimpleMaps")
    await load_simplemaps.main(csv_path)

    logger.info("==> Step 2/2: refresh hotel_count ranking")
    await refresh_main()

    logger.info("==> Reload complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/worldcities.csv"))
    args = parser.parse_args()
    asyncio.run(main(args.csv))
