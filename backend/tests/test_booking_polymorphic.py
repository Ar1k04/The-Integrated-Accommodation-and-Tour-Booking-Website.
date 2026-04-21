"""Tests for the polymorphic booking flow (cart with room + tour)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.loyalty_tier import LoyaltyTier
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.schemas.booking import BookingCreate
from app.schemas.booking_item import RoomItemCreate, TourItemCreate
from app.services import booking_service


async def _seed_tiers(db: AsyncSession):
    for name, mn, mx in [
        ("Bronze", 0, 499),
        ("Silver", 500, 1499),
        ("Gold", 1500, 4999),
        ("Platinum", 5000, 999999),
    ]:
        db.add(LoyaltyTier(id=uuid.uuid4(), name=name, min_points=mn, max_points=mx, discount_percent=0))
    await db.flush()


@pytest.fixture
async def test_tour(db_session: AsyncSession):
    tour = Tour(
        id=uuid.uuid4(),
        name="Paris City Tour",
        slug="paris-city-tour",
        city="Paris",
        country="France",
        duration_days=1,
        max_participants=20,
        price_per_person=Decimal("50.00"),
    )
    db_session.add(tour)
    await db_session.flush()
    await db_session.refresh(tour)
    return tour


@pytest.mark.asyncio
async def test_polymorphic_booking_room_plus_tour(
    db_session, test_user, test_room, test_tour
):
    await _seed_tiers(db_session)

    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=2)
    tour_date = date.today() + timedelta(days=12)

    data = BookingCreate(
        items=[
            RoomItemCreate(room_id=test_room.id, check_in=check_in, check_out=check_out, quantity=1),
            TourItemCreate(tour_id=test_tour.id, tour_date=tour_date, quantity=2),
        ],
    )

    booking = await booking_service.create_booking(db_session, test_user.id, data)

    room_subtotal = Decimal(str(test_room.price_per_night)) * 2
    tour_subtotal = Decimal(str(test_tour.price_per_person)) * 2
    expected_total = (room_subtotal + tour_subtotal).quantize(Decimal("0.01"))

    assert booking.total_price == expected_total

    items = (
        await db_session.execute(
            select(BookingItem).where(BookingItem.booking_id == booking.id)
        )
    ).scalars().all()
    assert len(items) == 2

    types = {i.item_type for i in items}
    assert types == {"room", "tour"}

    room_item = next(i for i in items if i.item_type == "room")
    assert room_item.room_id == test_room.id
    assert room_item.check_in == check_in
    assert room_item.check_out == check_out
    assert room_item.subtotal == room_subtotal.quantize(Decimal("0.01"))

    tour_item = next(i for i in items if i.item_type == "tour")
    assert tour_item.tour_schedule_id is not None
    assert tour_item.quantity == 2
    assert tour_item.subtotal == tour_subtotal.quantize(Decimal("0.01"))

    schedule = (
        await db_session.execute(
            select(TourSchedule).where(TourSchedule.id == tour_item.tour_schedule_id)
        )
    ).scalar_one()
    assert schedule.booked_slots == 2
    assert schedule.available_date == tour_date

    assert booking.room_id == test_room.id
    assert booking.check_in == check_in


@pytest.mark.asyncio
async def test_polymorphic_booking_tour_oversubscribed(db_session, test_user, test_tour):
    await _seed_tiers(db_session)
    tour_date = date.today() + timedelta(days=5)

    data = BookingCreate(
        items=[TourItemCreate(tour_id=test_tour.id, tour_date=tour_date, quantity=test_tour.max_participants + 1)],
    )
    with pytest.raises(booking_service.BookingServiceError):
        await booking_service.create_booking(db_session, test_user.id, data)


@pytest.mark.asyncio
async def test_cancel_booking_releases_tour_slots(db_session, test_user, test_tour):
    await _seed_tiers(db_session)
    tour_date = date.today() + timedelta(days=15)

    data = BookingCreate(
        items=[TourItemCreate(tour_id=test_tour.id, tour_date=tour_date, quantity=3)],
    )
    booking = await booking_service.create_booking(db_session, test_user.id, data)

    schedule_before = (
        await db_session.execute(
            select(TourSchedule).where(TourSchedule.tour_id == test_tour.id)
        )
    ).scalar_one()
    assert schedule_before.booked_slots == 3

    await booking_service.cancel_booking(db_session, booking)

    await db_session.refresh(schedule_before)
    assert schedule_before.booked_slots == 0
