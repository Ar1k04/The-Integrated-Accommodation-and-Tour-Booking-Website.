"""Local city autocomplete backed by the LiteAPI-synced cities table.

Algorithm: a single SQL query combining a prefix-anchored B-tree lookup
(text_pattern_ops on the unaccented lowercase name) with a GIN trigram
fallback for typo tolerance. Postgres plans this as BitmapOr across the
two indexes, returning in ~1–5 ms on 50k rows.

Ranking (composite, asc tier wins first):
  tier 0 — name_norm LIKE q%       (true prefix on the city name)
  tier 1 — search_text contains    (word-boundary inside city/state)
  tier 2 — trigram similarity      (fuzzy / typo)
Within the same tier, popular cities (hotel_count DESC) come first.

Fallback: if local returns 0 rows for queries ≥ 3 chars, proxies to
Nominatim live so we don't break for obscure villages outside LiteAPI's
dataset.
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.geocoding_service import search_cities_nominatim

router = APIRouter(prefix="/locations", tags=["Locations"])

_TRIGRAM_THRESHOLD = 0.3
_MAX_LIMIT = 20


@router.get("/autocomplete")
async def autocomplete_cities(
    response: Response,
    q: str = Query("", min_length=0, max_length=100),
    limit: int = Query(8, ge=1, le=_MAX_LIMIT),
    country_code: str | None = Query(None, min_length=2, max_length=2),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Returns up to `limit` city suggestions matching `q`.

    Response shape matches what the frontend expects from the legacy
    Nominatim helper: [{city, country, state, countryCode, latitude, longitude}].
    """
    query = (q or "").strip()
    if len(query) < 2:
        return []

    cc = country_code.upper() if country_code else None
    sql = text(
        """
        WITH params AS (
            SELECT f_unaccent(:q) AS qn,
                   set_limit(:threshold) AS _
        )
        SELECT
            c.name        AS city,
            co.name       AS country,
            c.state       AS state,
            c.country_code AS country_code,
            c.latitude    AS latitude,
            c.longitude   AS longitude,
            CASE
                WHEN c.name_norm   LIKE p.qn || '%'          THEN 0
                WHEN c.search_text LIKE '% ' || p.qn || '%'  THEN 1
                ELSE 2
            END AS tier,
            similarity(c.search_text, p.qn) AS sim
        FROM cities c
        JOIN countries co ON co.code = c.country_code
        CROSS JOIN params p
        WHERE ((:cc)::text IS NULL OR c.country_code = (:cc)::text)
          AND (
              c.name_norm   LIKE p.qn || '%'
              OR c.search_text LIKE '% ' || p.qn || '%'
              OR c.search_text % p.qn
          )
        ORDER BY tier ASC, c.hotel_count DESC, sim DESC, c.name ASC
        LIMIT :limit
        """
    )

    result = await db.execute(
        sql,
        {"q": query, "threshold": _TRIGRAM_THRESHOLD, "cc": cc, "limit": limit},
    )
    rows = result.mappings().all()

    items: list[dict] = [
        {
            "city": r["city"],
            "country": r["country"],
            "state": r["state"] or "",
            "countryCode": r["country_code"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
        }
        for r in rows
    ]

    # Fallback: only for queries with enough signal to avoid noisy OSM hits.
    if not items and len(query) >= 3:
        items = await search_cities_nominatim(query, limit=limit)

    # Browser/CDN cache identical autocomplete requests for 1h. Backend query
    # is so cheap (1–5ms) that hitting it again is fine — this mainly helps
    # repeat visitors and shared CDN tenants.
    response.headers["Cache-Control"] = "public, max-age=3600"
    return items
