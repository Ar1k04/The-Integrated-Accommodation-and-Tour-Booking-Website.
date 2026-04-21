"""Orchestrator for the new polymorphic booking flow.

Input: a BookingCreate with items[] (each item is a room, tour, or flight).
Output: a Booking row + one BookingItem per cart entry, with vouchers/loyalty
points applied and inventory locked atomically.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking
from app.models.room import Room
from app.models.room_availability import RoomAvailability, RoomAvailabilityStatus
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.schemas.booking import BookingCreate
from app.schemas.booking_item import (
    FlightItemCreate,
    RoomItemCreate,
    TourItemCreate,
)
from app.services import loyalty_service, voucher_service


class BookingServiceError(ValueError):
    """Domain errors raised by the booking flow."""


def _daterange(start: date, end: date):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(days=1)


async def _reserve_room_item(
    db: AsyncSession, item: RoomItemCreate
) -> tuple[BookingItem, Decimal]:
    if item.check_in >= item.check_out:
        raise BookingServiceError("check_out must be after check_in")

    room = (
        await db.execute(
            select(Room).where(Room.id == item.room_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not room:
        raise BookingServiceError("Room not found")

    if item.guests_count > room.max_guests:
        raise BookingServiceError(f"Room allows a maximum of {room.max_guests} guests")

    overlap = (
        await db.execute(
            select(func.count())
            .select_from(Booking)
            .where(
                and_(
                    Booking.room_id == item.room_id,
                    Booking.status.in_(["pending", "confirmed"]),
                    Booking.check_in < item.check_out,
                    Booking.check_out > item.check_in,
                )
            )
        )
    ).scalar() or 0
    if overlap >= room.total_quantity:
        raise BookingServiceError("Room is not available for the selected dates")

    for d in _daterange(item.check_in, item.check_out):
        existing = (
            await db.execute(
                select(RoomAvailability).where(
                    and_(RoomAvailability.room_id == item.room_id, RoomAvailability.date == d)
                )
            )
        ).scalar_one_or_none()
        if existing:
            if existing.status == RoomAvailabilityStatus.blocked.value:
                raise BookingServiceError(f"Room is blocked on {d.isoformat()}")
            existing.status = RoomAvailabilityStatus.booked.value
        else:
            db.add(
                RoomAvailability(
                    room_id=item.room_id,
                    date=d,
                    status=RoomAvailabilityStatus.booked.value,
                )
            )

    nights = (item.check_out - item.check_in).days
    unit_price = Decimal(str(room.price_per_night))
    subtotal = (unit_price * nights * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.room.value,
        room_id=item.room_id,
        check_in=item.check_in,
        check_out=item.check_out,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
    )
    return bi, subtotal


async def _reserve_tour_item(
    db: AsyncSession, item: TourItemCreate
) -> tuple[BookingItem, Decimal]:
    tour = (
        await db.execute(select(Tour).where(Tour.id == item.tour_id).with_for_update())
    ).scalar_one_or_none()
    if not tour:
        raise BookingServiceError("Tour not found")

    schedule = (
        await db.execute(
            select(TourSchedule).where(
                and_(TourSchedule.tour_id == item.tour_id, TourSchedule.available_date == item.tour_date)
            ).with_for_update()
        )
    ).scalar_one_or_none()
    if not schedule:
        schedule = TourSchedule(
            tour_id=item.tour_id,
            available_date=item.tour_date,
            total_slots=tour.max_participants,
            booked_slots=0,
        )
        db.add(schedule)
        await db.flush()

    if schedule.booked_slots + item.quantity > schedule.total_slots:
        remaining = schedule.total_slots - schedule.booked_slots
        raise BookingServiceError(f"Only {max(0, remaining)} spots left for this date")

    schedule.booked_slots += item.quantity

    unit_price = Decimal(str(tour.price_per_person))
    subtotal = (unit_price * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.tour.value,
        tour_schedule_id=schedule.id,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
    )
    return bi, subtotal


async def _reserve_flight_item(
    db: AsyncSession, item: FlightItemCreate
) -> tuple[BookingItem, Decimal]:
    flight = (
        await db.execute(
            select(FlightBooking).where(FlightBooking.id == item.flight_booking_id)
        )
    ).scalar_one_or_none()
    if not flight:
        raise BookingServiceError("Flight booking not found")

    unit_price = Decimal(str(flight.total_amount))
    subtotal = (unit_price * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.flight.value,
        flight_booking_id=flight.id,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
    )
    return bi, subtotal


async def create_booking(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: BookingCreate,
) -> Booking:
    """Create a polymorphic booking + items. Runs inside the caller's transaction."""

    booking = Booking(
        user_id=user_id,
        total_price=Decimal("0"),
        status=BookingStatus.pending.value,
        special_requests=data.special_requests,
    )
    db.add(booking)
    await db.flush()

    items: list[BookingItem] = []
    running_subtotal = Decimal("0")

    for entry in data.items:
        if isinstance(entry, RoomItemCreate):
            bi, subtotal = await _reserve_room_item(db, entry)
        elif isinstance(entry, TourItemCreate):
            bi, subtotal = await _reserve_tour_item(db, entry)
        elif isinstance(entry, FlightItemCreate):
            bi, subtotal = await _reserve_flight_item(db, entry)
        else:
            raise BookingServiceError("Unknown item type in cart")

        bi.booking_id = booking.id
        db.add(bi)
        items.append(bi)
        running_subtotal += subtotal

    first_room_entry = next(
        (e for e in data.items if isinstance(e, RoomItemCreate)), None
    )
    first_room_item = next((i for i in items if i.item_type == "room"), None)
    if first_room_item:
        booking.room_id = first_room_item.room_id
        booking.check_in = first_room_item.check_in
        booking.check_out = first_room_item.check_out
        booking.guests_count = first_room_entry.guests_count if first_room_entry else first_room_item.quantity

    booking.total_price = running_subtotal.quantize(Decimal("0.01"))

    discount = Decimal("0")
    if data.voucher_code:
        voucher = await voucher_service.validate_voucher(
            db, data.voucher_code, user_id, running_subtotal
        )
        discount = await voucher_service.apply_voucher(db, booking, voucher, user_id)

    redeem_discount = Decimal("0")
    if data.points_to_redeem > 0:
        _, redeem_discount = await loyalty_service.redeem_points(
            db,
            user_id=user_id,
            booking_id=booking.id,
            points=data.points_to_redeem,
            description=f"Redeemed at booking {booking.id}",
        )
        booking.points_redeemed = data.points_to_redeem

    final_total = running_subtotal - discount - redeem_discount
    if final_total < 0:
        final_total = Decimal("0")
    booking.total_price = final_total.quantize(Decimal("0.01"))

    await db.flush()
    await db.refresh(booking)
    return booking


