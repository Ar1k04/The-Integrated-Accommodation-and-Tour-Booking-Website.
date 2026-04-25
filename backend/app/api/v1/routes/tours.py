import json
import logging
import math
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.tour import Tour
from app.schemas.tour import (
    TourAvailabilityResponse,
    TourCreate,
    TourListResponse,
    TourResponse,
    TourUpdate,
)
from app.services import viator_service
from app.services.viator_service import ViatorError

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
    )


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


async def _set_cached(redis, key: str, data: list[dict] | dict) -> None:
    if redis is None:
        return
    try:
        await redis.set(key, json.dumps(data), ex=_VIATOR_CACHE_TTL)
    except Exception:
        pass


# ── Viator endpoints — MUST be declared before /{tour_id} ────────────────────

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
    guests: int = Query(default=1, ge=1),
):
    """Check live availability for a Viator product on a specific date."""
    try:
        result = await viator_service.check_availability(viator_product_code, tour_date, guests)
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
):
    # ── DB query ──────────────────────────────────────────────────────────────
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

    # Collect viator_product_codes already in DB to avoid duplicates
    db_viator_codes: set[str] = {t.viator_product_code for t in tours if t.viator_product_code}

    # ── Viator hybrid search (page 1, city filter, no owner/q filter) ─────────
    viator_items: list[TourResponse] = []
    if city and not owner_id and not q and page == 1:
        redis = getattr(request.app.state, "redis", None)
        cache_key = f"viator:tours:{city}"
        cached = await _get_cached(redis, cache_key)

        if cached is not None:
            raw_tours = cached
        else:
            try:
                raw_tours = await viator_service.search_tours(city=city, limit=20)
                await _set_cached(redis, cache_key, raw_tours)
            except ViatorError as exc:
                if exc.status_code != 400:
                    logger.warning("Viator search degraded: %s", exc.message)
                raw_tours = []

        for raw in raw_tours:
            code = raw.get("viator_product_code")
            if code and code in db_viator_codes:
                continue
            if category and raw.get("category") != category:
                continue
            viator_items.append(_viator_tour_to_response(raw))

    all_items = db_items + viator_items
    total = total_db + len(viator_items)

    return TourListResponse(
        items=all_items,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total_db / per_page) if total_db else 1,
        },
    )


@router.get("/{tour_id}", response_model=TourResponse)
async def get_tour(tour_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    return _tour_response(tour)


def _assert_tour_owner_or_superadmin(tour: Tour, user) -> None:
    if user.role == "superadmin":
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
    current_user: AdminUser,
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
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

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
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tour, field, value)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.delete("/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)
    await db.delete(tour)
    await db.flush()


@router.post("/{tour_id}/images", response_model=TourResponse)
async def upload_tour_images(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

    urls = await upload_images(files, folder="tours")
    existing = tour.images or []
    tour.images = existing + urls
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)
