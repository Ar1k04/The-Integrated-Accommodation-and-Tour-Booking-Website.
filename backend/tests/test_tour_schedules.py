"""Tests for partner-managed tour schedule CRUD (UC29)."""
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio

from tests.conftest import auth_header


@pytest_asyncio.fixture
async def partner_tour(db_session, partner_user):
    from app.models.tour import Tour
    tour = Tour(
        id=uuid.uuid4(),
        owner_id=partner_user.id,
        name="Partner City Walk",
        slug=f"partner-city-walk-{uuid.uuid4().hex[:6]}",
        city="Hanoi",
        country="Vietnam",
        duration_days=1,
        max_participants=20,
        price_per_person=30.00,
    )
    db_session.add(tour)
    await db_session.flush()
    await db_session.refresh(tour)
    return tour


@pytest.mark.asyncio
async def test_schedule_crud_lifecycle(client, partner_tour, partner_token):
    d = (date.today() + timedelta(days=10)).isoformat()
    h = auth_header(partner_token)

    # Create
    res = await client.post(
        f"/api/v1/tours/{partner_tour.id}/schedules",
        json={"available_date": d, "total_slots": 12}, headers=h,
    )
    assert res.status_code == 201, res.text
    assert res.json()["total_slots"] == 12

    # List
    res = await client.get(f"/api/v1/tours/{partner_tour.id}/schedules", headers=h)
    assert res.status_code == 200
    assert any(s["available_date"] == d for s in res.json())

    # Update capacity
    res = await client.patch(
        f"/api/v1/tours/{partner_tour.id}/schedules/{d}",
        json={"total_slots": 5}, headers=h,
    )
    assert res.status_code == 200
    assert res.json()["total_slots"] == 5

    # Delete (no bookings yet)
    res = await client.delete(f"/api/v1/tours/{partner_tour.id}/schedules/{d}", headers=h)
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_schedule_capacity_below_booked_rejected(client, db_session, partner_tour, partner_token):
    from app.models.tour_schedule import TourSchedule
    d = date.today() + timedelta(days=14)
    sched = TourSchedule(
        id=uuid.uuid4(), tour_id=partner_tour.id, available_date=d,
        total_slots=10, booked_slots=4,
    )
    db_session.add(sched)
    await db_session.flush()

    res = await client.patch(
        f"/api/v1/tours/{partner_tour.id}/schedules/{d.isoformat()}",
        json={"total_slots": 2}, headers=auth_header(partner_token),
    )
    assert res.status_code == 400

    # And a booked date cannot be deleted.
    res = await client.delete(
        f"/api/v1/tours/{partner_tour.id}/schedules/{d.isoformat()}",
        headers=auth_header(partner_token),
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_schedule_requires_owner(client, partner_tour, user_token):
    d = (date.today() + timedelta(days=10)).isoformat()
    res = await client.post(
        f"/api/v1/tours/{partner_tour.id}/schedules",
        json={"available_date": d, "total_slots": 12},
        headers=auth_header(user_token),
    )
    # Regular customers are not staff — blocked before the owner check.
    assert res.status_code in (401, 403)