async def confirm_booking(db: AsyncSession, booking: Booking) -> Booking:
    """Mark booking + items confirmed and award loyalty points based on final total."""

    booking.status = BookingStatus.confirmed.value
    for item in booking.items:
        item.status = BookingItemStatus.confirmed.value

    points = int(Decimal(str(booking.total_price)))
    if points > 0:
        await loyalty_service.award_points(
            db,
            user_id=booking.user_id,
            booking_id=booking.id,
            amount=points,
            description=f"Earned from booking {booking.id}",
        )
        booking.points_earned = points

    await db.flush()
    await db.refresh(booking)
    return booking


async def cancel_booking(db: AsyncSession, booking: Booking) -> Booking:
    """Cancel booking and release inventory (tour slots, room_availability rows)."""

    if booking.status == BookingStatus.cancelled.value:
        return booking

    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        item.status = BookingItemStatus.cancelled.value
        if item.item_type == BookingItemType.tour.value and item.tour_schedule_id:
            schedule = (
                await db.execute(
                    select(TourSchedule).where(TourSchedule.id == item.tour_schedule_id).with_for_update()
                )
            ).scalar_one_or_none()
            if schedule:
                schedule.booked_slots = max(0, schedule.booked_slots - item.quantity)
        elif item.item_type == BookingItemType.room.value and item.room_id and item.check_in and item.check_out:
            for d in _daterange(item.check_in, item.check_out):
                existing = (
                    await db.execute(
                        select(RoomAvailability).where(
                            and_(
                                RoomAvailability.room_id == item.room_id,
                                RoomAvailability.date == d,
                            )
                        )
                    )
                ).scalar_one_or_none()
                if existing and existing.status == RoomAvailabilityStatus.booked.value:
                    existing.status = RoomAvailabilityStatus.available.value

    await db.flush()
    await db.refresh(booking)
    return booking
