"""Homepage "featured" feed.

Serves the hotels and tours shown on the landing page. It blends two sources:

* **External top-rated** — top hotels (LiteAPI) and tours (Viator). Both
  providers only expose ratings *per destination* (no global "top rated"), so we
  sample a small curated set of popular destinations, merge, and keep the
  highest-rated few. This part is **cached permanently** in Redis (no TTL) under
  one key — it's expensive and rate-limited, and rarely changes. Rebuild with
  ``?refresh=true``. A Redis lock dedupes concurrent cold-cache rebuilds.
* **Partner hotels** — our own local-DB (partner-owned) inventory, fetched
  **live from Postgres on every request** so newly added partner hotels appear
  immediately and aren't frozen by the permanent cache. These carry their own
  nightly price; LiteAPI hotels ship priceless and the frontend fills in a price
  for the current date via ``/hotels/min-rates``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.routes.hotels import _hotel_response, _liteapi_hotel_to_response
from app.api.v1.routes.tours import _viator_tour_to_response
from app.db.session import get_db
from app.models.hotel import Hotel
from app.models.room import Room
from app.services import liteapi_service, viator_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/featured", tags=["Featured"])

_FEATURED_CACHE_KEY = "featured:home:v1"
# No TTL: the feed is cached permanently so it never reloads on its own. Rebuild
# explicitly with `?refresh=true` (or by deleting the Redis key). Redis persists
# the value across restarts via the redis_data volume.
_FEATURED_LOCK_TTL = 60         # cold-rebuild lock; a full sample is a few seconds
_TOP_N = 5                      # external items kept per section
_LOCAL_HOTEL_N = 4              # partner (local-DB) hotels shown alongside LiteAPI

# Curated destinations sampled to build each feed. Hotels need (country_code,
# city) exactly as LiteAPI knows them; tours resolve a Viator destination by
# name. Kept short so a cold rebuild stays within a handful of upstream calls.
_HOTEL_DESTINATIONS = [
    ("JP", "Tokyo"),
    ("FR", "Paris"),
    ("TH", "Bangkok"),
    ("VN", "Hanoi"),
]
_TOUR_DESTINATIONS = ["Tokyo", "Paris", "Bangkok", "Hanoi"]

_PER_DEST_LIMIT = 10            # fetched per destination before trimming to _TOP_N
_VIATOR_GAP_SECONDS = 0.5       # spacing between sequential Viator calls (avoids 429)
_RATES_DAY_TTL = 86_400         # 24h — see _get_today_rates (key is per calendar day)


def _rank_key(item: dict) -> tuple[float, int]:
    """Sort key: highest rating first, break ties by review volume."""
    return (float(item.get("avg_rating") or 0), int(item.get("total_reviews") or 0))


async def _fetch_top_hotels() -> list[dict]:
    async def one(cc: str, city: str) -> list[dict]:
        try:
            hotels, _ = await liteapi_service.search_hotels(
                country_code=cc, city=city, limit=_PER_DEST_LIMIT,
            )
            return hotels
        except Exception as exc:  # noqa: BLE001 — one bad destination must not sink the feed
            logger.warning("featured: LiteAPI fetch failed for %s/%s: %s", cc, city, exc)
            return []

    results = await asyncio.gather(*(one(cc, city) for cc, city in _HOTEL_DESTINATIONS))

    merged: dict[str, dict] = {}
    for hotels in results:
        for h in hotels:
            hid = h.get("liteapi_hotel_id")
            if hid and hid not in merged:
                merged[hid] = h

    ranked = sorted(merged.values(), key=_rank_key, reverse=True)[:_TOP_N]
    return [_liteapi_hotel_to_response(h).model_dump(mode="json") for h in ranked]


async def _fetch_top_tours() -> list[dict]:
    # Viator has no client-side throttle here and rate-limits bursts, so we walk
    # destinations sequentially with a short gap. This only runs on a cold cache
    # (once / 24h), so the few extra seconds are invisible to users.
    merged: dict[str, dict] = {}
    for i, city in enumerate(_TOUR_DESTINATIONS):
        if i:
            await asyncio.sleep(_VIATOR_GAP_SECONDS)
        try:
            res = await viator_service.search_tours(
                city=city, sort="TRAVELER_RATING", count=_PER_DEST_LIMIT,
            )
            products = res.get("products") or []
        except Exception as exc:  # noqa: BLE001 — one bad destination must not sink the feed
            logger.warning("featured: Viator fetch failed for %s: %s", city, exc)
            continue
        for p in products:
            code = p.get("viator_product_code")
            if code and code not in merged:
                merged[code] = p

    ranked = sorted(merged.values(), key=_rank_key, reverse=True)[:_TOP_N]
    return [_viator_tour_to_response(p).model_dump(mode="json") for p in ranked]


async def _fetch_local_hotels(db: AsyncSession) -> list[dict]:
    """Top partner (local-DB) hotels by rating, each with its min nightly price.

    Fetched live (not cached) so newly onboarded partner hotels show up at once.
    """
    room_price_subq = (
        select(
            Room.hotel_id.label("hotel_id"),
            func.min(Room.price_per_night).label("min_room_price"),
        )
        .group_by(Room.hotel_id)
        .subquery()
    )
    query = (
        select(Hotel, room_price_subq.c.min_room_price)
        .outerjoin(room_price_subq, Hotel.id == room_price_subq.c.hotel_id)
        .order_by(Hotel.avg_rating.desc(), Hotel.total_reviews.desc())
        .limit(_LOCAL_HOTEL_N)
    )
    try:
        rows = (await db.execute(query)).all()
    except Exception as exc:  # noqa: BLE001 — DB hiccup must not sink the whole feed
        logger.warning("featured: local hotel fetch failed: %s", exc)
        return []
    return [
        _hotel_response(hotel, float(mp) if mp is not None else None).model_dump(mode="json")
        for hotel, mp in rows
    ]


async def _build_external_feed() -> dict:
    """The expensive, cacheable half: LiteAPI hotels + Viator tours."""
    hotels, tours = await asyncio.gather(_fetch_top_hotels(), _fetch_top_tours())
    return {"hotels": hotels, "tours": tours}


async def _persist_feed(redis, feed: dict) -> None:
    """Cache the external feed permanently (no TTL) — but only when it has
    content, so a transient upstream outage never freezes an empty feed forever."""
    if redis is None or not (feed.get("hotels") or feed.get("tours")):
        return
    try:
        await redis.set(_FEATURED_CACHE_KEY, json.dumps(feed))
    except Exception:  # noqa: BLE001
        pass


async def _get_external_feed(redis, refresh: bool) -> dict:
    """Read the permanent external feed from Redis, or (re)build + persist it."""
    if redis is not None and not refresh:
        try:
            cached = await redis.get(_FEATURED_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception:  # noqa: BLE001 — read failure falls through to a live build
            pass

    if redis is not None and not refresh:
        # Cold cache: take a short lock so concurrent first-hits don't all rebuild.
        lock_key = f"{_FEATURED_CACHE_KEY}:lock"
        got_lock = await redis.set(lock_key, "1", nx=True, ex=_FEATURED_LOCK_TTL)
        if not got_lock:
            # Another request is rebuilding — briefly wait for it to publish.
            for _ in range(20):
                await asyncio.sleep(0.25)
                cached = await redis.get(_FEATURED_CACHE_KEY)
                if cached:
                    return json.loads(cached)
        try:
            feed = await _build_external_feed()
            await _persist_feed(redis, feed)
            return feed
        finally:
            try:
                await redis.delete(lock_key)
            except Exception:  # noqa: BLE001
                pass

    # No Redis (or forced refresh): build live, then persist on forced refresh.
    feed = await _build_external_feed()
    if refresh:
        await _persist_feed(redis, feed)
    return feed


def _resolve_rate_date(raw: str | None) -> date:
    """The check-in date to price for — the *viewer's* local "today".

    The server runs UTC, but a check-in date is a calendar date in the user's own
    zone (like Booking.com / Traveloka), so the frontend sends its local date.
    We clamp to ±1 day of UTC today: that's the full range any real timezone can
    differ by, and it stops a stray/abusive value from spawning unbounded cache
    keys or pricing nonsensical dates. Missing/invalid → UTC today.
    """
    today = date.today()
    if not raw:
        return today
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        return today
    if d < today - timedelta(days=1) or d > today + timedelta(days=1):
        return today
    return d


async def _get_today_rates(redis, liteapi_ids: list[str], rate_date: date) -> dict[str, float]:
    """Min nightly prices for LiteAPI hotels, for ``rate_date`` check-in (1 night).

    Cached under a per-day key (``featured:rates:<YYYY-MM-DD>``) for 24h. Because
    the date is in the key, each new day misses → fetches that day's rate → caches
    it for the whole day. Yesterday's key just ages out untouched.
    """
    if not liteapi_ids:
        return {}
    cache_key = f"featured:rates:{rate_date.isoformat()}"

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:  # noqa: BLE001 — fall through to a live fetch
            pass

    try:
        rates = await liteapi_service.get_min_rates_batch(
            liteapi_ids, rate_date, rate_date + timedelta(days=1), 1,
        )
    except Exception as exc:  # noqa: BLE001 — no price is better than a 500
        logger.warning("featured: rate fetch failed for %s: %s", rate_date, exc)
        rates = {}

    if redis is not None and rates:
        try:
            await redis.set(cache_key, json.dumps(rates), ex=_RATES_DAY_TTL)
        except Exception:  # noqa: BLE001
            pass
    return rates


def _apply_rates(hotels: list[dict], rates: dict[str, float]) -> None:
    """Fill ``min_room_price`` on priceless LiteAPI hotels from the rate map."""
    for h in hotels:
        if h.get("min_room_price") is None:
            price = rates.get(h.get("liteapi_hotel_id") or "")
            if price:
                h["min_room_price"] = price
                if not h.get("base_price"):
                    h["base_price"] = price


def _merge_hotels(local: list[dict], external: list[dict]) -> list[dict]:
    """Partner hotels first, then LiteAPI — de-duped by LiteAPI id so a partner
    row linked to a LiteAPI property isn't shown twice."""
    seen = {h["liteapi_hotel_id"] for h in local if h.get("liteapi_hotel_id")}
    merged = list(local)
    for h in external:
        if h.get("liteapi_hotel_id") and h["liteapi_hotel_id"] in seen:
            continue
        merged.append(h)
    return merged


