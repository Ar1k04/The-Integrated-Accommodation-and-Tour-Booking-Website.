"""Mark confirmed bookings/items as ``completed`` once their service date has
passed.

This is what unlocks the review-write gate: a guest may only review a hotel/tour
after the corresponding ``BookingItem`` (and, for internal hotels/tours, the
parent ``Booking``) reaches ``completed``. Nothing else in the system performs
this transition, so without it real customers can never review.

The "service end date" depends on item type:
  - room   → ``BookingItem.check_out`` (covers both internal and LiteAPI rooms)
  - tour   → ``TourSchedule.available_date`` (internal) or ``check_in`` (Viator,
             which stores the tour date in ``check_in``; see booking_service.py)
  - flight → ``FlightBooking.arrival_at`` (flights aren't reviewable but still
             gate the booking-level rollup)

An item is "due" when ``today >= service_end_date``. The function is idempotent
(only touches ``confirmed`` rows) and does NOT commit — the caller owns the
transaction (request session for lazy-on-read, or the scheduler's own session).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, and_, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus
from app.models.flight_booking import FlightBooking
from app.models.payment import Payment, PaymentStatus
from app.models.tour_schedule import TourSchedule

logger = logging.getLogger(__name__)

_CONFIRMED = BookingItemStatus.confirmed.value
_COMPLETED = BookingItemStatus.completed.value
_CANCELLED = BookingItemStatus.cancelled.value


async def complete_due_items(
    db: AsyncSession,
    *,
    today: date | None = None,
    user_id=None,
    booking_id=None,
) -> int:
    """Flip ``confirmed`` items whose service date has passed to ``completed``,
    then roll affected bookings up to ``completed`` when all their non-cancelled
    items are done.

    Optional ``user_id`` / ``booking_id`` scope the sweep (used by lazy-on-read
    so a request only touches its own data). Returns the number of items flipped.
    """
    today = today or date.today()

    room_due = and_(
        BookingItem.item_type == "room",
        BookingItem.check_out.is_not(None),
        BookingItem.check_out <= today,
    )
    internal_tour_due = and_(
        BookingItem.item_type == "tour",
        BookingItem.tour_schedule_id.is_not(None),
        TourSchedule.available_date <= today,
    )
    viator_tour_due = and_(
        BookingItem.item_type == "tour",
        BookingItem.tour_schedule_id.is_(None),
        BookingItem.check_in.is_not(None),
        BookingItem.check_in <= today,
    )
    flight_due = and_(
        BookingItem.item_type == "flight",
        FlightBooking.arrival_at.is_not(None),
        cast(FlightBooking.arrival_at, Date) <= today,
    )

    stmt = (
        select(BookingItem)
        .outerjoin(TourSchedule, BookingItem.tour_schedule_id == TourSchedule.id)
        .outerjoin(FlightBooking, BookingItem.flight_booking_id == FlightBooking.id)
        .where(
            BookingItem.status == _CONFIRMED,
            or_(room_due, internal_tour_due, viator_tour_due, flight_due),
        )
    )
    if user_id is not None:
        stmt = stmt.join(Booking, BookingItem.booking_id == Booking.id).where(
            Booking.user_id == user_id
        )
    if booking_id is not None:
        stmt = stmt.where(BookingItem.booking_id == booking_id)

    due_items = (await db.execute(stmt)).scalars().all()
    if not due_items:
        return 0

    affected_booking_ids = set()
    for item in due_items:
        item.status = _COMPLETED
        affected_booking_ids.add(item.booking_id)

    await db.flush()

    # Roll a booking up to completed only when every non-cancelled item is done.
    bookings = (
        await db.execute(
            select(Booking).where(
                Booking.id.in_(affected_booking_ids),
                Booking.status == BookingStatus.confirmed.value,
            )
        )
    ).scalars().all()
    for booking in bookings:
        active_items = [it for it in booking.items if it.status != _CANCELLED]
        if active_items and all(it.status == _COMPLETED for it in active_items):
            booking.status = BookingStatus.completed.value

    await db.flush()

    logger.info(
        "metric=completion.items_completed_total count=%d bookings_affected=%d",
        len(due_items),
        len(affected_booking_ids),
    )
    return len(due_items)


async def expire_stale_pending_bookings(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    redis=None,
) -> int:
    """Cancel ``pending`` bookings that were never paid for.

    A booking is created ``pending`` and only flips to ``confirmed`` once a
    Stripe payment succeeds. When the user abandons checkout or has a payment
    decline they don't retry, the booking would sit in My Bookings as a stale
    ``pending`` row forever. This sweep cancels any booking that is:

      - still ``pending``,
      - older than ``PENDING_BOOKING_EXPIRY_MINUTES`` (a grace window so a user
        who is mid-payment / retrying isn't cut off), and
      - has no ``succeeded`` payment (defensive — a confirmed booking already
        left ``pending``, but this guards against any out-of-band state).

    Pending items are flipped to ``cancelled`` and the booking's Redis inventory
    locks are released. These bookings never reached a supplier (that only
    happens on confirm), so there is nothing to refund or cancel upstream.

    Idempotent and does NOT commit — the caller owns the transaction. Returns the
    number of bookings expired.
    """
    from app.services.booking_service import cancel_pending_booking

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=settings.PENDING_BOOKING_EXPIRY_MINUTES)

    paid_booking_ids = select(Payment.booking_id).where(
        Payment.status == PaymentStatus.succeeded.value,
        Payment.booking_id.is_not(None),
    )
    stmt = select(Booking).where(
        Booking.status == BookingStatus.pending.value,
        Booking.created_at < cutoff,
        Booking.id.notin_(paid_booking_ids),
    )
    bookings = (await db.execute(stmt)).scalars().all()
    if not bookings:
        return 0

    for booking in bookings:
        await cancel_pending_booking(db, booking, redis=redis)

    logger.info(
        "metric=completion.pending_expired_total count=%d cutoff=%s",
        len(bookings),
        cutoff.isoformat(),
    )
    return len(bookings)
