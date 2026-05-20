"""Best-effort address → (lat, lng) geocoding via Nominatim (OpenStreetMap).

Used when a partner hotel is created/updated without explicit coordinates so it
can still appear on map views. Result is cached by writing the resolved
lat/lng back into the `hotels` row — we never re-geocode the same hotel.

Nominatim ToS: ≤1 req/s, identifying User-Agent. Fine for sandbox/dev; in
production swap to LocationIQ or Mapbox if volume grows.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {
    "User-Agent": "TravelBookingApp/1.0 (longbao12082004@gmail.com)",
    "Accept": "application/json",
}


async def geocode_address(
    address: str | None, city: str | None, country: str | None
) -> tuple[float, float] | None:
    """Resolve `address, city, country` → (lat, lng). Falls back to just
    `city, country` if the full string fails. Returns None on any error or
    when nothing usable is provided."""
    if not (address or city or country):
        return None

    queries: list[str] = []
    if address and (city or country):
        queries.append(", ".join(p for p in [address, city, country] if p))
    if city or country:
        queries.append(", ".join(p for p in [city, country] if p))

    async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
        for q in queries:
            try:
                resp = await client.get(
                    NOMINATIM_URL,
                    params={"q": q, "format": "json", "limit": 1},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"])
            except Exception as exc:
                logger.debug("geocode attempt failed for %r: %s", q, exc)
                continue
    return None
