import math
import uuid
from typing import Annotated, Any, Iterable

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.room import Room
from app.models.tour_schedule import TourSchedule
from app.schemas.booking import (
    BookingCreate,
    BookingDetailResponse,
    BookingListResponse,
    BookingResponse,
    BookingUpdate,
    CancellationResponse,
)
from app.services import booking_service
from app.services.booking_service import BookingServiceError, SupplierCancelError
from app.services.lock_service import LockCollisionError, RedisUnavailableError
from app.services.loyalty_service import LoyaltyError
from app.services.voucher_service import VoucherError

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _first_image(images) -> str | None:
    """Hotel/tour `images` are stored as a JSONB list of either strings or
    `{url, ...}` objects. Pick the first one in either shape."""
    if not images:
        return None
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("src") or None
    return None


def _attach_summaries(bookings: Iterable[Booking]) -> None:
    """Patch a `hotel` and `tour` summary dict onto each BookingItem so the
    Pydantic response can render them without an extra fetch from the client.

    For LiteAPI rooms there's no `room` relation — we fall back to the
    `hotel_name` / `liteapi_hotel_id` columns persisted at prebook. Same idea
    for Viator tours via `tour_name` / `viator_product_code`.
    """
    for b in bookings:
        for it in b.items:
            hotel = None
            if it.room and getattr(it.room, "hotel", None):
                h = it.room.hotel
                hotel = {
                    "id": h.id,
                    "name": h.name,
                    "slug": h.slug,
                    "city": h.city,
                    "country": h.country,
                    "liteapi_hotel_id": h.liteapi_hotel_id,
                    "image_url": _first_image(h.images),
                }
            elif it.liteapi_hotel_id or it.hotel_name:
                hotel = {
                    "id": None,
                    "name": it.hotel_name,
                    "slug": None,
                    "city": None,
                    "country": None,
                    "liteapi_hotel_id": it.liteapi_hotel_id,
                    "image_url": it.image_url,
                }
            it.hotel = hotel

            tour = None
            if it.tour_schedule and getattr(it.tour_schedule, "tour", None):
                t = it.tour_schedule.tour
                tour = {
                    "id": t.id,
                    "name": t.name,
                    "slug": t.slug,
                    "city": t.city,
                    "country": t.country,
                    "viator_product_code": t.viator_product_code,
                    "image_url": _first_image(t.images),
                }
            elif it.viator_product_code or it.tour_name:
                tour = {
                    "id": None,
                    "name": it.tour_name,
                    "slug": None,
                    "city": None,
                    "country": None,
                    "viator_product_code": it.viator_product_code,
                    "image_url": it.image_url,
                }
            it.tour = tour


_BOOKING_EAGER_LOADS = (
    selectinload(Booking.items).selectinload(BookingItem.room).selectinload(Room.hotel),
    selectinload(Booking.items).selectinload(BookingItem.tour_schedule).selectinload(TourSchedule.tour),
    selectinload(Booking.items).selectinload(BookingItem.flight_booking),
)


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
    # rooms walk through `room.hotel` and tours through `tour_schedule.tour`
    # so the My Bookings card can render hotel/tour summaries.
    result = await db.execute(
        select(Booking).options(*_BOOKING_EAGER_LOADS).where(Booking.id == booking.id)
    )
    booking = result.scalar_one()
    _attach_summaries([booking])
    return booking


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
    query = query.options(*_BOOKING_EAGER_LOADS)

    result = await db.execute(query)
    bookings = result.scalars().all()
    _attach_summaries(bookings)

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
        .options(*_BOOKING_EAGER_LOADS)
        .where(Booking.id == booking_id, Booking.user_id == current_user.id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    _attach_summaries([booking])
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
    try:
        booking, supplier_results, stripe_refund_info = await booking_service.cancel_booking(
            db, booking, redis=redis
        )
    except SupplierCancelError as exc:
        # LiteAPI (or another supplier) refused — typically past the rate's
        # cancellation deadline. Surface the upstream message so the UI can
        # explain why instead of showing a generic "failed to cancel" toast.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return CancellationResponse(
        booking_id=booking.id,
        status=booking.status,
        items=supplier_results,
        stripe_refund_id=stripe_refund_info.get("stripe_refund_id"),
        stripe_refund_amount=stripe_refund_info.get("stripe_refund_amount"),
        non_refundable=stripe_refund_info.get("non_refundable", False),
    )
