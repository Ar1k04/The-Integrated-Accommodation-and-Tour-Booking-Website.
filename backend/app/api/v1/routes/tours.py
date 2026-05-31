import asyncio
import hashlib
import json
import logging
import math
import re
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import StaffUser, CurrentUser
from app.core.pricing import (
    AgeBandError,
    adult_band_price,
    compute_tour_subtotal,
    compute_tour_subtotal_from_bands,
    match_age_band,
)
from app.db.session import get_db
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.schemas.tour import (
    TourAgeBand,
    TourAvailabilityResponse,
    TourCreate,
    TourListResponse,
    TourResponse,
    TourUpdate,
    ViatorDestinationsResponse,
    ViatorTagsResponse,
)
from app.services import lock_service, viator_service
from app.services.lock_service import RedisUnavailableError
from app.services.viator_service import ViatorError, VIATOR_FLAGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tours", tags=["Tours"])

_VIATOR_CACHE_TTL = 300       # 5 minutes — full cache
_VIATOR_FAST_LIMIT = 30       # tours fetched for cold page-1 (≈ 1 page visible)
_VIATOR_FAST_CACHE_TTL = 60   # short — full cache supersedes it within seconds
_VIATOR_FULL_PAGE_SIZE = 50   # batch size when fetching full set (Viator max)
_VIATOR_FULL_HARD_CAP = 500   # safety ceiling so background fill terminates


def _tour_response(tour: Tour) -> TourResponse:
    data = TourResponse.model_validate(tour)
    data.source = "local"
    data.viator_product_code = tour.viator_product_code
    data.age_bands = (
        [TourAgeBand(**b) for b in tour.age_bands] if tour.age_bands else None
    )
    if tour.owner:
        data.owner_name = tour.owner.full_name
    return data


def _sync_price_to_adult_band(tour: Tour) -> None:
    """Keep ``price_per_person`` aligned with the ADULT band price so list
    cards, sorting, and price filters (which all read ``price_per_person``)
    stay consistent with the band a Partner defined."""
    if tour.age_bands:
        tour.price_per_person = float(
            adult_band_price(tour.age_bands, tour.price_per_person)
        )


def _viator_tour_to_response(raw: dict) -> TourResponse:
    return TourResponse(
        id=None,
        name=raw.get("name", ""),
        slug=None,
        description=raw.get("description"),
        city=raw.get("city", ""),
        country=raw.get("country"),
        category=raw.get("category"),
        duration_days=int(raw.get("duration_days") or 1),
        max_participants=int(raw.get("max_participants") or 20),
        price_per_person=float(raw.get("price_per_person") or 0),
        highlights=raw.get("highlights"),
        includes=raw.get("includes"),
        excludes=raw.get("excludes"),
        images=raw.get("images") or [],
        avg_rating=float(raw.get("avg_rating") or 0),
        total_reviews=int(raw.get("total_reviews") or 0),
        source="viator",
        viator_product_code=raw.get("viator_product_code"),
        age_bands=raw.get("age_bands") or None,
        destinations=raw.get("destinations") or None,
        departs_from=raw.get("departs_from") or None,
    )


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", slug).strip("-")


def _parse_child_ages_csv(raw: str | None) -> list[int]:
    """Parse `child_ages=11,8` query string into a clamped list of ints (0–17)."""
    if not raw:
        return []
    ages: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            age = int(chunk)
        except ValueError:
            continue
        if 0 <= age <= 17:
            ages.append(age)
    return ages


async def _get_cached(redis, key: str) -> list[dict] | None:
    if redis is None:
        return None
    try:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None


async def _set_cached(redis, key: str, data: list[dict] | dict, ttl: int | None = None) -> None:
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(data), ex=ttl or _VIATOR_CACHE_TTL)
    except Exception:
        pass


