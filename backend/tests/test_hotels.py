"""Tests for hotel CRUD and search."""
import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_hotels(client: AsyncClient, test_hotel):
    res = await client.get("/api/v1/hotels")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_hotel(client: AsyncClient, test_hotel):
    res = await client.get(f"/api/v1/hotels/{test_hotel.id}")
    assert res.status_code == 200
    assert res.json()["name"] == "Test Hotel"


@pytest.mark.asyncio
async def test_get_hotel_not_found(client: AsyncClient):
    import uuid
    res = await client.get(f"/api/v1/hotels/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_hotel_admin(client: AsyncClient, admin_user, admin_token):
    res = await client.post(
        "/api/v1/hotels",
        json={
            "name": "New Hotel",
            "city": "Tokyo",
            "country": "Japan",
            "base_price": 250.00,
            "star_rating": 5,
        },
        headers=auth_header(admin_token),
    )
    assert res.status_code == 201
    assert res.json()["name"] == "New Hotel"


@pytest.mark.asyncio
async def test_create_hotel_non_admin(client: AsyncClient, test_user, user_token):
    res = await client.post(
        "/api/v1/hotels",
        json={
            "name": "Unauthorized Hotel",
            "city": "City",
            "country": "Country",
            "base_price": 100,
        },
        headers=auth_header(user_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_search_hotels_by_city(client: AsyncClient, test_hotel):
    res = await client.get("/api/v1/hotels", params={"city": "Paris"})
    assert res.status_code == 200
    items = res.json().get("items", [])
    assert all(h["city"] == "Paris" for h in items)


@pytest.mark.asyncio
async def test_delete_hotel_admin(client: AsyncClient, admin_user, admin_token, test_hotel):
    res = await client.delete(f"/api/v1/hotels/{test_hotel.id}", headers=auth_header(admin_token))
    assert res.status_code in (200, 204)
