"""Tests for booking flow with availability checking and double-booking prevention."""
import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_create_booking_success(client: AsyncClient, test_user, test_room, user_token):
    check_in = (date.today() + timedelta(days=10)).isoformat()
    check_out = (date.today() + timedelta(days=12)).isoformat()

    res = await client.post(
        "/api/v1/bookings",
        json={
            "room_id": str(test_room.id),
            "check_in": check_in,
            "check_out": check_out,
            "guests_count": 2,
        },
        headers=auth_header(user_token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "pending"
    assert float(data["total_price"]) == 400.00  # 200 * 2 nights


@pytest.mark.asyncio
async def test_create_booking_invalid_dates(client: AsyncClient, test_user, test_room, user_token):
    res = await client.post(
        "/api/v1/bookings",
        json={
            "room_id": str(test_room.id),
            "check_in": "2026-04-15",
            "check_out": "2026-04-10",
            "guests_count": 1,
        },
        headers=auth_header(user_token),
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_booking_too_many_guests(client: AsyncClient, test_user, test_room, user_token):
    check_in = (date.today() + timedelta(days=20)).isoformat()
    check_out = (date.today() + timedelta(days=22)).isoformat()

    res = await client.post(
        "/api/v1/bookings",
        json={
            "room_id": str(test_room.id),
            "check_in": check_in,
            "check_out": check_out,
            "guests_count": 10,
        },
        headers=auth_header(user_token),
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_create_booking_unauthenticated(client: AsyncClient, test_room):
    res = await client.post("/api/v1/bookings", json={
        "room_id": str(test_room.id),
        "check_in": "2026-05-01",
        "check_out": "2026-05-03",
        "guests_count": 1,
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_my_bookings(client: AsyncClient, test_user, test_room, user_token):
    check_in = (date.today() + timedelta(days=30)).isoformat()
    check_out = (date.today() + timedelta(days=32)).isoformat()

    await client.post(
        "/api/v1/bookings",
        json={"room_id": str(test_room.id), "check_in": check_in, "check_out": check_out, "guests_count": 1},
        headers=auth_header(user_token),
    )

    res = await client.get("/api/v1/bookings", headers=auth_header(user_token))
    assert res.status_code == 200
    items = res.json().get("items", [])
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_double_booking_prevention(
    client: AsyncClient, db_session: AsyncSession, test_user, test_room, user_token
):
    """Book all available rooms, then attempt one more — should fail."""
    check_in = (date.today() + timedelta(days=50)).isoformat()
    check_out = (date.today() + timedelta(days=52)).isoformat()

    for i in range(test_room.total_quantity):
        from app.models.user import User
        extra_user = User(
            id=uuid.uuid4(),
            email=f"extra{i}@example.com",
            hashed_password="unused",
            full_name=f"Extra {i}",
            role="user",
            is_active=True,
            loyalty_points=0,
        )
        db_session.add(extra_user)
        await db_session.flush()

        from app.core.security import create_access_token
        token = create_access_token(extra_user.id, extra={"role": "user"})
        res = await client.post(
            "/api/v1/bookings",
            json={"room_id": str(test_room.id), "check_in": check_in, "check_out": check_out, "guests_count": 1},
            headers=auth_header(token),
        )
        assert res.status_code == 201

    overflow_res = await client.post(
        "/api/v1/bookings",
        json={"room_id": str(test_room.id), "check_in": check_in, "check_out": check_out, "guests_count": 1},
        headers=auth_header(user_token),
    )
    assert overflow_res.status_code in (400, 409)


@pytest.mark.asyncio
async def test_cancel_booking(client: AsyncClient, test_user, test_room, user_token):
    check_in = (date.today() + timedelta(days=60)).isoformat()
    check_out = (date.today() + timedelta(days=62)).isoformat()

    create_res = await client.post(
        "/api/v1/bookings",
        json={"room_id": str(test_room.id), "check_in": check_in, "check_out": check_out, "guests_count": 1},
        headers=auth_header(user_token),
    )
    booking_id = create_res.json()["id"]

    cancel_res = await client.delete(f"/api/v1/bookings/{booking_id}", headers=auth_header(user_token))
    assert cancel_res.status_code in (200, 204)
