import json
import logging
import math
import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import StaffUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.hotel import Hotel
from app.models.room import Room
from app.schemas.hotel import (
    HotelCreate,
    HotelListResponse,
    HotelResponse,
    HotelRoomTypeResponse,
    HotelUpdate,
)
from app.services import liteapi_service, lock_service
from app.services.liteapi_service import LiteAPIError, get_min_rates_batch
from app.services.facility_mapping import HOTEL_TYPE_SLUG_TO_ID, SLUG_TO_LITEAPI_ID
from app.services.lock_service import RedisUnavailableError

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


def _parse_child_ages(raw: str | None) -> list[int]:
    """Parse a `child_ages=11,8` query string into a clamped list of ints (0–17)."""
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
    child_ages: str | None = Query(None, description="Comma-separated child ages (0–17)"),
    min_price: float | None = None,
    max_price: float | None = None,
    star_rating: int | None = None,
    amenities: str | None = Query(None, description="Comma-separated amenity list"),
    property_type: str | None = None,
    hotel_types: str | None = Query(None, description="Comma-separated hotel-type slugs (apartments,hotels,resorts,...)"),
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
            select(BookingItem.room_id)
            .join(Booking, BookingItem.booking_id == Booking.id)
            .where(
                BookingItem.item_type == "room",
                BookingItem.room_id.is_not(None),
                Booking.status.in_(["pending", "confirmed"]),
                BookingItem.check_in < check_out,
                BookingItem.check_out > check_in,
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

    # Hotel-type filter: a comma-separated slug list shared by frontend + LiteAPI.
    # Local rows match on Hotel.property_type slug; LiteAPI translates slugs to
    # supplier IDs further down (see `hotel_type_ids` below).
    selected_type_slugs = [
        s.strip() for s in (hotel_types or "").split(",") if s.strip()
    ]
    if selected_type_slugs:
        query = query.where(Hotel.property_type.in_(selected_type_slugs))

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
        # Translate amenity slugs → LiteAPI facility IDs
        selected_slugs = [s.strip() for s in (amenities or "").split(",") if s.strip()]
        facility_ids = [SLUG_TO_LITEAPI_ID[s] for s in selected_slugs if s in SLUG_TO_LITEAPI_ID]
        strict = len(facility_ids) >= 2
        # Translate hotel-type slugs → LiteAPI hotel-type IDs
        hotel_type_ids = [
            HOTEL_TYPE_SLUG_TO_ID[s] for s in selected_type_slugs if s in HOTEL_TYPE_SLUG_TO_ID
        ]
        slugs_key = ",".join(sorted(selected_slugs)) if selected_slugs else ""
        types_key = ",".join(sorted(selected_type_slugs)) if selected_type_slugs else ""
        cache_key = f"liteapi:hotels:{city or ''}:{country or ''}:{check_in}:{check_out}:{guests or 1}:{slugs_key}:{types_key}"
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
                    facility_ids=facility_ids or None,
                    strict_facilities_filtering=strict,
                    hotel_type_ids=hotel_type_ids or None,
                )
                await _set_cached_liteapi_hotels(redis, cache_key, raw_hotels)
            except LiteAPIError as exc:
                # 400 means we couldn't infer country — that's expected for unknown cities
                if exc.status_code != 400:
                    logger.warning("LiteAPI search degraded: %s", exc.message)
                raw_hotels = []

        # Build initial list and collect IDs that have no static minRate
        no_price_ids: list[str] = []
        for raw in raw_hotels:
            lite_id = raw.get("liteapi_hotel_id")
            if lite_id and lite_id in db_liteapi_ids:
                continue
            if star_rating and int(raw.get("star_rating") or 0) != star_rating:
                continue
            item = _liteapi_hotel_to_response(raw)
            liteapi_items.append(item)
            if item.min_room_price is None and lite_id:
                no_price_ids.append(lite_id)

        # Batch-fetch min rates for hotels that have no static pricing
        if no_price_ids:
            rate_check_in = check_in or (date.today() + timedelta(days=7))
            rate_check_out = check_out or (rate_check_in + timedelta(days=1))
            rate_cache_key = f"liteapi:minrates:{','.join(sorted(no_price_ids))}:{rate_check_in}:{rate_check_out}"
            cached_rates = await _get_cached_liteapi_hotels(redis, rate_cache_key)
            if cached_rates is not None:
                min_rates = {k: v for k, v in (cached_rates if isinstance(cached_rates, dict) else {}).items()}
            else:
                parsed_child_ages = _parse_child_ages(child_ages)
                min_rates = await get_min_rates_batch(
                    no_price_ids,
                    rate_check_in,
                    rate_check_out,
                    guests or 1,
                    children_ages=parsed_child_ages,
                )
                if min_rates:
                    await redis.set(rate_cache_key, json.dumps(min_rates), ex=_LITEAPI_CACHE_TTL) if redis else None
            for item in liteapi_items:
                if item.min_room_price is None and item.liteapi_hotel_id in min_rates:
                    item.min_room_price = min_rates[item.liteapi_hotel_id]

        # Apply price range filter to LiteAPI results after prices are populated
        if min_price is not None:
            liteapi_items = [
                item for item in liteapi_items
                if item.min_room_price is not None and item.min_room_price >= min_price
            ]
        if max_price is not None:
            liteapi_items = [
                item for item in liteapi_items
                if item.min_room_price is not None and item.min_room_price <= max_price
            ]

    all_items = db_items + liteapi_items

    # Re-sort the merged list so LiteAPI hotels respect the requested sort order.
    # Hotels without a value for the sort field always sink to the bottom.
    if sort_by != "created_at" and liteapi_items:
        reverse = sort_order == "desc"

        def _sort_key(item: HotelResponse):
            if sort_by == "base_price":
                val = item.min_room_price
            elif sort_by == "avg_rating":
                val = item.avg_rating
            elif sort_by == "star_rating":
                val = item.star_rating
            else:
                val = None
            if val is None:
                return (1, 0)
            return (0, -val if reverse else val)

        all_items = sorted(all_items, key=_sort_key)

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


