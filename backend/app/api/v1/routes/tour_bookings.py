import math
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.tour import Tour
from app.models.tour_booking import TourBooking
from app.schemas.tour_booking import (
    TourBookingCreate,
    TourBookingListResponse,
    TourBookingResponse,
    TourBookingUpdate,
)

router = APIRouter(prefix="/tour-bookings", tags=["Tour Bookings"])


@router.post("", response_model=TourBookingResponse, status_code=status.HTTP_201_CREATED)
async def create_tour_booking(
    data: TourBookingCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    tour = (
        await db.execute(select(Tour).where(Tour.id == data.tour_id).with_for_update())
    ).scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")

    existing_participants = (
        await db.execute(
            select(func.coalesce(func.sum(TourBooking.participants_count), 0))
            .where(
                and_(
                    TourBooking.tour_id == data.tour_id,
                    TourBooking.tour_date == data.tour_date,
                    TourBooking.status.in_(["pending", "confirmed"]),
                )
            )
        )
    ).scalar() or 0

    if existing_participants + data.participants_count > tour.max_participants:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TOUR_FULL",
                "message": f"Only {tour.max_participants - existing_participants} spots left for this date.",
            },
        )

    total_price = Decimal(str(tour.price_per_person)) * data.participants_count

    booking = TourBooking(
        user_id=current_user.id,
        tour_id=data.tour_id,
        tour_date=data.tour_date,
        participants_count=data.participants_count,
        total_price=total_price,
        special_requests=data.special_requests,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


@router.get("", response_model=TourBookingListResponse)
async def list_my_tour_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    booking_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(TourBooking).where(TourBooking.user_id == current_user.id)
    if booking_status:
        query = query.where(TourBooking.status == booking_status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(TourBooking.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    bookings = result.scalars().all()

    return TourBookingListResponse(
        items=[TourBookingResponse.model_validate(b) for b in bookings],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/{booking_id}", response_model=TourBookingResponse)
async def get_tour_booking(
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(TourBooking).where(TourBooking.id == booking_id, TourBooking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour booking not found")
    return booking


@router.patch("/{booking_id}", response_model=TourBookingResponse)
async def update_tour_booking(
    booking_id: uuid.UUID,
    data: TourBookingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(TourBooking).where(TourBooking.id == booking_id, TourBooking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour booking not found")

    if booking.status in ("cancelled", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify a {booking.status} booking",
        )

    update_data = data.model_dump(exclude_unset=True)

    if "participants_count" in update_data:
        tour = (await db.execute(select(Tour).where(Tour.id == booking.tour_id))).scalar_one()
        new_count = update_data["participants_count"]
        booking.participants_count = new_count
        booking.total_price = Decimal(str(tour.price_per_person)) * new_count

    if "special_requests" in update_data:
        booking.special_requests = update_data["special_requests"]

    await db.flush()
    await db.refresh(booking)
    return booking


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_tour_booking(
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(TourBooking).where(TourBooking.id == booking_id, TourBooking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour booking not found")

    if booking.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already cancelled")

    booking.status = "cancelled"
    await db.flush()
