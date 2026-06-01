"""Route tests cho rooms (cần DB test).

Bao phủ: get/list + 404, phân quyền tạo/sửa/xoá (StaffUser + ownership), kiểm
tra tồn phòng. Test IDs: UT-BE-ROOM-01..NN.
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_get_room(client: AsyncClient, test_room):
    res = await client.get(f"/api/v1/rooms/{test_room.id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Deluxe Double"


@pytest.mark.asyncio
async def test_get_room_404(client: AsyncClient):
    res = await client.get(f"/api/v1/rooms/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_hotel_rooms(client: AsyncClient, test_hotel, test_room):
    res = await client.get(f"/api/v1/hotels/{test_hotel.id}/rooms")
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_list_rooms_missing_hotel_404(client: AsyncClient):
    res = await client.get(f"/api/v1/hotels/{uuid.uuid4()}/rooms")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_room_requires_staff(client: AsyncClient, test_hotel, user_token):
    res = await client.post(
        f"/api/v1/hotels/{test_hotel.id}/rooms",
        json={"name": "R", "room_type": "double", "price_per_night": 100},
        headers=auth_header(user_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_room_as_admin(client: AsyncClient, test_hotel, admin_token):
    res = await client.post(
        f"/api/v1/hotels/{test_hotel.id}/rooms",
        json={"name": "Suite", "room_type": "suite", "price_per_night": 300, "max_guests": 4},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Suite"


@pytest.mark.asyncio
async def test_partner_cannot_create_room_in_other_owners_hotel(
    client: AsyncClient, db_session, partner_user, partner_token, admin_user
):
    from app.models.hotel import Hotel

    # Hotel thuộc sở hữu người khác (admin_user) → partner bị từ chối.
    other = Hotel(
        id=uuid.uuid4(),
        name="Other Hotel",
        slug="other-hotel",
        city="Rome",
        country="Italy",
        base_price=120.0,
        star_rating=3,
        owner_id=admin_user.id,
    )
    db_session.add(other)
    await db_session.flush()

    res = await client.post(
        f"/api/v1/hotels/{other.id}/rooms",
        json={"name": "R", "room_type": "double", "price_per_night": 100},
        headers=auth_header(partner_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_room_price_as_admin(client: AsyncClient, test_room, admin_token):
    res = await client.patch(
        f"/api/v1/rooms/{test_room.id}",
        json={"price_per_night": 250},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 200
    assert res.json()["price_per_night"] == 250


@pytest.mark.asyncio
async def test_update_room_requires_staff(client: AsyncClient, test_room, user_token):
    res = await client.patch(
        f"/api/v1/rooms/{test_room.id}",
        json={"price_per_night": 250},
        headers=auth_header(user_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_room_availability_when_free(client: AsyncClient, test_room):
    res = await client.get(
        f"/api/v1/rooms/{test_room.id}/availability",
        params={"check_in": "2026-06-01", "check_out": "2026-06-03"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is True
    assert body["rooms_left"] >= 1


@pytest.mark.asyncio
async def test_delete_room_as_admin(client: AsyncClient, test_room, admin_token):
    res = await client.delete(f"/api/v1/rooms/{test_room.id}", headers=auth_header(admin_token))
    assert res.status_code == 204
