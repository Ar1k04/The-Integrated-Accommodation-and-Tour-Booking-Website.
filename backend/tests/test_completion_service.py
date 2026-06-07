"""Unit tests for the booking-completion sweep.

Covers the service-date → ``completed`` transition that unlocks reviews:
rooms (internal + LiteAPI), internal tours, the booking-level rollup (only when
every non-cancelled item is done), and that future/cancelled items are skipped.
Test IDs: UT-BE-COMPLETION-01..NN.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.flight_booking import FlightBooking
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.services import completion_service

TODAY = date(2026, 6, 7)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


async def _booking(db, user, status="confirmed"):
    b = Booking(user_id=user.id, total_price=200, status=status)
    db.add(b)
    await db.flush()
    return b


@pytest.mark.asyncio
async def test_room_past_checkout_completes_item_and_booking(
    db_session, test_user, test_room
):
    booking = await _booking(db_session, test_user)
    item = BookingItem(
        booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=YESTERDAY - timedelta(days=2), check_out=YESTERDAY,
        status="confirmed", unit_price=200, subtotal=200,
    )
    db_session.add(item)
    await db_session.flush()

    n = await completion_service.complete_due_items(db_session, today=TODAY)

    assert n == 1
    assert item.status == "completed"
    assert booking.status == "completed"


@pytest.mark.asyncio
async def test_future_checkout_stays_confirmed(db_session, test_user, test_room):
    booking = await _booking(db_session, test_user)
    item = BookingItem(
        booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=TODAY, check_out=TOMORROW,
        status="confirmed", unit_price=200, subtotal=200,
    )
    db_session.add(item)
    await db_session.flush()

    n = await completion_service.complete_due_items(db_session, today=TODAY)

    assert n == 0
    assert item.status == "confirmed"
    assert booking.status == "confirmed"


@pytest.mark.asyncio
async def test_internal_tour_past_date_completes(db_session, test_user):
    tour = Tour(
        name="City Walk", slug=f"city-walk-{uuid.uuid4().hex[:8]}",
        city="Paris", country="France", price_per_person=50,
    )
    db_session.add(tour)
    await db_session.flush()
    schedule = TourSchedule(
        tour_id=tour.id, available_date=YESTERDAY, total_slots=10, booked_slots=1
    )
    db_session.add(schedule)
    await db_session.flush()

    booking = await _booking(db_session, test_user)
    item = BookingItem(
        booking_id=booking.id, item_type="tour", tour_schedule_id=schedule.id,
        status="confirmed", unit_price=50, subtotal=50,
    )
    db_session.add(item)
    await db_session.flush()

    n = await completion_service.complete_due_items(db_session, today=TODAY)

    assert n == 1
    assert item.status == "completed"
    assert booking.status == "completed"


@pytest.mark.asyncio
async def test_mixed_booking_room_done_flight_pending_stays_confirmed(
    db_session, test_user, test_room
):
    """Room stay is over but the flight hasn't departed → the room item
    completes but the booking must NOT roll up to completed yet."""
    booking = await _booking(db_session, test_user)
    room_item = BookingItem(
        booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=YESTERDAY - timedelta(days=1), check_out=YESTERDAY,
        status="confirmed", unit_price=200, subtotal=200,
    )
    flight = FlightBooking(
        airline_name="Duffel Airways", flight_number="ZZ100",
        departure_airport="HAN", arrival_airport="SGN",
        departure_at=datetime(2026, 7, 1, 8, tzinfo=timezone.utc),
        arrival_at=datetime(2026, 7, 1, 10, tzinfo=timezone.utc),  # future
        passenger_name="Test User", passenger_email="t@example.com",
        base_amount=100, total_amount=100, status="confirmed",
    )
    db_session.add_all([room_item, flight])
    await db_session.flush()
    flight_item = BookingItem(
        booking_id=booking.id, item_type="flight", flight_booking_id=flight.id,
        status="confirmed", unit_price=100, subtotal=100,
    )
    db_session.add(flight_item)
    await db_session.flush()

    n = await completion_service.complete_due_items(db_session, today=TODAY)

    assert n == 1
    assert room_item.status == "completed"
    assert flight_item.status == "confirmed"
    assert booking.status == "confirmed"  # not all items done → no rollup


@pytest.mark.asyncio
async def test_cancelled_item_ignored_in_rollup(db_session, test_user, test_room):
    """A cancelled sibling item must not block the booking-level rollup."""
    booking = await _booking(db_session, test_user)
    done_item = BookingItem(
        booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=YESTERDAY - timedelta(days=1), check_out=YESTERDAY,
        status="confirmed", unit_price=200, subtotal=200,
    )
    cancelled_item = BookingItem(
        booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=TODAY, check_out=TOMORROW,
        status="cancelled", unit_price=200, subtotal=200,
    )
    db_session.add_all([done_item, cancelled_item])
    await db_session.flush()

    n = await completion_service.complete_due_items(db_session, today=TODAY)

    assert n == 1
    assert done_item.status == "completed"
    assert booking.status == "completed"


@pytest.mark.asyncio
async def test_user_scope_only_touches_that_user(
    db_session, test_user, admin_user, test_room
):
    mine = await _booking(db_session, test_user)
    theirs = await _booking(db_session, admin_user)
    for b in (mine, theirs):
        db_session.add(BookingItem(
            booking_id=b.id, item_type="room", room_id=test_room.id,
            check_in=YESTERDAY - timedelta(days=1), check_out=YESTERDAY,
            status="confirmed", unit_price=200, subtotal=200,
        ))
    await db_session.flush()

    n = await completion_service.complete_due_items(
        db_session, today=TODAY, user_id=test_user.id
    )

    assert n == 1
    await db_session.refresh(mine)
    await db_session.refresh(theirs)
    assert mine.status == "completed"
    assert theirs.status == "confirmed"
