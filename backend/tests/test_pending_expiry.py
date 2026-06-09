"""Unit tests for the stale-pending-booking sweep and the pending-cancel helper.

A booking is created ``pending`` and only flips to ``confirmed`` once a payment
succeeds. When the user never pays (abandoned checkout, a declined payment they
don't retry, or a provider callback that never lands), the booking must not sit
in My Bookings as a stale ``pending`` row forever — the sweep cancels it after a
grace window. Test IDs: UT-BE-PENDING-EXPIRY-01..NN.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.payment import Payment
from app.services import completion_service
from app.services.booking_service import cancel_pending_booking

NOW = datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc)
GRACE = settings.PENDING_BOOKING_EXPIRY_MINUTES


def _aged(minutes: int) -> datetime:
    return NOW - timedelta(minutes=minutes)


async def _pending_booking(db, user, *, created_at, with_item=True, room=None):
    b = Booking(user_id=user.id, total_price=200, status="pending", created_at=created_at)
    db.add(b)
    await db.flush()
    if with_item:
        db.add(BookingItem(
            booking_id=b.id, item_type="room", room_id=room.id if room else None,
            status="pending", unit_price=200, subtotal=200,
        ))
        await db.flush()
    return b


@pytest.mark.asyncio
async def test_old_unpaid_pending_is_cancelled(db_session, test_user, test_room):
    booking = await _pending_booking(
        db_session, test_user, created_at=_aged(GRACE + 10), room=test_room
    )

    n = await completion_service.expire_stale_pending_bookings(db_session, now=NOW)

    assert n == 1
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    item = (await db_session.execute(
        select(BookingItem).where(BookingItem.booking_id == booking.id)
    )).scalar_one()
    assert item.status == "cancelled"


@pytest.mark.asyncio
async def test_recent_pending_within_grace_survives(db_session, test_user, test_room):
    booking = await _pending_booking(
        db_session, test_user, created_at=_aged(GRACE - 5), room=test_room
    )

    n = await completion_service.expire_stale_pending_bookings(db_session, now=NOW)

    assert n == 0
    await db_session.refresh(booking)
    assert booking.status == "pending"


@pytest.mark.asyncio
async def test_paid_pending_is_left_alone(db_session, test_user, test_room):
    """Defensive: a booking with a succeeded payment is never swept, even if it
    is somehow still pending and past the grace window."""
    booking = await _pending_booking(
        db_session, test_user, created_at=_aged(GRACE + 60), room=test_room
    )
    db_session.add(Payment(booking_id=booking.id, amount=200, status="succeeded"))
    await db_session.flush()

    n = await completion_service.expire_stale_pending_bookings(db_session, now=NOW)

    assert n == 0
    await db_session.refresh(booking)
    assert booking.status == "pending"


@pytest.mark.asyncio
async def test_failed_payment_does_not_protect_booking(db_session, test_user, test_room):
    """Only a *succeeded* payment protects a booking — a failed attempt must
    still let the sweep cancel the abandoned booking."""
    booking = await _pending_booking(
        db_session, test_user, created_at=_aged(GRACE + 10), room=test_room
    )
    db_session.add(Payment(booking_id=booking.id, amount=200, status="failed"))
    await db_session.flush()

    n = await completion_service.expire_stale_pending_bookings(db_session, now=NOW)

    assert n == 1
    await db_session.refresh(booking)
    assert booking.status == "cancelled"


@pytest.mark.asyncio
async def test_confirmed_booking_never_swept(db_session, test_user, test_room):
    booking = Booking(
        user_id=test_user.id, total_price=200, status="confirmed",
        created_at=_aged(GRACE + 999),
    )
    db_session.add(booking)
    await db_session.flush()

    n = await completion_service.expire_stale_pending_bookings(db_session, now=NOW)

    assert n == 0
    await db_session.refresh(booking)
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_cancel_pending_helper_is_idempotent(db_session, test_user, test_room):
    booking = await _pending_booking(
        db_session, test_user, created_at=_aged(5), room=test_room
    )
    # Reload so the selectin `items` relationship is populated like in production.
    booking = (await db_session.execute(
        select(Booking).where(Booking.id == booking.id)
    )).scalar_one()

    await cancel_pending_booking(db_session, booking)
    assert booking.status == "cancelled"

    # Second call is a no-op (already cancelled) and must not raise.
    await cancel_pending_booking(db_session, booking)
    assert booking.status == "cancelled"
