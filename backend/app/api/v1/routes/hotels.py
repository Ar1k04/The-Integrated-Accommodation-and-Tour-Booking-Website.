import asyncio
import json
import logging
import math
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.room import Room
from app.schemas.hotel import (
    HotelCreate,
    HotelListResponse,
    HotelRateResponse,
    HotelResponse,
    HotelUpdate,
)
from app.services import liteapi_service
from app.services.liteapi_service import LiteAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hotels", tags=["Hotels"])

_LITEAPI_CACHE_TTL = 300  # 5 minutes


def _hotel_response(hotel: Hotel, min_room_price: float | None = None) -> HotelResponse:
    data = HotelResponse.model_validate(hotel)
    data.min_room_price = min_room_price
    data.source = "local"
    data.liteapi_hotel_id = hotel.liteapi_hotel_id
    if hotel.owner:
        data.owner_name = hotel.owner.full_name
    return data


def _liteapi_hotel_to_response(raw: dict) -> HotelResponse:
    """Convert a normalized LiteAPI hotel dict to HotelResponse."""
    return HotelResponse(
        id=None,
        name=raw.get("name", ""),
        slug=None,
        description=raw.get("description"),
        address=raw.get("address"),
        city=raw.get("city", ""),
        country=raw.get("country", ""),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        star_rating=int(raw.get("star_rating") or 3),
        property_type=raw.get("property_type"),
        amenities=raw.get("amenities") or [],
        images=raw.get("images") or [],
        base_price=raw.get("min_room_price") or 0,
        min_room_price=raw.get("min_room_price"),
        currency=raw.get("currency") or "USD",
        avg_rating=float(raw.get("avg_rating") or 0),
        total_reviews=int(raw.get("total_reviews") or 0),
        source="liteapi",
        liteapi_hotel_id=raw.get("liteapi_hotel_id"),
    )


async def _get_cached_liteapi_hotels(redis, cache_key: str) -> list[dict] | None:
    if redis is None:
        return None
    try:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None


async def _set_cached_liteapi_hotels(redis, cache_key: str, data: list[dict]) -> None:
    if redis is None:
        return
    try:
        await redis.set(cache_key, json.dumps(data), ex=_LITEAPI_CACHE_TTL)
    except Exception:
        pass


@router.get("", response_model=HotelListResponse)
async def list_hotels(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = None,
    country: str | None = None,
    check_in: date | None = None,
    check_out: date | None = None,
    guests: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    star_rating: int | None = None,
    amenities: str | None = Query(None, description="Comma-separated amenity list"),
    property_type: str | None = None,
    search: str | None = Query(None, description="Text search on name/description"),
    owner_id: uuid.UUID | None = Query(None, description="Filter by owner admin"),
    sort_by: str = Query("created_at", regex="^(created_at|base_price|avg_rating|star_rating|name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    # ── DB query ──────────────────────────────────────────────────────────────
    room_price_q = (
        select(
            Room.hotel_id.label("hotel_id"),
            func.min(Room.price_per_night).label("min_room_price"),
        )
        .group_by(Room.hotel_id)
    )
    if check_in and check_out:
        overlap_rooms_q = (
            select(Booking.room_id)
            .where(
                and_(
                    Booking.status.in_(["pending", "confirmed"]),
                    Booking.check_in < check_out,
                    Booking.check_out > check_in,
                )
            )
        )
        room_price_q = room_price_q.where(Room.id.notin_(overlap_rooms_q))

    if guests:
        room_price_q = room_price_q.where(Room.max_guests >= guests)

    room_price_subq = room_price_q.subquery()

    query = select(Hotel, room_price_subq.c.min_room_price).outerjoin(
        room_price_subq, Hotel.id == room_price_subq.c.hotel_id
    )

    if owner_id:
        query = query.where(Hotel.owner_id == owner_id)
    if city:
        query = query.where(Hotel.city.ilike(f"%{city}%"))
    if country:
        query = query.where(Hotel.country.ilike(f"%{country}%"))
    if star_rating:
        query = query.where(Hotel.star_rating == star_rating)
    if min_price is not None:
        query = query.where(room_price_subq.c.min_room_price >= min_price)
    if max_price is not None:
        query = query.where(room_price_subq.c.min_room_price <= max_price)
    if property_type:
        query = query.where(Hotel.property_type == property_type)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Hotel.name.ilike(pattern), Hotel.description.ilike(pattern)))
    if amenities:
        for amenity in amenities.split(","):
            query = query.where(Hotel.amenities.contains([amenity.strip()]))

    if check_in and check_out:
        query = query.where(room_price_subq.c.min_room_price.isnot(None))

    count_q = select(func.count()).select_from(query.subquery())
    total_db = (await db.execute(count_q)).scalar() or 0

    if sort_by == "base_price":
        sort_col = room_price_subq.c.min_room_price
    else:
        sort_col = getattr(Hotel, sort_by)

    if sort_order == "desc":
        query = query.order_by(sort_col.desc().nulls_last() if sort_by == "base_price" else sort_col.desc())
    else:
        query = query.order_by(sort_col.asc().nulls_last() if sort_by == "base_price" else sort_col.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    rows = result.all()
    db_items = [_hotel_response(row[0], row[1]) for row in rows]

    # Collect liteapi_hotel_ids already in DB to avoid duplicates
    db_liteapi_ids: set[str] = {
        row[0].liteapi_hotel_id for row in rows if row[0].liteapi_hotel_id
    }

    # ── LiteAPI hybrid search (only when city/country + dates provided, page 1, no owner filter) ──
    liteapi_items: list[HotelResponse] = []
    if (city or country) and not owner_id and not search and page == 1:
        redis = getattr(request.app.state, "redis", None)
        cache_key = f"liteapi:hotels:{city or ''}:{country or ''}:{check_in}:{check_out}:{guests or 1}"
        cached = await _get_cached_liteapi_hotels(redis, cache_key)

        if cached is not None:
            raw_hotels = cached
        else:
            try:
                raw_hotels = await liteapi_service.search_hotels(
                    country_code=country or "",
                    city=city or "",
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests or 1,
                    limit=20,
                )
                await _set_cached_liteapi_hotels(redis, cache_key, raw_hotels)
            except LiteAPIError as exc:
                # 400 means we couldn't infer country — that's expected for unknown cities
                if exc.status_code != 400:
                    logger.warning("LiteAPI search degraded: %s", exc.message)
                raw_hotels = []

        for raw in raw_hotels:
            lite_id = raw.get("liteapi_hotel_id")
            if lite_id and lite_id in db_liteapi_ids:
                continue  # already represented by a local hotel
            if star_rating and int(raw.get("star_rating") or 0) != star_rating:
                continue
            liteapi_items.append(_liteapi_hotel_to_response(raw))

    all_items = db_items + liteapi_items
    total = total_db + len(liteapi_items)

    return HotelListResponse(
        items=all_items,
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total_db / per_page) if total_db else 1,
        },
    )