async def _get_cached_tour_block(redis, key: str) -> tuple[list[dict], int] | None:
    """Read a {products, total} cache entry. Returns None on miss / parse error."""
    if redis is None:
        return None
    try:
        cached = await redis.get(key)
        if not cached:
            return None
        obj = json.loads(cached)
        if not isinstance(obj, dict) or "products" not in obj:
            return None
        products = obj["products"] if isinstance(obj["products"], list) else []
        total = int(obj.get("total", len(products)))
        return products, total
    except Exception:
        return None


async def _set_cached_tour_block(
    redis, key: str, products: list[dict], total: int, ttl: int = _VIATOR_CACHE_TTL
) -> None:
    """Write a {products, total} cache entry. `total` is Viator's full match
    count (independent of how many we fetched), so the route can advertise a
    stable count even when serving the fast 30-tour preview."""
    if redis is None:
        return
    try:
        payload = {"products": products, "total": int(total)}
        await redis.set(key, json.dumps(payload), ex=ttl)
    except Exception:
        pass


async def _background_fill_full_viator_cache(
    redis,
    cache_key_full: str,
    viator_kwargs: dict,
    total_hint: int,
) -> None:
    """Fire-and-forget: fetch the full Viator product set (capped at
    _VIATOR_FULL_HARD_CAP) so page-2+ requests slice from Redis without
    hitting Viator. A Redis SET NX lock dedupes concurrent triggers."""
    if redis is None:
        return
    lock_key = f"{cache_key_full}:bg-lock"
    try:
        got_lock = await redis.set(lock_key, "1", nx=True, ex=60)
        if not got_lock:
            return
        existing = await redis.get(cache_key_full)
        if existing:
            return

        # If caller didn't have a total yet, fetch the first batch to learn it.
        all_products: list[dict] = []
        seen_codes: set[str] = set()
        total = int(total_hint or 0)

        if total <= 0:
            first = await viator_service.search_tours(
                **viator_kwargs, start=1, count=_VIATOR_FULL_PAGE_SIZE
            )
            total = int(first.get("total") or 0)
            for p in first.get("products") or []:
                code = p.get("viator_product_code")
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    all_products.append(p)
            next_start = _VIATOR_FULL_PAGE_SIZE + 1
        else:
            next_start = 1

        target = min(total, _VIATOR_FULL_HARD_CAP)
        starts = list(range(next_start, target + 1, _VIATOR_FULL_PAGE_SIZE))
        if starts:
            results = await asyncio.gather(
                *[
                    viator_service.search_tours(
                        **viator_kwargs, start=s, count=_VIATOR_FULL_PAGE_SIZE
                    )
                    for s in starts
                ],
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, Exception):
                    continue
                for p in r.get("products") or []:
                    code = p.get("viator_product_code")
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        all_products.append(p)

        if all_products:
            await _set_cached_tour_block(redis, cache_key_full, all_products, total)
    except ViatorError as exc:
        if exc.status_code != 400:
            logger.warning("Viator background full-fetch failed for %s: %s", cache_key_full, exc.message)
    except Exception as exc:
        logger.warning("Viator background full-fetch crashed for %s: %s", cache_key_full, exc)
    finally:
        try:
            await redis.delete(lock_key)
        except Exception:
            pass


_SORT_BY_TO_VIATOR = {
    "created_at": ("DATE_ADDED", "DESCENDING"),
    "price_per_person": ("PRICE", "ASCENDING"),
    "avg_rating": ("TRAVELER_RATING", "DESCENDING"),
    "duration_days": ("ITINERARY_DURATION", "ASCENDING"),
    "name": ("DEFAULT", "DESCENDING"),
}


def _map_sort_to_viator(sort_by: str, sort_order: str) -> tuple[str, str]:
    viator_sort, default_order = _SORT_BY_TO_VIATOR.get(sort_by, ("DEFAULT", "DESCENDING"))
    if viator_sort == "PRICE" or viator_sort == "ITINERARY_DURATION":
        order = "ASCENDING" if sort_order == "asc" else "DESCENDING"
    elif viator_sort == "TRAVELER_RATING":
        order = "DESCENDING"
    else:
        order = default_order
    return viator_sort, order


# ── Viator endpoints — MUST be declared before /{tour_id} ────────────────────

