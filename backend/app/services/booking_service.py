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

from app.core.config import settings
from app.core.pricing import compute_room_subtotal
from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking
from app.models.loyalty_tier import LoyaltyTier
from app.models.room import Room
from app.models.user import User
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

    Internal rooms: one key per night (sorted ascending) so overlapping ranges
    collide on at least one shared day.
    LiteAPI rooms: one key per (hotel_id, room_name, dates) tuple to fast-fail
    duplicate prebook attempts before the external HTTP call.
    Viator / Duffel: no Redis lock; their own APIs hold inventory.
    """
    if isinstance(entry, RoomItemCreate):
        if entry.liteapi_rate_id and entry.liteapi_hotel_id and entry.check_in and entry.check_out:
            return [
                lock_service.liteapi_key(
                    entry.liteapi_hotel_id,
                    entry.liteapi_room_name or "",
                    entry.check_in,
                    entry.check_out,
                )
            ]
        if entry.room_id and entry.check_in and entry.check_out:
            return lock_service.room_day_keys(entry.room_id, entry.check_in, entry.check_out)
    elif isinstance(entry, TourItemCreate):
        if entry.tour_id and entry.tour_date and not entry.viator_product_code:
            return [lock_service.tour_key(entry.tour_id, entry.tour_date)]
    return []


def _parse_expiry_seconds(expires_at) -> int | None:
    """Convert LiteAPI's expiryTime (ISO datetime or seconds-from-now) to seconds remaining.

    Returns None if the field is missing/unparseable, so the caller can fall back
    to the default Redis TTL.
    """
    if expires_at is None:
        return None
    try:
        if isinstance(expires_at, (int, float)):
            return max(int(expires_at), 1)
        if isinstance(expires_at, str):
            s = expires_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            now = datetime.now(tz=dt.tzinfo or timezone.utc)
            delta = int((dt - now).total_seconds())
            return delta if delta > 0 else None
    except (ValueError, TypeError):
        return None
    return None


def _daterange(start: date, end: date):
    cur = start
    while cur < end:
        yield cur
        cur += timedelta(days=1)


# Tolerance for price drift between the rate shown to the user (item.liteapi_price)
# and the supplier-confirmed price returned by prebook. Anything bigger surfaces
# as a price-change error so the frontend can re-confirm with the user.
_LITEAPI_PRICE_TOLERANCE = Decimal("1.00")


async def _reserve_liteapi_room_item(
    item: RoomItemCreate,
    voucher_code: str | None = None,
) -> tuple[BookingItem, Decimal, int | None, Decimal]:
    """Prebook a LiteAPI rate and return a BookingItem with liteapi_prebook_id set.

    When voucher_code is provided, it is forwarded to LiteAPI so the discount
    is applied supplier-side. In that case the supplier-confirmed price is
    expected to be LOWER than the quoted price, so the usual drift check is
    relaxed (negative drift = expected discount).

    Returns (BookingItem, subtotal, prebook_ttl_seconds, supplier_discount):
        supplier_discount is (quoted - supplier) * quantity when a voucher was
        applied supplier-side, else 0. Callers sum this across items to record
        the discount on the booking without double-applying it locally.
    """
    try:
        result = await liteapi_service.prebook(
            item.liteapi_rate_id,
            guests=item.guests_count,
            voucher_code=voucher_code,
        )
    except LiteAPIError as exc:
        # Map LiteAPI's noisy upstream errors to user-friendly text.
        # 2001 = "no prebook availability" (room just sold out OR rate cache stale)
        # HTTP 409 = supplier-side price/availability drift since the rate was quoted
        # Both mean: the rate the user clicked is no longer bookable as quoted.
        if exc.code == 2001 or exc.status_code == 409:
            logger.info(
                "LiteAPI prebook unavailable (code=%s, http=%s): %s",
                exc.code, exc.status_code, exc.message,
            )
            raise BookingServiceError(
                "This room just sold out or the price changed. "
                "Please pick different dates or refresh to see the latest rates."
            )
        raise BookingServiceError(f"LiteAPI prebook failed: {exc.message}")

    supplier_price = Decimal(str(result["price"] or 0)).quantize(Decimal("0.01"))
    quoted_price = Decimal(str(item.liteapi_price)).quantize(Decimal("0.01")) if item.liteapi_price else None
    supplier_discount_per_unit = Decimal("0")
    if quoted_price is not None and supplier_price > 0:
        if voucher_code:
            # With a voucher, supplier price is expected to be <= quoted.
            # Only flag an unexpected *upward* drift beyond tolerance.
            if supplier_price - quoted_price > _LITEAPI_PRICE_TOLERANCE:
                raise BookingServiceError(
                    f"LiteAPI rate price increased from {quoted_price} to {supplier_price} "
                    f"({result.get('currency') or 'USD'}) despite voucher. Please re-confirm."
                )
            if quoted_price > supplier_price:
                supplier_discount_per_unit = quoted_price - supplier_price
        else:
            drift = abs(supplier_price - quoted_price)
            if drift > _LITEAPI_PRICE_TOLERANCE:
                raise BookingServiceError(
                    f"LiteAPI rate price changed from {quoted_price} to {supplier_price} "
                    f"({result.get('currency') or 'USD'}). Please re-confirm the rate before booking."
                )

    # Trust the supplier-confirmed price when available; fall back to the quoted
    # price for sandbox responses that omit the amount.
    # LiteAPI returns a per-night rate, so multiply by nights to get the stay
    # subtotal — matches the frontend's `roomRateTotal * nights` computation and
    # the non-LiteAPI room path at _reserve_room_item.
    nights = (item.check_out - item.check_in).days or 1
    unit_price = supplier_price if supplier_price > 0 else (quoted_price or Decimal("0.00"))
    subtotal = (unit_price * nights * item.quantity).quantize(Decimal("0.01"))
    supplier_discount = (supplier_discount_per_unit * nights * item.quantity).quantize(Decimal("0.01"))

    children_ages = list(item.children_ages or [])
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
        adults_count=item.adults or item.guests_count,
        children_count=len(children_ages),
        children_ages=children_ages,
    )
    return bi, subtotal, _parse_expiry_seconds(result.get("expires_at")), supplier_discount


async def _reserve_room_item(
    db: AsyncSession, item: RoomItemCreate, voucher_code: str | None = None
) -> tuple[BookingItem, Decimal, int | None, Decimal]:
    if item.liteapi_rate_id:
        return await _reserve_liteapi_room_item(item, voucher_code=voucher_code)

    if item.check_in >= item.check_out:
        raise BookingServiceError("check_out must be after check_in")

    room = (
        await db.execute(
            select(Room).where(Room.id == item.room_id).with_for_update()
        )
    ).scalar_one_or_none()
    if not room:
        raise BookingServiceError("Room not found")

    adults = item.adults or item.guests_count
    children_ages = list(item.children_ages or [])
    total_occupants = adults + len(children_ages)
    if total_occupants > room.max_guests * item.quantity:
        raise BookingServiceError(
            f"Room allows a maximum of {room.max_guests} guests per room"
        )

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
    subtotal = compute_room_subtotal(
        unit_price,
        nights=nights,
        quantity=item.quantity,
        adults=adults,
        children_ages=children_ages,
        tiers=room.child_age_tiers,
        max_guests=room.max_guests,
    )

    bi = BookingItem(
        item_type=BookingItemType.room.value,
        room_id=item.room_id,
        check_in=item.check_in,
        check_out=item.check_out,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
        adults_count=adults,
        children_count=len(children_ages),
        children_ages=children_ages,
    )
    return bi, subtotal, None, Decimal("0")


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
    db: AsyncSession, item: FlightItemCreate, redis=None,
) -> tuple[BookingItem, Decimal]:
    """Validate a Duffel offer and create a pending FlightBooking snapshot.

    Handles multi-passenger orders: the lead pax populates the dedicated columns,
    all passengers go into JSONB passenger_details["passengers"], and the offer
    snapshot (slices/airline) is preserved so the confirmation page can render
    a full itinerary without re-hitting Duffel.

    If Duffel's individual-offer lookup fails (often happens late in the offer
    TTL) but we have a per-offer snapshot in Redis from /search, fall back to
    that snapshot. The actual create_order step at confirmation time is what
    really validates the offer with Duffel.
    """
    import json as _json
    from app.models.flight_booking import FlightBookingStatus

    offer: dict | None = None
    fetch_error: str | None = None
    try:
        offer = await duffel_service.get_offer(item.duffel_offer_id)
    except DuffelError as exc:
        fetch_error = exc.message

    if offer is None and redis is not None:
        try:
            cached = await redis.get(f"duffel:offer:{item.duffel_offer_id}")
            if cached:
                offer = _json.loads(cached)
        except Exception:
            offer = None

    if offer is None:
        raise BookingServiceError(
            f"Duffel offer validation failed: {fetch_error or 'offer unavailable'}"
        )

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

    passenger_list = item.passengers or ([item.passenger] if item.passenger else [])
    if not passenger_list:
        raise BookingServiceError("At least one passenger is required for a flight booking")

    lead = passenger_list[0]
    total_amount = float(offer["total_amount"])
    pax_count = len(passenger_list)

    flight = FlightBooking(
        duffel_order_id=None,
        airline_name=offer.get("airline_name", "Unknown"),
        flight_number=first_seg.get("flight_number", ""),
        departure_airport=first_slice.get("origin", first_seg.get("origin_iata", "")),
        arrival_airport=last_slice.get("destination", last_seg.get("destination_iata", "")),
        departure_at=_parse_dt(first_seg.get("departure_at", "")),
        arrival_at=_parse_dt(last_seg.get("arrival_at", "")),
        cabin_class=offer.get("cabin_class"),
        passenger_name=f"{lead.first_name} {lead.last_name}",
        passenger_email=lead.email,
        base_amount=total_amount,
        total_amount=total_amount,
        currency=offer["currency"],
        status=FlightBookingStatus.pending.value,
        passenger_details={
            "offer_id": item.duffel_offer_id,
            "passengers": [p.model_dump(mode="json") for p in passenger_list],
            "selected_services": item.selected_services or [],
            "selected_seats": item.selected_seats or {},
            "offer_snapshot": {
                "airline_name": offer.get("airline_name"),
                "airline_iata": offer.get("airline_iata"),
                "cabin_class": offer.get("cabin_class"),
                "slices": offer.get("slices") or [],
                "total_amount": total_amount,
                "currency": offer["currency"],
            },
        },
    )
    db.add(flight)
    await db.flush()

    unit_price = (Decimal(str(total_amount)) / Decimal(pax_count)).quantize(Decimal("0.01"))
    subtotal = Decimal(str(total_amount)).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.flight.value,
        flight_booking_id=flight.id,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=pax_count,
        status=BookingItemStatus.pending.value,
    )
    return bi, subtotal


async def _reserve_flight_item(
    db: AsyncSession, item: FlightItemCreate, redis=None,
) -> tuple[BookingItem, Decimal]:
    if item.duffel_offer_id:
        return await _reserve_duffel_flight_item(db, item, redis=redis)

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

    # Peek the voucher (if any) so we can decide whether to push it to LiteAPI
    # at prebook time vs. apply it locally after the cart is reserved.
    supplier_side_voucher: str | None = None
    peeked_voucher = None
    if data.voucher_code:
        peeked_voucher = await voucher_service.peek_voucher(db, data.voucher_code)
        all_liteapi_hotels = bool(data.items) and all(
            isinstance(e, RoomItemCreate) and e.liteapi_rate_id for e in data.items
        )
        if (
            peeked_voucher
            and peeked_voucher.liteapi_sync_status == "synced"
            and peeked_voucher.applicable_to in ("all", "hotel")
            and peeked_voucher.guest_id is None
            and all_liteapi_hotels
        ):
            # Pre-validate against the *quoted* (pre-discount) subtotal so
            # min_order_value / budget / guest checks use the right baseline.
            # liteapi_price is per-night; multiply by nights to get stay total.
            est_quoted_subtotal = sum(
                (
                    Decimal(str(e.liteapi_price or 0))
                    * e.quantity
                    * max((e.check_out - e.check_in).days, 1)
                    for e in data.items
                ),
                Decimal("0"),
            )
            try:
                await voucher_service.validate_voucher(
                    db, data.voucher_code, user_id, est_quoted_subtotal
                )
                supplier_side_voucher = data.voucher_code
            except voucher_service.VoucherError:
                # Fall through to local validation later (which will surface
                # the same error to the caller in a single place).
                supplier_side_voucher = None

    items: list[BookingItem] = []
    running_subtotal = Decimal("0")
    supplier_discount_total = Decimal("0")

    try:
        for entry in data.items:
            expires_in: int | None = None
            supplier_discount = Decimal("0")
            if isinstance(entry, RoomItemCreate):
                bi, subtotal, expires_in, supplier_discount = await _reserve_room_item(
                    db, entry, voucher_code=supplier_side_voucher
                )
            elif isinstance(entry, TourItemCreate):
                bi, subtotal = await _reserve_tour_item(db, entry)
            elif isinstance(entry, FlightItemCreate):
                bi, subtotal = await _reserve_flight_item(db, entry, redis=redis)
            else:
                raise BookingServiceError("Unknown item type in cart")

            # Shrink the LiteAPI lock TTL to match the external prebook expiry
            # so the Redis lock cannot outlive the upstream hold.
            if expires_in is not None and redis is not None:
                ttl = min(expires_in, lock_service.CHECKOUT_LOCK_TTL)
                for key in _soft_lock_keys(entry):
                    try:
                        await redis.expire(key, ttl)
                    except Exception as exc:
                        logger.warning("TTL shrink failed for %s: %s", key, exc)

            bi.booking_id = booking.id
            db.add(bi)
            items.append(bi)
            running_subtotal += subtotal
            supplier_discount_total += supplier_discount
    except Exception:
        # Reservation failed — release any acquired locks and re-raise
        await lock_service.release_many(redis, acquired_lock_keys, owner)
        raise

    # Gross subtotal = what the user saw before any discount. When a voucher is
    # applied supplier-side the supplier returns a net-of-discount price, so we
    # add the discount back to reconstruct the pre-discount amount. This is the
    # baseline used for tier/voucher/tax math so it matches the frontend.
    gross_subtotal = (running_subtotal + supplier_discount_total).quantize(Decimal("0.01"))
    booking.total_price = gross_subtotal

    # Tier discount: apply member discount before voucher and points
    tier_discount = Decimal("0")
    user_obj = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user_obj and user_obj.loyalty_tier_id:
        tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == user_obj.loyalty_tier_id))).scalar_one_or_none()
        if tier and tier.discount_percent > 0:
            tier_discount = (gross_subtotal * Decimal(str(tier.discount_percent)) / Decimal("100")).quantize(Decimal("0.01"))
            booking.tier_discount = float(tier_discount)

    discount = Decimal("0")
    if supplier_side_voucher and peeked_voucher is not None:
        # Voucher already applied at the supplier — record usage without
        # double-discounting. running_subtotal already reflects the supplier
        # discount, so booking.total_price is correct.
        await voucher_service.record_usage_only(
            db, booking, peeked_voucher, user_id, supplier_discount_total
        )
        discount = Decimal("0")  # already baked into running_subtotal
    elif data.voucher_code:
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

    # Tax on the pre-discount subtotal — matches the frontend display.
    taxes = (gross_subtotal * Decimal(str(settings.TAX_RATE))).quantize(Decimal("0.01"))

    # Surface the supplier-side voucher discount on the booking so MyBookings
    # can display it. Local voucher path already set discount_amount via
    # voucher_service.apply_voucher.
    if supplier_side_voucher and supplier_discount_total > 0:
        booking.discount_amount = float(supplier_discount_total.quantize(Decimal("0.01")))

    booking.subtotal = gross_subtotal
    booking.taxes = taxes

    final_total = gross_subtotal + taxes - tier_discount - supplier_discount_total - discount - redeem_discount
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
    guest_phone: str | None = None,
    redis=None,
) -> Booking:
    """Mark booking + items confirmed and award loyalty points based on final total."""

    booking.status = BookingStatus.confirmed.value
    for item in booking.items:
        item.status = BookingItemStatus.confirmed.value
        # Finalize any LiteAPI prebook → real booking
        if item.liteapi_prebook_id and not item.liteapi_booking_id:
            holder = {
                "firstName": guest_first_name,
                "lastName": guest_last_name,
                "email": guest_email,
            }
            if guest_phone:
                holder["phoneNumber"] = guest_phone
            # One guest entry per room (occupancyNumber starts at 1 per LiteAPI spec)
            guests_payload = [
                {
                    "occupancyNumber": i + 1,
                    "firstName": guest_first_name,
                    "lastName": guest_last_name,
                    "email": guest_email,
                }
                for i in range(max(1, item.quantity))
            ]
            try:
                result = await liteapi_service.book(
                    prebook_id=item.liteapi_prebook_id,
                    holder=holder,
                    guests=guests_payload,
                    client_reference=f"BK-{booking.id}-{item.id}",
                )
                item.liteapi_booking_id = result["liteapi_booking_id"]
                item.supplier_status = result.get("status") or "CONFIRMED"
                item.supplier_status_synced_at = datetime.now(timezone.utc)
            except LiteAPIError as exc:
                logger.warning(
                    "LiteAPI book failed for prebook %s: %s — booking recorded locally",
                    item.liteapi_prebook_id,
                    exc.message,
                )
                item.supplier_status = "BOOK_FAILED"
                item.supplier_status_synced_at = datetime.now(timezone.utc)

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
                    pax_list = details.get("passengers") or (
                        [details["passenger"]] if details.get("passenger") else []
                    )
                    try:
                        result = await duffel_service.create_order(
                            duffel_offer_id=details["offer_id"],
                            passengers=pax_list,
                            amount=str(flight.total_amount),
                            currency=flight.currency,
                            services=details.get("selected_services") or None,
                            selected_seats=details.get("selected_seats") or None,
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


async def cancel_booking(db: AsyncSession, booking: Booking, redis=None) -> tuple[Booking, list[dict]]:
    """
    Cancel booking and release inventory (tour slots, room_availability rows).

    Returns (booking, supplier_results) where supplier_results is a list of
    per-item dicts capturing what each upstream supplier reported (LiteAPI's
    refund_amount, cancellation_fee, etc.). The frontend uses this to show
    the user whether they got a refund.
    """

    supplier_results: list[dict] = []
    if booking.status == BookingStatus.cancelled.value:
        return booking, supplier_results

    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        supplier_entry: dict | None = None
        if item.liteapi_booking_id:
            result = await liteapi_service.cancel_booking(item.liteapi_booking_id)
            if result:
                item.supplier_status = result.get("status") or "CANCELLED"
                item.supplier_status_synced_at = datetime.now(timezone.utc)
                supplier_entry = {
                    "item_id": item.id,
                    "supplier": "liteapi",
                    "status": result.get("status"),
                    "refund_amount": result.get("refund_amount"),
                    "cancellation_fee": result.get("cancellation_fee"),
                    "currency": result.get("currency"),
                }
        elif item.liteapi_prebook_id:
            # Prebook never finalized — record supplier-side as cancelled locally
            item.supplier_status = "CANCELLED"
            item.supplier_status_synced_at = datetime.now(timezone.utc)
            supplier_entry = {
                "item_id": item.id,
                "supplier": "liteapi",
                "status": "CANCELLED",
                "refund_amount": None,
                "cancellation_fee": 0.0,
                "currency": None,
            }
        if item.viator_booking_ref:
            await viator_service.cancel_booking(item.viator_booking_ref)
            supplier_entry = supplier_entry or {
                "item_id": item.id,
                "supplier": "viator",
                "status": "CANCELLED",
                "refund_amount": None,
                "cancellation_fee": None,
                "currency": None,
            }
        if item.item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            if flight and flight.duffel_order_id:
                await duffel_service.cancel_order(flight.duffel_order_id)
                flight.status = "cancelled"
                supplier_entry = supplier_entry or {
                    "item_id": item.id,
                    "supplier": "duffel",
                    "status": "CANCELLED",
                    "refund_amount": None,
                    "cancellation_fee": None,
                    "currency": None,
                }
        item.status = BookingItemStatus.cancelled.value
        if supplier_entry is None:
            supplier_entry = {
                "item_id": item.id,
                "supplier": "local",
                "status": "CANCELLED",
                "refund_amount": None,
                "cancellation_fee": None,
                "currency": None,
            }
        supplier_results.append(supplier_entry)
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

    # Reverse loyalty points: deduct earned, restore redeemed
    try:
        await loyalty_service.reverse_booking_points(db, booking.id)
        booking.points_earned = 0
        booking.points_redeemed = 0
    except Exception as exc:
        logger.warning("Loyalty reversal failed for booking %s: %s", booking.id, exc)

    await db.flush()
    await db.refresh(booking)

    # Release soft-locks — slot is freed, next user can book.
    await lock_service.release_booking_locks(redis, booking.id)

    # Non-blocking cancellation email — look up user email from booking
    try:
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        if user and user.email:
            await email_service.send_booking_cancellation(booking, user.email)
    except Exception as exc:
        logger.warning("Cancellation email failed for booking %s: %s", booking.id, exc)

    return booking, supplier_results


async def sync_supplier_status(db: AsyncSession, item: BookingItem) -> str | None:
    """Refresh BookingItem.supplier_status from LiteAPI's authoritative source.

    Prefers the booking ID (post-confirmation). Falls back to the prebook ID
    (pre-payment state). Returns the new supplier_status, or None if the item
    has no LiteAPI reference or the API call fails.
    """
    raw_status: str | None = None
    try:
        if item.liteapi_booking_id:
            data = await liteapi_service.get_booking(item.liteapi_booking_id)
            raw_status = data.get("status") or data.get("bookingStatus")
        elif item.liteapi_prebook_id:
            data = await liteapi_service.get_prebook(item.liteapi_prebook_id)
            raw_status = data.get("status") or data.get("prebookStatus")
        else:
            return None
    except LiteAPIError as exc:
        logger.warning(
            "LiteAPI status sync failed for item %s: %s",
            item.id,
            getattr(exc, "message", str(exc)),
        )
        return None

    if raw_status:
        item.supplier_status = raw_status
        item.supplier_status_synced_at = datetime.now(timezone.utc)
        await db.flush()
    return raw_status
