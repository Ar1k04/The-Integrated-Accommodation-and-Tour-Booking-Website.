import math
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.room import Room
from app.schemas.room import RoomAvailabilityResponse, RoomCreate, RoomListResponse, RoomResponse, RoomUpdate

router = APIRouter(tags=["Rooms"])


async def _get_hotel_for_room(db: AsyncSession, room: Room) -> Hotel:
    """Load the hotel that owns this room (for ownership checks)."""
    result = await db.execute(select(Hotel).where(Hotel.id == room.hotel_id))
    return result.scalar_one_or_none()


# --- nested under hotels ---

@router.get("/hotels/{hotel_id}/rooms", response_model=RoomListResponse)
async def list_hotel_rooms(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    check_in: date | None = None,
    check_out: date | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    hotel = (await db.execute(select(Hotel).where(Hotel.id == hotel_id))).scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    query = select(Room).where(Room.hotel_id == hotel_id)

    if check_in and check_out:
        booked_room_ids = (
            select(Booking.room_id)
            .where(
                and_(
                    Booking.status.in_(["pending", "confirmed"]),
                    Booking.check_in < check_out,
                    Booking.check_out > check_in,
                )
            )
        )
        query = query.where(Room.id.notin_(booked_room_ids))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rooms = result.scalars().all()

    return RoomListResponse(
        items=[RoomResponse.model_validate(r) for r in rooms],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


def _assert_hotel_owner_or_superadmin(hotel: Hotel, user) -> None:
    if user.role == "superadmin":
        return
    if hotel.owner_id and hotel.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this hotel",
        )


async def _load_room_and_check(db: AsyncSession, room_id: uuid.UUID, user) -> Room:
    room = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    hotel = (await db.execute(select(Hotel).where(Hotel.id == room.hotel_id))).scalar_one()
    _assert_hotel_owner_or_superadmin(hotel, user)
    return room


@router.post("/hotels/{hotel_id}/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    hotel_id: uuid.UUID,
    data: RoomCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    hotel = (await db.execute(select(Hotel).where(Hotel.id == hotel_id))).scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")
    _assert_hotel_owner_or_superadmin(hotel, current_user)

    room = Room(hotel_id=hotel_id, **data.model_dump())
    db.add(room)
    await db.flush()
    await db.refresh(room)
    return room


# --- direct room operations ---

@router.get("/rooms/{room_id}", response_model=RoomResponse)
async def get_room(room_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return room


@router.put("/rooms/{room_id}", response_model=RoomResponse)
async def replace_room(
    room_id: uuid.UUID,
    data: RoomCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    room = await _load_room_and_check(db, room_id, current_user)
    for field, value in data.model_dump().items():
        setattr(room, field, value)
    await db.flush()
    await db.refresh(room)
    return room


@router.patch("/rooms/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: uuid.UUID,
    data: RoomUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    room = await _load_room_and_check(db, room_id, current_user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    await db.flush()
    await db.refresh(room)
    return room


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    room = await _load_room_and_check(db, room_id, current_user)
    await db.delete(room)
    await db.flush()


@router.get("/rooms/{room_id}/availability", response_model=RoomAvailabilityResponse)
async def check_room_availability(
    room_id: uuid.UUID,
    check_in: date = Query(...),
    check_out: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    overlap_count = (
        await db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                and_(
                    Booking.room_id == room_id,
                    Booking.status.in_(["pending", "confirmed"]),
                    Booking.check_in < check_out,
                    Booking.check_out > check_in,
                )
            )
        )
    ).scalar() or 0

    rooms_left = room.total_quantity - overlap_count
    return RoomAvailabilityResponse(available=rooms_left > 0, rooms_left=max(rooms_left, 0))


@router.post("/rooms/{room_id}/images", response_model=RoomResponse)
async def upload_room_images(
    room_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    room = await _load_room_and_check(db, room_id, current_user)
    urls = await upload_images(files, folder="rooms")
    existing = room.images or []
    room.images = existing + urls
    await db.flush()
    await db.refresh(room)
    return room