@router.get("/home")
async def featured_home(
    request: Request,
    db: AsyncSession = Depends(get_db),
    refresh: bool = Query(False),
    rate_date: str | None = Query(
        None, description="Viewer's local date (YYYY-MM-DD) to price LiteAPI hotels for"
    ),
):
    """Featured hotels + tours for the landing page.

    Tours and the LiteAPI hotels come from a permanent Redis cache (rebuild with
    ``?refresh=true``). Partner (local-DB) hotels are fetched live and listed
    first. LiteAPI hotels carry no price of their own, so we attach the rate for
    ``rate_date`` (the viewer's local today), cached for that whole day — the next
    day fetches the next day's rate.
    """
    redis = getattr(request.app.state, "redis", None)
    external = await _get_external_feed(redis, refresh)
    local_hotels = await _fetch_local_hotels(db)
    hotels = _merge_hotels(local_hotels, external.get("hotels") or [])

    liteapi_ids = [
        h["liteapi_hotel_id"]
        for h in hotels
        if h.get("min_room_price") is None and h.get("liteapi_hotel_id")
    ]
    rates = await _get_today_rates(redis, liteapi_ids, _resolve_rate_date(rate_date))
    _apply_rates(hotels, rates)

    return {"hotels": hotels, "tours": external.get("tours") or []}
