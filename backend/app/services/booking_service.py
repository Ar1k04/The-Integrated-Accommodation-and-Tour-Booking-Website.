"""Orchestrator for the new polymorphic booking flow.

Input: a BookingCreate with items[] (each item is a room, tour, or flight).
Output: a Booking row + one BookingItem per cart entry, with vouchers/loyalty
points applied and inventory locked atomically.
"""
import asyncio
import logging
import random
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.pricing import (
    AgeBandError,
    compute_room_subtotal,
    compute_tour_subtotal,
    compute_tour_subtotal_from_bands,
)
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
from app.services.duffel_service import DuffelError, is_retryable_duffel_error
from app.services.liteapi_service import LiteAPIError
from app.services.lock_service import LockCollisionError
from app.services.viator_service import ViatorError


# User-friendly messages for the most common Duffel failures. Generic fallback
# is used when the error code isn't mapped.
DUFFEL_USER_MESSAGES = {
    "offer_no_longer_available": "This flight offer expired before we could book it. Please search again.",
    "airline_error": "The airline rejected this booking. Your payment has been refunded.",
    "insufficient_balance": "We could not complete your flight booking right now. Your payment has been refunded.",
    "validation_error": "There was a problem with the passenger information. Your payment has been refunded.",
}
DUFFEL_USER_MESSAGE_FALLBACK = "Your flight booking could not be completed. Your payment has been refunded."


def _duffel_user_message(error_code: str | None, error_type: str | None) -> str:
    """Pick a user-friendly explanation. Never returns raw Duffel internals."""
    if error_code and error_code in DUFFEL_USER_MESSAGES:
        return DUFFEL_USER_MESSAGES[error_code]
    if error_type and error_type in DUFFEL_USER_MESSAGES:
        return DUFFEL_USER_MESSAGES[error_type]
    return DUFFEL_USER_MESSAGE_FALLBACK


class BookingServiceError(ValueError):
    """Domain errors raised by the booking flow."""


class SupplierCancelError(BookingServiceError):
    """An upstream supplier (LiteAPI / Viator / Duffel) refused a cancel.

    Distinct from BookingServiceError so the route can map it to HTTP 409 with
    the supplier's message intact — important for cases like "past the rate's
    cancellation deadline" where the user needs to see *why* the cancel was
    refused rather than a generic failure."""


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
            # MONEY-03: a non-positive "seconds from now" means the supplier
            # hold is already gone — fall back to the default lock TTL instead
            # of clamping to a near-zero 1s window.
            return int(expires_at) if expires_at > 0 else None
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
    # Parse the cancellation deadline from LiteAPI (ISO string). Persisting it
    # means the My Bookings UI can show the user exactly when free cancellation
    # ends — no need to chase the rate again later.
    deadline_iso = result.get("cancellation_deadline")
    cancellation_deadline = None
    if isinstance(deadline_iso, str):
        try:
            cancellation_deadline = datetime.fromisoformat(deadline_iso.replace("Z", "+00:00"))
        except ValueError:
            cancellation_deadline = None
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
        liteapi_hotel_id=item.liteapi_hotel_id,
        hotel_name=item.liteapi_hotel_name,
        image_url=item.liteapi_hotel_image_url,
        cancellation_deadline=cancellation_deadline,
        refundable=result.get("refundable"),
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

    # Snapshot the partner's cancellation policy onto the item so a later edit
    # to room.cancellation_* can't change what an already-confirmed booking owes.
    # free_cancellation_days before check-in → free cancel deadline.
    cancellation_deadline = datetime.combine(
        item.check_in, datetime.min.time(), tzinfo=timezone.utc
    ) - timedelta(days=room.free_cancellation_days)

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
        refundable=room.refundable,
        cancellation_deadline=cancellation_deadline,
        cancellation_fee_percent=room.cancellation_fee_percent,
    )
    return bi, subtotal, None, Decimal("0")


