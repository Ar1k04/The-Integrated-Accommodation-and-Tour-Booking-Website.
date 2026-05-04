"""Orchestrator for the new polymorphic booking flow.

Input: a BookingCreate with items[] (each item is a room, tour, or flight).
Output: a Booking row + one BookingItem per cart entry, with vouchers/loyalty
points applied and inventory locked atomically.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

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
from app.services import duffel_service, email_service, liteapi_service, lock_service, loyalty_service, viator_service, voucher_service
from app.services.duffel_service import DuffelError
from app.services.liteapi_service import LiteAPIError
from app.services.lock_service import LockCollisionError
from app.services.viator_service import ViatorError


class BookingServiceError(ValueError):
    """Domain errors raised by the booking flow."""


def _soft_lock_keys(entry) -> list[str]:
    """Return Redis lock keys to acquire for a BookingItemCreate entry.

    Only local (DB-backed) inventory gets locked; external API items
    (LiteAPI, Viator, Duffel) rely on their own prebook/TTL mechanisms.
    """
    if isinstance(entry, RoomItemCreate):
        if entry.room_id and entry.check_in and entry.check_out and not entry.liteapi_rate_id:
            return [lock_service.room_key(entry.room_id, entry.check_in, entry.check_out)]
    elif isinstance(entry, TourItemCreate):
        if entry.tour_id and entry.tour_date and not entry.viator_product_code:
            return [lock_service.tour_key(entry.tour_id, entry.tour_date)]
    return []


def _daterange(start: date, end: date):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(days=1)


async def _reserve_liteapi_room_item(
    item: RoomItemCreate,
) -> tuple[BookingItem, Decimal]:
    """Prebook a LiteAPI rate and return a BookingItem with liteapi_prebook_id set."""
    try:
        result = await liteapi_service.prebook(item.liteapi_rate_id, guests=item.guests_count)
    except LiteAPIError as exc:
        raise BookingServiceError(f"LiteAPI prebook failed: {exc.message}")

    price = item.liteapi_price if item.liteapi_price else result["price"]
    unit_price = Decimal(str(price)).quantize(Decimal("0.01"))
    subtotal = (unit_price * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.room.value,
        room_id=None,
        check_in=item.check_in,
        check_out=item.check_out,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
        liteapi_prebook_id=result["prebook_id"],
    )
    return bi, subtotal


async def _reserve_room_item(
    db: AsyncSession, item: RoomItemCreate
) -> tuple[BookingItem, Decimal]:
    if item.liteapi_rate_id:
        return await _reserve_liteapi_room_item(item)

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
            .select_from(BookingItem)
            .join(Booking, BookingItem.booking_id == Booking.id)
            .where(
                and_(
                    BookingItem.room_id == item.room_id,
                    BookingItem.item_type == BookingItemType.room.value,
                    Booking.status.in_(["pending", "confirmed"]),
                    BookingItem.check_in < item.check_out,
                    BookingItem.check_out > item.check_in,
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


async def _reserve_viator_tour_item(
    item: TourItemCreate,
) -> tuple[BookingItem, Decimal]:
    """Reserve a Viator tour by checking availability; no local DB locking needed."""
    try:
        avail = await viator_service.check_availability(
            item.viator_product_code, item.tour_date, guests=item.quantity
        )
    except ViatorError as exc:
        raise BookingServiceError(f"Viator availability check failed: {exc.message}")

    price = item.viator_price if item.viator_price else avail.get("price", 0)
    unit_price = Decimal(str(price)).quantize(Decimal("0.01"))
    subtotal = (unit_price * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.tour.value,
        tour_schedule_id=None,
        check_in=item.tour_date,  # store tour_date in check_in for confirm_booking lookup
        viator_product_code=item.viator_product_code,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
    )
    return bi, subtotal


async def _reserve_tour_item(
    db: AsyncSession, item: TourItemCreate
) -> tuple[BookingItem, Decimal]:
    if item.viator_product_code:
        return await _reserve_viator_tour_item(item)

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


async def _reserve_duffel_flight_item(
    db: AsyncSession, item: FlightItemCreate
) -> tuple[BookingItem, Decimal]:
    """Validate a Duffel offer and create a pending FlightBooking snapshot."""
    from app.models.flight_booking import FlightBookingStatus

    try:
        offer = await duffel_service.get_offer(item.duffel_offer_id)
    except DuffelError as exc:
        raise BookingServiceError(f"Duffel offer validation failed: {exc.message}")

    # Extract first-segment details for the snapshot
    first_slice = offer["slices"][0] if offer.get("slices") else {}
    first_seg = first_slice.get("segments", [{}])[0]
    last_slice = offer["slices"][-1] if offer.get("slices") else {}
    last_seg = last_slice.get("segments", [{}])[-1]

    def _parse_dt(s: str) -> datetime:
        if not s:
            return datetime.now(tz=timezone.utc)
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(tz=timezone.utc)

    pax = item.passenger
    flight = FlightBooking(
        duffel_order_id=None,
        airline_name=offer.get("airline_name", "Unknown"),
        flight_number=first_seg.get("flight_number", ""),
        departure_airport=first_slice.get("origin", first_seg.get("origin_iata", "")),
        arrival_airport=last_slice.get("destination", last_seg.get("destination_iata", "")),
        departure_at=_parse_dt(first_seg.get("departure_at", "")),
        arrival_at=_parse_dt(last_seg.get("arrival_at", "")),
        cabin_class=offer.get("cabin_class"),
        passenger_name=f"{pax.first_name} {pax.last_name}",
        passenger_email=pax.email,
        base_amount=offer["total_amount"],
        total_amount=offer["total_amount"],
        currency=offer["currency"],
        status=FlightBookingStatus.pending.value,
        passenger_details={
            "offer_id": item.duffel_offer_id,
            "passenger": pax.model_dump(mode="json"),
        },
    )
    db.add(flight)
    await db.flush()

    unit_price = Decimal(str(offer["total_amount"])).quantize(Decimal("0.01"))
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


async def _reserve_flight_item(
    db: AsyncSession, item: FlightItemCreate
) -> tuple[BookingItem, Decimal]:
    if item.duffel_offer_id:
        return await _reserve_duffel_flight_item(db, item)

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
    redis=None,
) -> Booking:
    """Create a polymorphic booking + items. Runs inside the caller's transaction."""

    owner = str(user_id)
    acquired_lock_keys: list[str] = []

    # Acquire Redis soft-locks for all local inventory items before touching the DB.
    # If any slot is held by a concurrent checkout, raise immediately (→ 409).
    for entry in data.items:
        keys = _soft_lock_keys(entry)
        try:
            for key in keys:
                await lock_service.acquire(redis, key, owner)
                acquired_lock_keys.append(key)
        except LockCollisionError:
            await lock_service.release_many(redis, acquired_lock_keys, owner)
            raise  # propagates to route → HTTP 409

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

    try:
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
    except Exception:
        # Reservation failed — release any acquired locks and re-raise
        await lock_service.release_many(redis, acquired_lock_keys, owner)
        raise

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

    # Store which lock keys this booking holds so confirm/cancel can release them.
    await lock_service.store_booking_locks(redis, booking.id, acquired_lock_keys, owner)

    return booking