@router.get("/liteapi/{liteapi_hotel_id}/rates", response_model=list[HotelRoomTypeResponse])
async def get_liteapi_rates(
    liteapi_hotel_id: str,
    check_in: date = Query(...),
    check_out: date = Query(...),
    guests: int = Query(default=1, ge=1),
    rooms: int = Query(default=1, ge=1, le=20),
    adults: int | None = Query(default=None, ge=1),
    child_ages: str | None = Query(default=None, description="Comma-separated child ages (0–17)"),
):
    """Fetch live room-type groups (each with multiple rate plans) for a LiteAPI hotel.

    ``rooms`` is forwarded to LiteAPI as the number of occupancy slots so the search
    natively supports multi-room queries used by the recommendation widget.

    Children pricing: when ``child_ages`` is provided, each room receives a
    proportional share of the children list so suppliers apply per-room child
    policies (some hotels charge nothing for kids under 12, others charge a cot
    fee, etc.).
    """
    parsed_children = _parse_child_ages(child_ages)
    try:
        room_types = await liteapi_service.get_rates(
            liteapi_hotel_id=liteapi_hotel_id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            rooms=rooms,
            adults=adults,
            children_ages=parsed_children,
        )
    except LiteAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )
    return [HotelRoomTypeResponse(**rt) for rt in room_types]


@router.get("/liteapi/{liteapi_hotel_id}/reviews")
async def get_liteapi_hotel_reviews(
    liteapi_hotel_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
):
    """Return normalized guest reviews for a LiteAPI hotel.

    Cached in Redis for 1 h per hotel — review feeds change slowly.
    The shape matches the local ReviewCard component (id, user.full_name,
    rating on a 0–5 scale, comment, created_at) so the same UI can render both.
    """
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"liteapi:reviews:{liteapi_hotel_id}:{limit}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return {"items": json.loads(cached)}
        except Exception:
            pass

    try:
        reviews = await liteapi_service.get_hotel_reviews(liteapi_hotel_id, limit=limit)
    except LiteAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY if exc.status_code >= 500 else exc.status_code,
            detail=exc.message,
        )

    if reviews and redis:
        try:
            await redis.set(cache_key, json.dumps(reviews), ex=3600)
        except Exception:
            pass

    return {"items": reviews}


@router.get("/liteapi/{liteapi_hotel_id}/room-types", response_model=list[HotelRoomTypeResponse])
async def get_liteapi_room_types(
    liteapi_hotel_id: str,
    request: Request,
):
    """Return the room-type catalog (no prices) for the no-dates state.

    Cached in Redis for 1 h per hotel — the catalog rarely changes day-to-day.
    """
    redis = getattr(request.app.state, "redis", None)
    cache_key = f"liteapi:roomtypes:{liteapi_hotel_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return [HotelRoomTypeResponse(**rt) for rt in json.loads(cached)]
        except Exception:
            pass

    room_types = await liteapi_service.get_room_types_catalog(liteapi_hotel_id)

    if room_types and redis:
        try:
            await redis.set(cache_key, json.dumps(room_types), ex=3600)
        except Exception:
            pass

    return [HotelRoomTypeResponse(**rt) for rt in room_types]


# ── Facilities proxy ─────────────────────────────────────────────────────────

@router.get("/facilities")
async def list_facilities(request: Request):
    """Return canonical hotel facility list from LiteAPI. Cached in Redis for 24 h."""
    redis = getattr(request.app.state, "redis", None)
    cache_key = "liteapi:facilities:v1"
    cached = await _get_cached_liteapi_hotels(redis, cache_key)
    if cached:
        return cached
    try:
        data = await liteapi_service.list_facilities()
    except LiteAPIError:
        data = []
    if data and redis:
        try:
            await redis.set(cache_key, json.dumps(data), ex=86400)
        except Exception:
            pass
    return data


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


def _assert_owner_or_admin(hotel: Hotel, user) -> None:
    if user.role == "admin":
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
    current_user: StaffUser,
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
    current_user: StaffUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_admin(hotel, current_user)

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
    current_user: StaffUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_admin(hotel, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, value)
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_admin(hotel, current_user)

    # Cascade DELETE would drop every Room (and its RoomAvailability) under this
    # hotel — refuse if any of those rooms has an active checkout.
    room_ids = (
        await db.execute(select(Room.id).where(Room.hotel_id == hotel_id))
    ).scalars().all()
    redis = getattr(request.app.state, "redis", None)
    try:
        for rid in room_ids:
            if await lock_service.has_active_room_lock(redis, rid):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Hotel has rooms with active checkouts; please retry in a few minutes.",
                )
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    await db.delete(hotel)
    await db.flush()


@router.post("/{hotel_id}/images", response_model=HotelResponse)
async def upload_hotel_images(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_owner_or_admin(hotel, current_user)

    urls = await upload_images(files, folder="hotels")
    existing = hotel.images or []
    hotel.images = existing + urls
    await db.flush()
    await db.refresh(hotel)
    return _hotel_response(hotel, None)