async def _reserve_viator_tour_item(
    item: TourItemCreate,
) -> tuple[BookingItem, Decimal]:
    """Reserve a Viator tour by checking availability; no local DB locking needed."""
    adults = item.adults or item.quantity
    children_ages = list(item.children_ages or [])

    try:
        avail = await viator_service.check_availability(
            item.viator_product_code,
            item.tour_date,
            adults=adults,
            children_ages=children_ages,
        )
    except ViatorError as exc:
        raise BookingServiceError(f"Viator availability check failed: {exc.message}")

    # Average per-person price returned by Viator already reflects per-band
    # discounts. We persist unit_price as that average so the BookingItem
    # subtotal stays consistent with what we showed the user at quote time.
    price = item.viator_price if item.viator_price else avail.get("price", 0)
    unit_price = Decimal(str(price)).quantize(Decimal("0.01"))
    subtotal = (unit_price * item.quantity).quantize(Decimal("0.01"))

    bi = BookingItem(
        item_type=BookingItemType.tour.value,
        tour_schedule_id=None,
        check_in=item.tour_date,  # store tour_date in check_in for confirm_booking lookup
        viator_product_code=item.viator_product_code,
        tour_name=item.viator_tour_name,
        image_url=item.viator_tour_image_url,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
        adults_count=adults,
        children_count=len(children_ages),
        children_ages=children_ages,
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

    adults = item.adults or item.quantity
    children_ages = list(item.children_ages or [])

    # Partner tours price by their own age bands (same model as Viator). Tours
    # without bands (legacy/seeded) fall back to the default child tiers
    # (0–5 free, 6–12 50% off, 13–17 25% off).
    unit_price = Decimal(str(tour.price_per_person))
    if tour.age_bands:
        try:
            subtotal = compute_tour_subtotal_from_bands(
                tour.age_bands,
                adults=adults,
                children_ages=children_ages,
                fallback_price=unit_price,
            )
        except AgeBandError as exc:
            raise BookingServiceError(str(exc))
    else:
        subtotal = compute_tour_subtotal(
            unit_price,
            adults=adults,
            children_ages=children_ages,
        )

    bi = BookingItem(
        item_type=BookingItemType.tour.value,
        tour_schedule_id=schedule.id,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=item.quantity,
        status=BookingItemStatus.pending.value,
        adults_count=adults,
        children_count=len(children_ages),
        children_ages=children_ages,
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

    # Track adult/child split for audit + so confirm_booking sends the
    # right per-passenger fields to /air/orders. Child ages live on each
    # PassengerInfo (.age) too, but the BookingItem-level summary is
    # cheaper to read for analytics / display.
    adults_count = item.adults if item.adults is not None else pax_count
    children_ages_snapshot = list(item.children_ages or [])

    bi = BookingItem(
        item_type=BookingItemType.flight.value,
        flight_booking_id=flight.id,
        unit_price=unit_price,
        subtotal=subtotal,
        quantity=pax_count,
        status=BookingItemStatus.pending.value,
        adults_count=adults_count,
        children_count=len(children_ages_snapshot),
        children_ages=children_ages_snapshot,
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


async def _finalize_duffel_flight(
    db: AsyncSession,
    booking: Booking,
    item: BookingItem,
    flight: FlightBooking,
    *,
    max_attempts: int = 3,
) -> tuple[bool, DuffelError | None]:
    """Try to create the Duffel order for a pending FlightBooking.

    Retries transient failures up to ``max_attempts`` with jittered backoff.
    Permanent failures (expired offer, validation, balance) skip retries.

    On success: mutates ``flight`` (duffel_order_id, status, booking_ref) and
    clears any previous ``last_error`` on ``passenger_details``. Caller should
    set ``item.status`` to confirmed.

    On failure: persists a structured error blob on
    ``flight.passenger_details['last_error']`` for diagnostics and admin retry.
    Caller MUST NOT mark ``item.status`` as confirmed.
    """
    details = flight.passenger_details or {}
    offer_id = details.get("offer_id")
    if not offer_id:
        # Nothing to do — no offer snapshot. Treat as permanent failure with a
        # synthetic error so the caller still routes through the failure path.
        err = DuffelError(422, "Flight booking has no associated Duffel offer")
        flight.passenger_details = {
            **details,
            "last_error": {
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "status_code": 422,
                "error_type": None,
                "error_code": "missing_offer",
                "message": err.message,
                "attempts": 0,
                "offer_id": None,
                "amount": str(flight.total_amount),
                "currency": flight.currency,
                "passenger_count": 0,
            },
        }
        return False, err

    pax_list = details.get("passengers") or (
        [details["passenger"]] if details.get("passenger") else []
    )
    amount = str(flight.total_amount)
    currency = flight.currency

    # [0.5s, 2.0s] base delays — short enough to keep total worst-case under
    # ~3s on top of the Stripe-confirm latency budget.
    base_delays = [0.5, 2.0]
    last_error: DuffelError | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await duffel_service.create_order(
                duffel_offer_id=offer_id,
                passengers=pax_list,
                amount=amount,
                currency=currency,
                services=details.get("selected_services") or None,
                selected_seats=details.get("selected_seats") or None,
            )
        except DuffelError as exc:
            last_error = exc
            retryable = is_retryable_duffel_error(exc)
            if attempt < max_attempts and retryable:
                logger.warning(
                    "Duffel create_order retryable failure booking=%s flight=%s "
                    "offer=%s attempt=%d/%d status=%s code=%s message=%s",
                    booking.id, flight.id, offer_id, attempt, max_attempts,
                    exc.status_code, exc.error_code, exc.message,
                )
                delay = base_delays[attempt - 1] + random.uniform(0, 0.5)
                await asyncio.sleep(delay)
                continue
            # Either retries exhausted, or permanent failure → break to record.
            break
        else:
            # Success path
            flight.duffel_order_id = result["duffel_order_id"]
            flight.duffel_booking_ref = result.get("duffel_booking_ref")
            flight.status = "confirmed"
            # Sync local total_amount with what Duffel actually charged from balance.
            # `result["total_amount"]` is the upstream order total; differs from
            # `flight.total_amount` (search-time snapshot) whenever the offer was
            # re-quoted between search and book. Keeping the local row in sync
            # makes downstream accounting (refunds, reports) match the supplier.
            charged_total = result.get("total_amount")
            if charged_total is not None:
                try:
                    from decimal import Decimal as _Decimal
                    flight.total_amount = _Decimal(str(charged_total))
                except Exception:
                    pass
            charged_currency = result.get("currency")
            if charged_currency:
                flight.currency = charged_currency
            # Clear any cached error from a previous failed attempt.
            cleaned = {k: v for k, v in (flight.passenger_details or {}).items() if k != "last_error"}
            flight.passenger_details = cleaned
            return True, None

    # All attempts exhausted (or permanent error on attempt 1).
    assert last_error is not None
    logger.error(
        "Duffel create_order failed permanently booking=%s flight=%s offer=%s "
        "amount=%s %s pax=%d status=%s type=%s code=%s message=%s attempts=%d",
        booking.id, flight.id, offer_id, amount, currency, len(pax_list),
        last_error.status_code, last_error.error_type, last_error.error_code,
        last_error.message, attempt,
    )
    flight.passenger_details = {
        **(flight.passenger_details or {}),
        "last_error": {
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "status_code": last_error.status_code,
            "error_type": last_error.error_type,
            "error_code": last_error.error_code,
            "message": last_error.message,
            "attempts": attempt,
            "offer_id": offer_id,
            "amount": amount,
            "currency": currency,
            "passenger_count": len(pax_list),
        },
    }
    return False, last_error


def _build_failed_item_entry(item: BookingItem, flight: FlightBooking, exc: DuffelError | None) -> dict:
    """Serialize a failed-flight outcome for the API response."""
    err_code = exc.error_code if exc else None
    err_type = exc.error_type if exc else None
    return {
        "item_id": str(item.id),
        "type": "flight",
        "error_code": err_code,
        "error_type": err_type,
        "message": exc.message if exc else None,
        "user_message": _duffel_user_message(err_code, err_type),
    }


async def confirm_booking(
    db: AsyncSession,
    booking: Booking,
    guest_first_name: str = "Guest",
    guest_last_name: str = "Guest",
    guest_email: str = "guest@example.com",
    guest_phone: str | None = None,
    redis=None,
) -> tuple[Booking, dict]:
    """Finalize each item with its supplier and decide the booking outcome.

    Returns ``(booking, outcome)``. ``outcome`` shape:
      {
        "status": "confirmed" | "partial" | "failed" | "failed_refund_pending",
        "confirmed_items": [{"item_id", "type"}],
        "failed_items": [{"item_id", "type", "error_code", "user_message", ...}],
        "refund": None | {"issued": bool, "amount_usd": float, "currency": str,
                          "stripe_refund_id": str | None, "partial": bool,
                          "reason": str | None},
      }

    Idempotent: a second call once the booking has reached a terminal state
    (confirmed or cancelled) returns the cached outcome derived from the
    persisted state without re-running supplier calls.
    """

    # RACE-01/03: serialize concurrent confirmations of the same booking
    # (Stripe webhook vs /confirm-stripe). Take a row
    # lock and re-read the latest status BEFORE the terminal short-circuit so
    # a second caller waits, then sees the terminal state and returns the
    # cached outcome instead of re-running supplier calls / re-awarding points.
    await db.execute(
        select(Booking.id).where(Booking.id == booking.id).with_for_update()
    )
    await db.refresh(booking, attribute_names=["status"])

    # Idempotency: terminal-state short-circuit. Re-derive the outcome from
    # what's already persisted so the caller can render the same response.
    if booking.status in (BookingStatus.confirmed.value, BookingStatus.cancelled.value):
        return booking, _outcome_from_persisted_state(booking)

    failed_items: list[dict] = []
    confirmed_items: list[dict] = []

    for item in booking.items:
        # Tracks a supplier (LiteAPI/Viator) booking failure for this item so
        # the non-flight branch below can route it into the refund path instead
        # of silently marking it confirmed.
        supplier_failed_entry: dict | None = None

        # ─── LiteAPI rooms ────────────────────────────────────────────
        # Existing silent-warning pattern kept as-is — out of scope for this
        # bug fix. Item is marked confirmed regardless so the user sees the
        # local booking (LiteAPI failures surface via `supplier_status`).
        if item.liteapi_prebook_id and not item.liteapi_booking_id:
            holder = {
                "firstName": guest_first_name,
                "lastName": guest_last_name,
                "email": guest_email,
            }
            if guest_phone:
                holder["phoneNumber"] = guest_phone
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
                    "LiteAPI book failed for prebook %s: %s — item will be refunded",
                    item.liteapi_prebook_id,
                    exc.message,
                )
                item.supplier_status = "BOOK_FAILED"
                item.supplier_status_synced_at = datetime.now(timezone.utc)
                supplier_failed_entry = {
                    "item_id": str(item.id),
                    "type": "room",
                    "error_code": getattr(exc, "code", None),
                    "error_type": "liteapi_error",
                    "message": exc.message,
                    "user_message": "We couldn't confirm this room with the hotel. You will be refunded.",
                }

        # ─── Viator tours ─────────────────────────────────────────────
        if item.viator_product_code and not item.viator_booking_ref:
            try:
                tour_date_val = item.check_in or date.today()
                adults_at_book = item.adults_count or item.quantity
                child_ages_at_book = list(item.children_ages or [])
                result = await viator_service.book_tour(
                    viator_product_code=item.viator_product_code,
                    tour_date=tour_date_val,
                    adults=adults_at_book,
                    children_ages=child_ages_at_book,
                    guest_first_name=guest_first_name,
                    guest_last_name=guest_last_name,
                    guest_email=guest_email,
                )
                item.viator_booking_ref = result["viator_booking_ref"]
            except ViatorError as exc:
                logger.warning(
                    "Viator book failed for %s: %s — item will be refunded",
                    item.viator_product_code,
                    exc.message,
                )
                supplier_failed_entry = {
                    "item_id": str(item.id),
                    "type": "tour",
                    "error_code": getattr(exc, "code", None),
                    "error_type": "viator_error",
                    "message": exc.message,
                    "user_message": "We couldn't confirm this tour with the operator. You will be refunded.",
                }

        # ─── Duffel flights ───────────────────────────────────────────
        # Real fix: retry transient failures, persist permanent ones, and
        # propagate the outcome so the caller can refund + notify.
        if item.item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            if flight and flight.status == "pending" and not flight.duffel_order_id:
                success, last_error = await _finalize_duffel_flight(
                    db, booking, item, flight, max_attempts=3,
                )
                if success:
                    item.status = BookingItemStatus.confirmed.value
                    confirmed_items.append({"item_id": str(item.id), "type": "flight"})
                else:
                    # Leave item.status as pending and skip to next item.
                    failed_items.append(_build_failed_item_entry(item, flight, last_error))
                    continue
            else:
                item.status = BookingItemStatus.confirmed.value
                confirmed_items.append({"item_id": str(item.id), "type": "flight"})
        else:
            # Non-flight items (room/tour). If the supplier booking failed,
            # route the item into the failed set so it gets refunded — mirrors
            # the Duffel flow — instead of silently marking it confirmed.
            if supplier_failed_entry is not None:
                failed_items.append(supplier_failed_entry)
            else:
                item.status = BookingItemStatus.confirmed.value
                confirmed_items.append({
                    "item_id": str(item.id),
                    "type": "room" if item.item_type == BookingItemType.room.value else item.item_type,
                })

    # ─── Booking-level outcome ────────────────────────────────────────────
    if not failed_items:
        # Happy path — every item finalized successfully.
        booking.status = BookingStatus.confirmed.value
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
        await lock_service.release_booking_locks(redis, booking.id)
        try:
            await email_service.send_booking_confirmation(booking, guest_email)
        except Exception as exc:
            logger.warning("Confirmation email failed for booking %s: %s", booking.id, exc)
        return booking, {
            "status": "confirmed",
            "confirmed_items": confirmed_items,
            "failed_items": [],
            "refund": None,
        }

    # At least one flight failed. Decide between partial vs total failure.
    has_any_confirmed = len(confirmed_items) > 0

    if has_any_confirmed:
        # Partial — confirm what worked, refund pro-rata share of failed items.
        booking.status = BookingStatus.confirmed.value
        refund_amount = sum(
            _failed_item_refund_share(booking, item_id=entry["item_id"])
            for entry in failed_items
        )
        refund_info = await _attempt_stripe_refund(
            db, booking, amount=refund_amount, partial=True
        )
        net_total = float(booking.total_price) - (refund_info.get("amount_usd") or 0.0)
        points = max(0, int(Decimal(str(net_total))))
        if points > 0:
            await loyalty_service.award_points(
                db,
                user_id=booking.user_id,
                booking_id=booking.id,
                amount=points,
                description=f"Earned from booking {booking.id} (partial)",
            )
            booking.points_earned = points
        await db.flush()
        await db.refresh(booking)
        await lock_service.release_booking_locks(redis, booking.id)
        try:
            await email_service.send_booking_partial_failure(
                booking, guest_email, failed_items, refund_info,
            )
        except Exception as exc:
            logger.warning("Partial-failure email failed for booking %s: %s", booking.id, exc)
        status_str = "partial" if refund_info.get("issued") else "failed_refund_pending"
        return booking, {
            "status": status_str,
            "confirmed_items": confirmed_items,
            "failed_items": failed_items,
            "refund": refund_info,
        }

    # Total failure — cancel the booking and refund in full.
    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        if item.status != BookingItemStatus.confirmed.value:
            item.status = BookingItemStatus.cancelled.value
    refund_info = await _attempt_stripe_refund(db, booking, amount=None, partial=False)
    # The whole booking is cancelled — restore redeemed points and release the
    # voucher so the customer doesn't lose what they spent on a failed booking.
    try:
        await loyalty_service.reverse_booking_points(db, booking.id)
        booking.points_redeemed = 0
        booking.points_earned = 0
    except Exception as exc:
        logger.warning("Loyalty reversal failed for failed booking %s: %s", booking.id, exc)
    try:
        await voucher_service.reverse_voucher_for_booking(db, booking.id)
    except Exception as exc:
        logger.warning("Voucher reversal failed for failed booking %s: %s", booking.id, exc)
    await db.flush()
    await db.refresh(booking)
    await lock_service.release_booking_locks(redis, booking.id)
    primary_failure = failed_items[0] if failed_items else {}
    try:
        await email_service.send_flight_booking_failed(
            booking, guest_email, primary_failure, refund_info,
        )
    except Exception as exc:
        logger.warning("Failure email failed for booking %s: %s", booking.id, exc)
    status_str = "failed" if refund_info.get("issued") else "failed_refund_pending"
    return booking, {
        "status": status_str,
        "confirmed_items": [],
        "failed_items": failed_items,
        "refund": refund_info,
    }


def _failed_item_refund_share(booking: Booking, *, item_id: str) -> float:
    """Pro-rata USD share of booking.total_price owed back for one failed item.

    Uses the persisted ``subtotal`` per item so we refund what was actually
    charged for the failed line, not the whole booking. Single-item bookings
    fall back to total_price.
    """
    items = list(booking.items or [])
    if len(items) <= 1:
        return float(booking.total_price or 0)
    target = next((it for it in items if str(it.id) == str(item_id)), None)
    if target is None:
        return 0.0
    sum_subtotals = sum(float(it.subtotal or 0) for it in items) or 0.0
    if sum_subtotals <= 0:
        return float(booking.total_price or 0)
    share = float(booking.total_price or 0) * (float(target.subtotal or 0) / sum_subtotals)
    return round(share, 2)


async def _attempt_stripe_refund(
    db: AsyncSession,
    booking: Booking,
    *,
    amount: float | None,
    partial: bool,
) -> dict:
    """Issue a Stripe refund through payment_service. Always returns a dict
    describing the outcome — never raises into the caller. ``amount=None``
    means full refund.
    """
    from app.services import payment_service  # avoid circular import at module load

    refund_payload: dict = {
        "issued": False,
        "amount_usd": None,
        "currency": "usd",
        "stripe_refund_id": None,
        "partial": partial,
        "reason": None,
    }
    try:
        payment = await payment_service.refund_for_booking(
            db, booking.id, refund_amount_usd=amount
        )
        if payment is None:
            refund_payload["reason"] = "no_refundable_payment"
            return refund_payload
        # `refund_for_booking` returns the updated Payment row. Stripe-side
        # amount we just issued = either the explicit `amount` or the full
        # booking total when amount was None.
        issued_amount = float(amount) if amount is not None else float(booking.total_price or 0)
        refund_payload.update(
            issued=True,
            amount_usd=round(issued_amount, 2),
            stripe_refund_id=getattr(payment, "stripe_refund_id", None),
            currency=getattr(payment, "currency", None) or "usd",
        )
        return refund_payload
    except Exception:
        logger.exception(
            "Auto-refund FAILED for booking %s — manual intervention required",
            booking.id,
        )
        # Alert ops so a human can issue the refund manually.
        try:
            await email_service.send_admin_alert(
                subject=f"URGENT: Auto-refund failed for booking {booking.id}",
                body=(
                    f"Booking {booking.id} had a supplier failure and the automatic "
                    f"Stripe refund ALSO failed. The customer has been charged but "
                    f"no flight is booked. Refund manually NOW."
                ),
            )
        except Exception:
            pass
        refund_payload["reason"] = "stripe_refund_error"
        return refund_payload


def _outcome_from_persisted_state(booking: Booking) -> dict:
    """Reconstruct the response outcome for an already-finalized booking.

    Used when /confirm-stripe is re-called after a previous run already
    confirmed-or-cancelled the booking. We read ``flight.passenger_details``
    to recover the supplier error that was persisted.
    """
    confirmed_items: list[dict] = []
    failed_items: list[dict] = []
    for item in booking.items or []:
        item_type = item.item_type
        if item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            err = ((flight.passenger_details or {}).get("last_error") if flight else None) or {}
            if flight and flight.duffel_order_id:
                confirmed_items.append({"item_id": str(item.id), "type": "flight"})
            elif err:
                failed_items.append({
                    "item_id": str(item.id),
                    "type": "flight",
                    "error_code": err.get("error_code"),
                    "error_type": err.get("error_type"),
                    "message": err.get("message"),
                    "user_message": _duffel_user_message(
                        err.get("error_code"), err.get("error_type"),
                    ),
                })
        else:
            if item.status == BookingItemStatus.confirmed.value:
                confirmed_items.append({
                    "item_id": str(item.id),
                    "type": "room" if item_type == BookingItemType.room.value else item_type,
                })

    if booking.status == BookingStatus.cancelled.value:
        status_str = "failed"
    elif failed_items:
        status_str = "partial"
    else:
        status_str = "confirmed"
    return {
        "status": status_str,
        "confirmed_items": confirmed_items,
        "failed_items": failed_items,
        "refund": None,  # caller can re-read the Payment row if needed
    }


def _item_refund_share(booking: Booking, item: BookingItem) -> float:
    """USD share of booking.total_price attributable to one item.

    Used when a supplier doesn't report a refund_amount but the item is fully
    refundable (e.g. LiteAPI prebook that was never finalized). For a
    single-item booking this returns total_price; for multi-item it
    pro-rates by line subtotal.
    """
    try:
        items = list(booking.items or [])
        if len(items) <= 1:
            return float(booking.total_price or 0)
        # subtotal is the persisted per-line charge; quantity is already baked in.
        sum_subtotals = sum(float(it.subtotal or 0) for it in items) or 0.0
        if sum_subtotals <= 0:
            return float(booking.total_price or 0)
        return round(float(booking.total_price or 0) * (float(item.subtotal or 0) / sum_subtotals), 2)
    except Exception:
        return float(booking.total_price or 0)


def _local_room_refund(booking: Booking, item: BookingItem) -> tuple[float, float]:
    """Refund + cancellation fee (USD) for cancelling a partner-room item.

    Applies the policy snapshotted on the item at booking time:
      * refundable is False                  → keep everything (no refund)
      * now <= cancellation_deadline (or none)→ full refund, no fee
      * past the deadline                    → keep cancellation_fee_percent of
                                               the item's share, refund the rest

    Returns (refund_amount, cancellation_fee).
    """
    share = _item_refund_share(booking, item)
    if item.refundable is False:
        return 0.0, share

    deadline = item.cancellation_deadline
    now = datetime.now(timezone.utc)
    if deadline is None or now <= deadline:
        return share, 0.0

    fee_pct = float(item.cancellation_fee_percent if item.cancellation_fee_percent is not None else 100)
    fee = round(share * fee_pct / 100.0, 2)
    refund = round(share - fee, 2)
    return max(0.0, refund), fee


async def cancel_pending_booking(
    db: AsyncSession, booking: Booking, redis=None
) -> Booking:
    """Cancel a booking that never got past ``pending`` (no payment succeeded).

    Unlike :func:`cancel_booking`, this touches no supplier: a pending booking
    has not been confirmed with LiteAPI/Duffel/Viator, so there is nothing to
    cancel or refund upstream. It simply flips the booking and its pending items
    to ``cancelled`` and releases any held Redis inventory locks.

    Used for a definitive payment failure (Stripe ``payment_intent.canceled``)
    and by the stale-pending sweep. Idempotent — a no-op if the booking is
    already cancelled.
    """
    if booking.status != BookingStatus.pending.value:
        return booking

    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        if item.status == BookingItemStatus.pending.value:
            item.status = BookingItemStatus.cancelled.value
    await db.flush()

    if redis is not None:
        await lock_service.release_booking_locks(redis, booking.id)
    return booking


async def cancel_booking(
    db: AsyncSession, booking: Booking, redis=None
) -> tuple[Booking, list[dict], dict]:
    """
    Cancel booking and release inventory (tour slots, room_availability rows).

    Returns (booking, supplier_results, stripe_refund_info) where:
      - supplier_results is a list of per-item dicts capturing what each
        upstream supplier reported (LiteAPI's refund_amount, cancellation_fee, etc.)
      - stripe_refund_info is a dict shaped like:
          {"stripe_refund_id": str | None,
           "stripe_refund_amount": float | None,
           "non_refundable": bool}
        It is populated by attempting a Stripe refund for the *sum of supplier-
        reported refundable amounts*. If every supplier reports non-refundable,
        no Stripe refund is issued and `non_refundable=True`.
    """

    supplier_results: list[dict] = []
    stripe_refund_info: dict = {
        "stripe_refund_id": None,
        "stripe_refund_amount": None,
        "non_refundable": False,
    }
    if booking.status == BookingStatus.cancelled.value:
        return booking, supplier_results, stripe_refund_info

    booking.status = BookingStatus.cancelled.value
    for item in booking.items:
        supplier_entry: dict | None = None
        if item.liteapi_booking_id:
            result = await liteapi_service.cancel_booking(item.liteapi_booking_id)
            if not result.get("ok"):
                # Surface LiteAPI's "no" instead of silently cancelling locally.
                # Common case: past the rate's cancellation deadline → the user
                # should see the supplier message ("non-refundable rate cannot
                # be cancelled" or similar) and decide what to do.
                msg = result.get("message") or "LiteAPI refused to cancel this booking"
                raise SupplierCancelError(msg)
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
            # Prebook never finalized — never charged the supplier, so a full refund is safe.
            item.supplier_status = "CANCELLED"
            item.supplier_status_synced_at = datetime.now(timezone.utc)
            supplier_entry = {
                "item_id": item.id,
                "supplier": "liteapi",
                "status": "CANCELLED",
                "refund_amount": _item_refund_share(booking, item),
                "cancellation_fee": 0.0,
                "currency": None,
            }
        if item.viator_booking_ref:
            viator_result = await viator_service.cancel_booking(item.viator_booking_ref)
            supplier_entry = supplier_entry or {
                "item_id": item.id,
                "supplier": "viator",
                "status": (viator_result or {}).get("status") or "CANCELLED",
                "refund_amount": (viator_result or {}).get("refund_amount"),
                "cancellation_fee": None,
                "currency": (viator_result or {}).get("currency"),
            }
        if item.item_type == BookingItemType.flight.value:
            flight = item.flight_booking
            if flight and flight.duffel_order_id:
                duffel_result = await duffel_service.cancel_order(flight.duffel_order_id)
                flight.status = "cancelled"
                supplier_entry = supplier_entry or {
                    "item_id": item.id,
                    "supplier": "duffel",
                    "status": (duffel_result or {}).get("status") or "CANCELLED",
                    "refund_amount": (duffel_result or {}).get("refund_amount"),
                    "cancellation_fee": None,
                    "currency": (duffel_result or {}).get("currency"),
                }
        item.status = BookingItemStatus.cancelled.value
        if supplier_entry is None and item.item_type == BookingItemType.room.value and item.room_id:
            # Partner-owned room: refund per the policy snapshotted at booking time.
            refund_amount, cancellation_fee = _local_room_refund(booking, item)
            if item.refundable is False:
                # Rate never allowed a refund — distinct from "missed the free
                # cancellation window", so the UI can word it differently.
                local_status = "NON_REFUNDABLE"
            elif cancellation_fee > 0:
                local_status = "CANCELLED_WITH_CHARGES"
            else:
                local_status = "CANCELLED"
            supplier_entry = {
                "item_id": item.id,
                "supplier": "local",
                "status": local_status,
                "refund_amount": refund_amount,
                "cancellation_fee": cancellation_fee,
                "currency": None,
            }
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

    # Release the voucher (if any) so the customer can reuse it and the budget
    # pool is restored — mirrors the loyalty reversal above.
    try:
        await voucher_service.reverse_voucher_for_booking(db, booking.id)
    except Exception as exc:
        logger.warning("Voucher reversal failed for booking %s: %s", booking.id, exc)

    # Stripe refund — only refund what the supplier confirmed as refundable.
    # If every supplier reports non-refundable, no refund is issued and the
    # money stays charged. This protects us from refunding the customer when
    # we still owe the supplier.
    total_refundable = 0.0
    any_refundable = False
    for entry in supplier_results:
        amt = entry.get("refund_amount")
        if amt is not None and float(amt) > 0:
            total_refundable += float(amt)
            any_refundable = True

    if any_refundable and total_refundable > 0:
        try:
            from app.services import payment_service
            refunded = await payment_service.refund_for_booking(
                db, booking.id, refund_amount_usd=total_refundable
            )
            if refunded:
                stripe_refund_info["stripe_refund_id"] = refunded.stripe_refund_id
                stripe_refund_info["stripe_refund_amount"] = float(refunded.refunded_amount or 0)
        except Exception as exc:
            # Stripe outage must not block the cancellation. Admin can retry
            # via DELETE /payments/{id}.
            logger.exception("Stripe refund failed for booking %s: %s", booking.id, exc)
    else:
        stripe_refund_info["non_refundable"] = True

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

    return booking, supplier_results, stripe_refund_info


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
