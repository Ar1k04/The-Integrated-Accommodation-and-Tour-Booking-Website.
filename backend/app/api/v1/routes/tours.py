import hashlib
import json
import logging
import math
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import StaffUser, CurrentUser
from app.db.session import get_db
from app.models.tour import Tour
from app.schemas.tour import (
    TourAvailabilityResponse,
    TourCreate,
    TourListResponse,
    TourResponse,
    TourUpdate,
    ViatorTagsResponse,
)
from app.services import lock_service, viator_service
from app.services.lock_service import RedisUnavailableError
from app.services.viator_service import ViatorError, VIATOR_FLAGS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tours", tags=["Tours"])

_VIATOR_CACHE_TTL = 300  # 5 minutes


def _tour_response(tour: Tour) -> TourResponse:
    data = TourResponse.model_validate(tour)
    data.source = "local"
    data.viator_product_code = tour.viator_product_code
    if tour.owner:
        data.owner_name = tour.owner.full_name
    return data


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
    )


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
    per_page: int = Query(20, ge=1, le=100),
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

    # ── DB query (skipped when effective_source == "viator") ─────────────────
    if effective_source != "viator":
        query = select(Tour)

        if owner_id:
            query = query.where(Tour.owner_id == owner_id)
        if city:
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
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await db.execute(query)
        tours = result.scalars().all()
        db_items = [_tour_response(t) for t in tours]
        db_viator_codes = {t.viator_product_code for t in tours if t.viator_product_code}

    # ── Viator hybrid search ─────────────────────────────────────────────────
    viator_city = city or q
    viator_items: list[TourResponse] = []
    viator_total = 0
    if effective_source != "local" and viator_city and not owner_id:
        viator_sort, viator_order = _map_sort_to_viator(sort_by, sort_order)
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
            "page": page,
            "per_page": per_page,
        }
        key_hash = hashlib.sha1(
            json.dumps(filter_payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        cache_key = f"viator:tours:{key_hash}"

        redis = getattr(request.app.state, "redis", None)
        cached = await _get_cached(redis, cache_key)
        if cached is not None and isinstance(cached, dict):
            raw_payload = cached
        else:
            try:
                raw_payload = await viator_service.search_tours(
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
                    start=(page - 1) * per_page + 1,
                    count=per_page,
                )
                await _set_cached(redis, cache_key, raw_payload)
            except ViatorError as exc:
                if exc.status_code != 400:
                    logger.warning("Viator search degraded: %s", exc.message)
                raw_payload = {"products": [], "total": 0}

        raw_tours = raw_payload.get("products", []) if isinstance(raw_payload, dict) else raw_payload
        viator_total = int(raw_payload.get("total") or len(raw_tours)) if isinstance(raw_payload, dict) else len(raw_tours)
        for raw in raw_tours:
            code = raw.get("viator_product_code")
            if code and code in db_viator_codes:
                continue
            if category and effective_source != "viator" and raw.get("category") != category:
                continue
            viator_items.append(_viator_tour_to_response(raw))

    all_items = db_items + viator_items
    total = total_db + viator_total
    total_pages = math.ceil(total / per_page) if total else 1

    return TourListResponse(
        items=all_items,
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
    existing = await db.execute(select(Tour).where(Tour.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    tour = Tour(**data.model_dump(), owner_id=current_user.id)
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
        setattr(tour, field, value)
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
