"""
Availability service with row-level locking to prevent double-booking.

Uses SELECT ... FOR UPDATE on the Room row to serialise concurrent booking
attempts for the same room & overlapping dates.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.promo_code import PromoCode
from app.models.room import Room


async def check_and_reserve(
    db: AsyncSession,
    room_id: uuid.UUID,
    check_in: date,
    check_out: date,
    user_id: uuid.UUID,
    guests_count: int,
    special_requests: str | None = None,
    promo_code: str | None = None,
) -> Booking:
    """
    Atomically checks availability and creates a booking.

    Acquires a FOR UPDATE lock on the Room row so that concurrent requests
    for the same room are serialised at the DB level.
    """
    if check_in >= check_out:
        raise ValueError("check_out must be after check_in")

    room = (
        await db.execute(
            select(Room).where(Room.id == room_id).with_for_update()
        )
    ).scalar_one_or_none()

    if not room:
        raise ValueError("Room not found")

    if guests_count > room.max_guests:
        raise ValueError(f"Room supports at most {room.max_guests} guests")

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

    if overlap_count >= room.total_quantity:
        raise ValueError("No rooms available for the selected dates")

    nights = (check_out - check_in).days
    total_price = Decimal(str(room.price_per_night)) * nights

    promo_code_id = None
    if promo_code:
        promo = (
            await db.execute(
                select(PromoCode).where(
                    and_(
                        PromoCode.code == promo_code,
                        PromoCode.is_active == True,  # noqa: E712
                    )
                )
            )
        ).scalar_one_or_none()

        if promo and _promo_is_valid(promo, total_price):
            discount = total_price * Decimal(str(promo.discount_percent)) / 100
            total_price -= discount
            promo_code_id = promo.id
            promo.current_uses += 1

    booking = Booking(
        user_id=user_id,
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        guests_count=guests_count,
        total_price=total_price,
        special_requests=special_requests,
        promo_code_id=promo_code_id,
    )
    db.add(booking)
    await db.flush()
    await db.refresh(booking)
    return booking


def _promo_is_valid(promo: PromoCode, booking_amount: Decimal) -> bool:
    from datetime import datetime, timezone

    if promo.expires_at and promo.expires_at < datetime.now(timezone.utc):
        return False
    if promo.current_uses >= promo.max_uses:
        return False
    if booking_amount < Decimal(str(promo.min_booking_amount)):
        return False
    return True