# ── LiteAPI-specific endpoints (must be defined BEFORE /{hotel_id} to avoid routing conflict) ──

@router.get("/liteapi/{liteapi_hotel_id}", response_model=HotelResponse)
async def get_liteapi_hotel(
    liteapi_hotel_id: str,
    request: Request,
):
    """Fetch a single LiteAPI hotel by its LiteAPI ID."""
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"liteapi:hotel:{liteapi_hotel_id}"
    cached = await _get_cached_liteapi_hotels(redis, cache_key)

    if cached:
        return _liteapi_hotel_to_response(cached[0] if isinstance(cached, list) else cached)

    try:
        raw = await liteapi_service.get_hotel(liteapi_hotel_id)
    except LiteAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    await _set_cached_liteapi_hotels(redis, cache_key, [raw])
    return _liteapi_hotel_to_response(raw)


@router.get("/liteapi/{liteapi_hotel_id}/rates", response_model=list[HotelRateResponse])
async def get_liteapi_rates(
    liteapi_hotel_id: str,
    check_in: date = Query(...),
    check_out: date = Query(...),
    guests: int = Query(default=1, ge=1),
):
    """Fetch live room rates for a LiteAPI hotel."""
    try:
        rates = await liteapi_service.get_rates(
            liteapi_hotel_id=liteapi_hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
        )
    except LiteAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    return [HotelRateResponse(**r) for r in rates]


# ── Standard DB hotel endpoints ───────────────────────────────────────────────

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    min_price_result = await db.execute(
        select(func.min(Room.price_per_night)).where(Room.hotel_id == hotel_id)
    )
    min_room_price = min_price_result.scalar_one_or_none()
    return _hotel_response(hotel, min_room_price)


def _assert_owner_or_superadmin(hotel: Hotel, user) -> None:
    if user.role == "superadmin":
        return
    if hotel.owner_id and hotel.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this hotel",
        )


def _slugify(text: str) -> str:
    import re
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", slug).strip("-")


@router.post("", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    data: HotelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    slug = data.slug or _slugify(data.name)
    base_slug = slug
    suffix = 1
    while True:
        existing = await db.execute(select(Hotel).where(Hotel.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    hotel_data = data.model_dump()
    hotel_data["slug"] = slug
    if hotel_data.get("base_price") is None:
        hotel_data["base_price"] = 1
    hotel = Hotel(**hotel_data, owner_id=current_user.id)
    db.add(hotel)
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)


@router.put("/{hotel_id}", response_model=HotelResponse)
async def replace_hotel(
    hotel_id: uuid.UUID,
    data: HotelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_superadmin(hotel, current_user)

    for field, value in data.model_dump().items():
        if field == "base_price" and value is None:
            continue
        setattr(hotel, field, value)
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)


@router.patch("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: uuid.UUID,
    data: HotelUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_superadmin(hotel, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, value)
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_superadmin(hotel, current_user)
    await db.delete(hotel)
    await db.flush()


@router.post("/{hotel_id}/images", response_model=HotelResponse)
async def upload_hotel_images(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_superadmin(hotel, current_user)

    urls = await upload_images(files, folder="hotels")
    existing = hotel.images or []
    hotel.images = existing + urls
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)