@router.get("/viator/tags", response_model=ViatorTagsResponse)
async def list_viator_tags(request: Request):
    """Return Viator tag tree (categories) used to render filter UI. Cached 24h."""
    redis = getattr(request.app.state, "redis", None)
    cache_key = "viator:tags:v2"
    cached = await _get_cached(redis, cache_key)
    if cached is not None:
        return cached
    try:
        tags = await viator_service.get_tags()
    except ViatorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    result = {"tags": tags}
    await _set_cached(redis, cache_key, result, ttl=86400)
    return result


@router.get("/viator/destinations", response_model=ViatorDestinationsResponse)
async def list_viator_destinations(
    request: Request,
    q: str = Query(..., min_length=2, description="City/region prefix to autocomplete"),
    limit: int = Query(10, ge=1, le=25),
):
    """Autocomplete from Viator's `/destinations` catalog so users can only
    pick destinations that actually return tours. Cached 24h server-side.
    """
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"viator:dest-search:{q.lower()}:{limit}"
    cached = await _get_cached(redis, cache_key)
    if cached is not None and isinstance(cached, dict):
        return cached
    try:
        matches = await viator_service.search_destinations(q, limit=limit)
    except ViatorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    payload = {
        "destinations": [
            {
                "destination_id": d["destinationId"],
                "name": d["name"],
                "type": d.get("type", ""),
                "parent_destination_id": d.get("parentDestinationId"),
            }
            for d in matches
        ]
    }
    await _set_cached(redis, cache_key, payload, ttl=86400)
    return payload


@router.get("/viator/{viator_product_code}", response_model=TourResponse)
async def get_viator_tour(viator_product_code: str, request: Request):
    """Fetch a single Viator product by its product code."""
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"viator:tour:{viator_product_code}"
    cached = await _get_cached(redis, cache_key)
    if cached:
        raw = cached[0] if isinstance(cached, list) else cached
        return _viator_tour_to_response(raw)

    try:
        raw = await viator_service.get_product(viator_product_code)
    except ViatorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    await _set_cached(redis, cache_key, [raw])
    return _viator_tour_to_response(raw)


@router.get("/viator/{viator_product_code}/availability", response_model=TourAvailabilityResponse)
async def get_viator_availability(
    viator_product_code: str,
    tour_date: date = Query(...),
    adults: int = Query(default=1, ge=1),
    child_ages: str | None = Query(
        default=None,
        description="Comma-separated child ages (0–17), e.g. '8,11'",
    ),
    guests: int | None = Query(
        default=None,
        ge=1,
        description="Deprecated. Use adults + child_ages instead.",
    ),
):
    """Check live availability + per-band-aware price for a Viator product."""
    parsed_children = _parse_child_ages_csv(child_ages)
    effective_adults = adults
    if guests is not None and child_ages is None:
        # Legacy callers: keep behaviour identical to the old guests=N path.
        effective_adults = guests
    try:
        result = await viator_service.check_availability(
            viator_product_code,
            tour_date,
            adults=effective_adults,
            children_ages=parsed_children,
        )
    except ViatorError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    return TourAvailabilityResponse(**result)


# ── Standard tour endpoints ───────────────────────────────────────────────────

