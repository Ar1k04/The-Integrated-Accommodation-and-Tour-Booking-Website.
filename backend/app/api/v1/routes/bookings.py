import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.flight_booking import FlightBooking
from app.schemas.booking import (
    BookingCreate,
    BookingDetailResponse,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
    CancellationResponse,
)
from app.services import booking_service
from app.services.booking_service import BookingServiceError
from app.services.lock_service import LockCollisionError, RedisUnavailableError
from app.services.loyalty_service import LoyaltyError
from app.services.voucher_service import VoucherError

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    payload: Annotated[dict[str, Any], Body(...)],
):
    if "items" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking must include an `items` array",
        )
    data = BookingCreate.model_validate(payload)
    redis = getattr(request.app.state, "redis", None)

    try:
        booking = await booking_service.create_booking(
            db=db, user_id=current_user.id, data=data, redis=redis
        )
    except LockCollisionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RedisUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except (BookingServiceError, VoucherError, LoyaltyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # Reload with eager relationships to avoid lazy-load failures during
    # serialization. Flight bookings populate `BookingItem.flight_booking`;
    # without this option Pydantic triggers MissingGreenlet on serialize.
    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.items).selectinload(BookingItem.room),
            selectinload(Booking.items).selectinload(BookingItem.flight_booking),
        )
        .where(Booking.id == booking.id)
    )
    return result.scalar_one()


@router.get("", response_model=BookingListResponse)
async def list_my_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    booking_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Booking).where(Booking.user_id == current_user.id)

    if booking_status:
        query = query.where(Booking.status == booking_status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Booking.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    query = query.options(
        selectinload(Booking.items).selectinload(BookingItem.room),
        selectinload(Booking.items).selectinload(BookingItem.flight_booking),
    )

    result = await db.execute(query)
    bookings = result.scalars().all()

    return BookingListResponse(
        items=[BookingResponse.model_validate(b) for b in bookings],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/{booking_id}", response_model=BookingDetailResponse)
async def get_booking(
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(Booking)
        .options(
            selectinload(Booking.items).selectinload(BookingItem.room),
            selectinload(Booking.items).selectinload(BookingItem.flight_booking),
        )
        .where(Booking.id == booking_id, Booking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return booking


@router.patch("/{booking_id}", response_model=BookingResponse)
async def update_booking(
    booking_id: uuid.UUID,
    data: BookingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status in ("cancelled", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify a {booking.status} booking",
        )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(booking, field, value)
    await db.flush()
    await db.refresh(booking)
    return booking


@router.delete("/{booking_id}", response_model=CancellationResponse)
async def cancel_booking(
    booking_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Cancel a booking. For LiteAPI-sourced room items, this also cancels the
    booking upstream via LiteAPI's PUT /bookings/{id}, and the response
    includes the supplier's refund_amount / cancellation_fee so the frontend
    can show the user what (if anything) they'll get back.
    """
    # Nested eager-load: cancel_booking walks booking.items and accesses
    # item.flight_booking — without selectinload at this depth SQLAlchemy
    # tries to lazy-load inside an async session and raises
    # `MissingGreenlet`. Same fix as the silent-fail bug from
    # confirm_booking (memory 2026-05-23).
    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
        .where(Booking.id == booking_id, Booking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if booking.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already cancelled")

    redis = getattr(request.app.state, "redis", None)
    booking, supplier_results, stripe_refund_info = await booking_service.cancel_booking(
        db, booking, redis=redis
    )
    return CancellationResponse(
        booking_id=booking.id,
        status=booking.status,
        items=supplier_results,
        stripe_refund_id=stripe_refund_info.get("stripe_refund_id"),
        stripe_refund_amount=stripe_refund_info.get("stripe_refund_amount"),
        non_refundable=stripe_refund_info.get("non_refundable", False),
    )