async def confirm_booking(
    db: AsyncSession,
    booking: Booking,
    guest_first_name: str = "Guest",
    guest_last_name: str = "Guest",
    guest_email: str = "guest@example.com",
    redis=None,
) -> Booking:
    """Mark booking + items confirmed and award loyalty points based on final total."""

    booking.status = BookingStatus.confirmed.value
    for item in booking.items:
        item.status = BookingItemStatus.confirmed.value
        # Finalize any LiteAPI prebook → real booking
        if item.liteapi_prebook_id and not item.liteapi_booking_id:
            try:
                result = await liteapi_service.book(
                    prebook_id=item.liteapi_prebook_id,
                    guest_first_name=guest_first_name,
                    guest_last_name=guest_last_name,
                    guest_email=guest_email,
                )
                item.liteapi_booking_id = result["liteapi_booking_id"]
            except LiteAPIError as exc:
                logger.warning(
                    "LiteAPI book failed for prebook %s: %s — booking recorded locally",
                    item.liteapi_prebook_id,
                    exc.message,
                )

        # Finalize any Viator tour → real booking
        if item.viator_product_code and not item.viator_booking_ref:
            try:
                tour_date_val = item.check_in or date.today()
                result = await viator_service.book_tour(
                    viator_product_code=item.viator_product_code,
                    tour_date=tour_date_val,
                    guests=item.quantity,
                    guest_first_name=guest_first_name,
                    guest_last_name=guest_last_name,
                    guest_email=guest_email,
                )
                item.viator_booking_ref = result["viator_booking_ref"]
            except ViatorError as exc:
                logger.warning(
                    "Viator book failed for %s: %s — booking recorded locally",
                    item.viator_product_code,
                    exc.message,
                )

        # Finalize any pending Duffel flight → real order
        if item.item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            if flight and flight.status == "pending" and not flight.duffel_order_id:
                details = flight.passenger_details or {}
                if details.get("offer_id"):
                    try:
                        result = await duffel_service.create_order(
                            duffel_offer_id=details["offer_id"],
                            passenger=details.get("passenger", {}),
                            amount=str(flight.total_amount),
                            currency=flight.currency,
                        )
                        flight.duffel_order_id = result["duffel_order_id"]
                        flight.duffel_booking_ref = result.get("duffel_booking_ref")
                        flight.status = "confirmed"
                    except DuffelError as exc:
                        logger.warning(
                            "Duffel order failed for offer %s: %s — booking recorded locally",
                            details.get("offer_id"),
                            exc.message,
                        )

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

    # Release soft-locks — booking is now confirmed, inventory is committed.
    await lock_service.release_booking_locks(redis, booking.id)

    # Non-blocking confirmation email
    try:
        await email_service.send_booking_confirmation(booking, guest_email)
    except Exception as exc:
        logger.warning("Confirmation email failed for booking %s: %s", booking.id, exc)

    return booking


async def cancel_booking(db: AsyncSession, booking: Booking, redis=None) -> Booking:
    """Cancel booking and release inventory (tour slots, room_availability rows)."""

    if booking.status == BookingStatus.cancelled.value:
        return booking

    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        if item.liteapi_booking_id:
            await liteapi_service.cancel_booking(item.liteapi_booking_id)
        if item.viator_booking_ref:
            await viator_service.cancel_booking(item.viator_booking_ref)
        if item.item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            if flight and flight.duffel_order_id:
                await duffel_service.cancel_order(flight.duffel_order_id)
                flight.status = "cancelled"
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

    # Release soft-locks — slot is freed, next user can book.
    await lock_service.release_booking_locks(redis, booking.id)

    # Non-blocking cancellation email — look up user email from booking
    try:
        from app.models.user import User
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        if user and user.email:
            await email_service.send_booking_cancellation(booking, user.email)
    except Exception as exc:
        logger.warning("Cancellation email failed for booking %s: %s", booking.id, exc)

    return booking