@router.get("", response_model=TourListResponse)
async def list_tours(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = None,
    country: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, description="Text search on name/description"),
    min_price: float | None = None,
    max_price: float | None = None,
    duration: int | None = None,
    owner_id: uuid.UUID | None = Query(None, description="Filter by owner admin"),
    sort_by: str = Query("created_at", pattern="^(created_at|price_per_person|avg_rating|duration_days|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    # ── Viator-specific filters (Affiliate Basic Access surface) ───────────
    tags: list[int] | None = Query(None, description="Viator tag IDs (multi)"),
    flags: list[str] | None = Query(None, description="Viator flags: FREE_CANCELLATION, etc."),
    rating_min: float | None = Query(None, ge=1, le=5),
    duration_min: int | None = Query(None, ge=0, description="Min duration in minutes"),
    duration_max: int | None = Query(None, ge=0, description="Max duration in minutes"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    source: str | None = Query(None, pattern="^(all|viator|local)$"),
):
    # Validate flags whitelist early so caller gets 422 rather than silent drop.
    if flags:
        invalid = [f for f in flags if f not in VIATOR_FLAGS]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown Viator flags: {invalid}",
            )

    # Determine effective source. Activating any Viator-only filter implicitly
    # restricts results to Viator unless the caller pinned source explicitly.
    viator_only_active = bool(
        tags or flags or rating_min is not None
        or duration_min is not None or duration_max is not None
        or start_date is not None or end_date is not None
    )
    if source is None:
        effective_source = "viator" if viator_only_active else "all"
    else:
        effective_source = source

    db_items: list[TourResponse] = []
    total_db = 0
    db_viator_codes: set[str] = set()

    viator_city = city or q
    use_viator = effective_source != "local" and bool(viator_city) and not owner_id

    # ── DB query (skipped when effective_source == "viator") ─────────────────
    if effective_source != "viator":
        query = select(Tour)

        if owner_id:
            query = query.where(Tour.owner_id == owner_id)
        if city:
            # Match partner tours using the SAME normalized + alias-resolved key
            # Viator search uses, so "Ha Noi"/"Hà Nội"/"Saigon" surface partner
            # rows alongside the Viator results instead of being dropped by a raw
            # ilike. f_unaccent already lowercases + strips diacritics; the
            # regexp_replace removes spaces/punctuation to mirror _normalize_dest_name.
            norm_city = viator_service.normalize_destination_key(city)
            if norm_city:
                city_key = func.regexp_replace(func.f_unaccent(Tour.city), "[^a-z0-9]+", "", "g")
                query = query.where(city_key.like(f"%{norm_city}%"))
            else:
                query = query.where(Tour.city.ilike(f"%{city}%"))
        if country:
            query = query.where(Tour.country.ilike(f"%{country}%"))
        if category:
            query = query.where(Tour.category == category)
        if min_price is not None:
            query = query.where(Tour.price_per_person >= min_price)
        if max_price is not None:
            query = query.where(Tour.price_per_person <= max_price)
        if duration:
            query = query.where(Tour.duration_days == duration)
        if q:
            pattern = f"%{q}%"
            query = query.where(or_(Tour.name.ilike(pattern), Tour.description.ilike(pattern)))

        count_q = select(func.count()).select_from(query.subquery())
        total_db = (await db.execute(count_q)).scalar() or 0

        sort_col = getattr(Tour, sort_by)
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        if not use_viator:
            # Local-only: paginate at SQL level and return directly.
            query = query.offset((page - 1) * per_page).limit(per_page)
            result = await db.execute(query)
            tours = result.scalars().all()
            db_items = [_tour_response(t) for t in tours]
            total_pages = math.ceil(total_db / per_page) if total_db else 1
            return TourListResponse(
                items=db_items,
                meta={
                    "total": total_db,
                    "page": page,
                    "per_page": per_page,
                    "total_pages": total_pages,
                },
            )

        # Hybrid path: fetch *all* matching DB rows so we can merge with Viator
        # and slice the combined list in-memory. DB rows are typically few
        # (mostly local/seeded tours), so this stays cheap.
        result = await db.execute(query)
        tours = result.scalars().all()
        db_items = [_tour_response(t) for t in tours]
        db_viator_codes = {t.viator_product_code for t in tours if t.viator_product_code}

    # ── Viator hybrid search (two-tier cache; page 1 fast preview + bg fill) ──
    viator_items: list[TourResponse] = []
    viator_total = 0
    if use_viator:
        viator_sort, viator_order = _map_sort_to_viator(sort_by, sort_order)
        # Cache key is keyed by filters only — NOT page/per_page — so all pages
        # of the same search share the same cached product set.
        filter_payload = {
            "city": viator_city.lower(),
            "tags": sorted(tags or []),
            "flags": sorted(flags or []),
            "rating_min": rating_min,
            "duration_min": duration_min,
            "duration_max": duration_max,
            "lowest_price": min_price,
            "highest_price": max_price,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "sort": viator_sort,
            "order": viator_order,
        }
        key_hash = hashlib.sha1(
            json.dumps(filter_payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        cache_base = f"viator:tours_v2:{key_hash}"
        cache_key_full = f"{cache_base}:full"
        cache_key_p1 = f"{cache_base}:p1"

        viator_kwargs = dict(
            city=viator_city,
            tags=tags,
            flags=flags,
            rating_from=rating_min,
            duration_from_min=duration_min,
            duration_to_min=duration_max,
            lowest_price=min_price,
            highest_price=max_price,
            start_date=start_date,
            end_date=end_date,
            sort=viator_sort,
            order=viator_order,
        )

        redis = getattr(request.app.state, "redis", None)
        raw_products: list[dict] = []

        cached_full = await _get_cached_tour_block(redis, cache_key_full)
        if cached_full is not None:
            raw_products, viator_total = cached_full
        elif page > 1:
            # Page 2+ cold cache: need the full set — fetch one batch sync and
            # trigger the rest in the background.
            try:
                first = await viator_service.search_tours(
                    **viator_kwargs, start=1, count=_VIATOR_FULL_PAGE_SIZE
                )
                raw_products = first.get("products") or []
                viator_total = int(first.get("total") or len(raw_products))
                if raw_products:
                    await _set_cached_tour_block(
                        redis, cache_key_full, raw_products, viator_total
                    )
                    background_tasks.add_task(
                        _background_fill_full_viator_cache,
                        redis, cache_key_full, viator_kwargs, viator_total,
                    )
            except ViatorError as exc:
                if exc.status_code != 400:
                    logger.warning("Viator search degraded: %s", exc.message)
        else:
            # Page 1 fast path.
            cached_p1 = await _get_cached_tour_block(redis, cache_key_p1)
            if cached_p1 is not None:
                raw_products, viator_total = cached_p1
            else:
                try:
                    payload = await viator_service.search_tours(
                        **viator_kwargs, start=1, count=_VIATOR_FAST_LIMIT
                    )
                    raw_products = payload.get("products") or []
                    viator_total = int(payload.get("total") or len(raw_products))
                    if raw_products:
                        await _set_cached_tour_block(
                            redis,
                            cache_key_p1,
                            raw_products,
                            viator_total,
                            ttl=_VIATOR_FAST_CACHE_TTL,
                        )
                except ViatorError as exc:
                    if exc.status_code != 400:
                        logger.warning("Viator search degraded: %s", exc.message)
            # Fire-and-forget: fill the full cache so page-2+ are instant.
            if raw_products:
                background_tasks.add_task(
                    _background_fill_full_viator_cache,
                    redis, cache_key_full, viator_kwargs, viator_total,
                )

        for raw in raw_products:
            code = raw.get("viator_product_code")
            if code and code in db_viator_codes:
                continue
            if category and effective_source != "viator" and raw.get("category") != category:
                continue
            viator_items.append(_viator_tour_to_response(raw))

    all_items = db_items + viator_items
    # Stable total: advertise Viator's full match count (capped) + DB rows, so
    # the displayed count doesn't jump between the page-1 fast preview and the
    # later full-cache responses.
    if viator_total > 0:
        viator_visible = min(viator_total, _VIATOR_FULL_HARD_CAP)
        total = max(len(all_items), total_db + viator_visible)
    else:
        total = len(all_items)
    total_pages = math.ceil(total / per_page) if total else 1
    start = (page - 1) * per_page
    end = start + per_page
    page_items = all_items[start:end]

    return TourListResponse(
        items=page_items,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    )


@router.get("/{tour_id}", response_model=TourResponse)
async def get_tour(tour_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    return _tour_response(tour)


@router.get("/{tour_id}/availability", response_model=TourAvailabilityResponse)
async def get_tour_availability(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    tour_date: date = Query(...),
    adults: int = Query(default=1, ge=1),
    child_ages: str | None = Query(
        default=None,
        description="Comma-separated child ages (0–17), e.g. '8,11'",
    ),
):
    """Check remaining slots + per-person price for a Partner tour on a date.

    Returns the same `TourAvailabilityResponse` shape as the Viator
    availability endpoint so the unified tour detail page can drive one
    "Check availability" widget for both sources. Read-only — it does NOT
    create a `tour_schedule` row (that happens at booking time).
    """
    tour = (
        await db.execute(select(Tour).where(Tour.id == tour_id))
    ).scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")

    children = _parse_child_ages_csv(child_ages)
    total_travelers = adults + len(children)
    age_bands = tour.age_bands or []

    # Per-person price: age bands when defined, else legacy default tiers.
    try:
        if age_bands:
            subtotal = compute_tour_subtotal_from_bands(
                age_bands,
                adults=adults,
                children_ages=children,
                fallback_price=tour.price_per_person,
            )
        else:
            subtotal = compute_tour_subtotal(
                tour.price_per_person, adults=adults, children_ages=children
            )
    except AgeBandError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    per_person = float(subtotal) / total_travelers if total_travelers else float(subtotal)

    # Remaining slots (read-only): no schedule row yet ⇒ full capacity.
    schedule = (
        await db.execute(
            select(TourSchedule).where(
                TourSchedule.tour_id == tour_id,
                TourSchedule.available_date == tour_date,
            )
        )
    ).scalar_one_or_none()
    remaining = (
        schedule.total_slots - schedule.booked_slots
        if schedule is not None
        else tour.max_participants
    )

    # paxMix breakdown (mirrors Viator response): adults + children grouped by band.
    paxmix: list[dict] = []
    if adults > 0:
        paxmix.append({"ageBand": "ADULT", "numberOfTravelers": adults})
    if children:
        band_counts: dict[str, int] = {}
        for age in children:
            band = match_age_band(age, age_bands) if age_bands else None
            name = str((band or {}).get("age_band") or "CHILD").upper()
            band_counts[name] = band_counts.get(name, 0) + 1
        for name, n in band_counts.items():
            paxmix.append({"ageBand": name, "numberOfTravelers": n})

    return TourAvailabilityResponse(
        available=remaining >= total_travelers,
        price=round(per_person, 2),
        currency="USD",
        tour_date=tour_date.isoformat(),
        paxmix_used=paxmix or None,
    )


def _assert_tour_owner_or_admin(tour: Tour, user) -> None:
    if user.role == "admin":
        return
    if tour.owner_id and tour.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this tour",
        )


@router.post("", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def create_tour(
    data: TourCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    payload = data.model_dump()
    slug = payload.get("slug") or _slugify(data.name)
    base_slug = slug
    suffix = 1
    while True:
        existing = await db.execute(select(Tour).where(Tour.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    payload["slug"] = slug

    tour = Tour(**payload, owner_id=current_user.id)
    _sync_price_to_adult_band(tour)
    db.add(tour)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.put("/{tour_id}", response_model=TourResponse)
async def replace_tour(
    tour_id: uuid.UUID,
    data: TourCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_admin(tour, current_user)

    for field, value in data.model_dump().items():
        # slug is auto-managed; don't let an omitted (None) slug null the column.
        if field == "slug" and value is None:
            continue
        setattr(tour, field, value)
    _sync_price_to_adult_band(tour)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.patch("/{tour_id}", response_model=TourResponse)
async def update_tour(
    tour_id: uuid.UUID,
    data: TourUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_admin(tour, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tour, field, value)
    _sync_price_to_adult_band(tour)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.delete("/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(
    tour_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_admin(tour, current_user)

    redis = getattr(request.app.state, "redis", None)
    try:
        if await lock_service.has_active_tour_lock(redis, tour_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tour has an active checkout; please retry in a few minutes.",
            )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    await db.delete(tour)
    await db.flush()


@router.post("/{tour_id}/images", response_model=TourResponse)
async def upload_tour_images(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_admin(tour, current_user)

    urls = await upload_images(files, folder="tours")
    existing = tour.images or []
    tour.images = existing + urls
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)
