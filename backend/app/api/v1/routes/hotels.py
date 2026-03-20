import math
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.room import Room
from app.schemas.hotel import HotelCreate, HotelListResponse, HotelResponse, HotelUpdate

router = APIRouter(prefix="/hotels", tags=["Hotels"])


@router.get("", response_model=HotelListResponse)
async def list_hotels(
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
    sort_by: str = Query("created_at", regex="^(created_at|base_price|avg_rating|star_rating|name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Hotel)

    if city:
        query = query.where(Hotel.city.ilike(f"%{city}%"))
    if country:
        query = query.where(Hotel.country.ilike(f"%{country}%"))
    if star_rating:
        query = query.where(Hotel.star_rating == star_rating)
    if min_price is not None:
        query = query.where(Hotel.base_price >= min_price)
    if max_price is not None:
        query = query.where(Hotel.base_price <= max_price)
    if property_type:
        query = query.where(Hotel.property_type == property_type)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Hotel.name.ilike(pattern), Hotel.description.ilike(pattern)))
    if amenities:
        for amenity in amenities.split(","):
            query = query.where(Hotel.amenities.contains([amenity.strip()]))

    if check_in and check_out:
        available_hotel_ids = (
            select(Room.hotel_id)
            .where(
                Room.id.notin_(
                    select(Booking.room_id)
                    .where(
                        and_(
                            Booking.status.in_(["pending", "confirmed"]),
                            Booking.check_in < check_out,
                            Booking.check_out > check_in,
                        )
                    )
                    .correlate(Room)
                )
            )
        )
        if guests:
            available_hotel_ids = available_hotel_ids.where(Room.max_guests >= guests)
        query = query.where(Hotel.id.in_(available_hotel_ids))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sort_col = getattr(Hotel, sort_by)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    hotels = result.scalars().all()

    return HotelListResponse(
        items=[HotelResponse.model_validate(h) for h in hotels],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    return hotel


@router.post("", response_model=HotelResponse, status_code=status.HTTP_201_CREATED)
async def create_hotel(
    data: HotelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    existing = await db.execute(select(Hotel).where(Hotel.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    hotel = Hotel(**data.model_dump())
    db.add(hotel)
    await db.flush()
    await db.refresh(hotel)
    return hotel


@router.put("/{hotel_id}", response_model=HotelResponse)
async def replace_hotel(
    hotel_id: uuid.UUID,
    data: HotelCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    for field, value in data.model_dump().items():
        setattr(hotel, field, value)
    await db.flush()
    await db.refresh(hotel)
    return hotel


@router.patch("/{hotel_id}", response_model=HotelResponse)
async def update_hotel(
    hotel_id: uuid.UUID,
    data: HotelUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(hotel, field, value)
    await db.flush()
    await db.refresh(hotel)
    return hotel


@router.delete("/{hotel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hotel(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    await db.delete(hotel)
    await db.flush()


@router.post("/{hotel_id}/images", response_model=HotelResponse)
async def upload_hotel_images(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    urls = await upload_images(files, folder="hotels")
    existing = hotel.images or []
    hotel.images = existing + urls
    await db.flush()
    await db.refresh(hotel)
    return hotel
