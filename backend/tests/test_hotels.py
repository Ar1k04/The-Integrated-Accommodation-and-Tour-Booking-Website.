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


# ── Dated search: partner (local DB) rooms ────────────────────────────────────

@pytest.mark.asyncio
async def test_dated_search_partner_room_real_price(client: AsyncClient, test_hotel, test_room):
    """A partner hotel with an available room shows its real DB min price for a
    dated search (no phantom price). LiteAPI is mocked empty to isolate the
    local path through the combined search."""
    from unittest.mock import AsyncMock, patch
    from app.services import liteapi_service
    from app.main import app
    app.state.redis = None

    with patch.object(liteapi_service, "search_hotels", new=AsyncMock(return_value=([], 0))):
        res = await client.get(
            "/api/v1/hotels?city=Paris&check_in=2026-06-04&check_out=2026-06-06&guests=2"
        )

    assert res.status_code == 200
    by_name = {h["name"]: h for h in res.json()["items"]}
    assert "Test Hotel" in by_name
    assert by_name["Test Hotel"]["source"] == "local"
    assert float(by_name["Test Hotel"]["min_room_price"]) == 200.0


@pytest.mark.asyncio
async def test_dated_search_partner_soldout_priceless_and_last(
    client: AsyncClient, db_session, test_hotel, test_room, test_user
):
    """A partner hotel whose only room is booked over the searched nights stays
    visible but price-less, and sorts BELOW an available LiteAPI hotel — same
    treatment sold-out LiteAPI hotels get."""
    import uuid
    from datetime import date
    from unittest.mock import AsyncMock, patch
    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from app.services import liteapi_service
    from app.main import app

    # Reserve the room across 2026-06-04 → 06 so the hotel has no availability.
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=200, status="confirmed")
    db_session.add(booking)
    await db_session.flush()
    db_session.add(BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type="room", room_id=test_room.id,
        check_in=date(2026, 6, 4), check_out=date(2026, 6, 6),
        unit_price=200, subtotal=200, status="confirmed",
    ))
    await db_session.flush()

    lite_raw = [{
        "hotelId": "L1", "name": "Lite Avail", "cityName": "Paris", "countryCode": "FR",
        "starRating": 4, "minRate": 150.0, "amenities": [], "hotelImages": [],
    }]
    app.state.redis = None
    with patch.object(
        liteapi_service, "search_hotels",
        new=AsyncMock(return_value=([liteapi_service._normalize_hotel(h) for h in lite_raw], 1)),
    ), patch(
        "app.api.v1.routes.hotels.get_min_rates_batch",
        new=AsyncMock(return_value={"L1": 175.0}),
    ):
        res = await client.get(
            "/api/v1/hotels?city=Paris&check_in=2026-06-04&check_out=2026-06-06&guests=2"
        )

    assert res.status_code == 200
    items = res.json()["items"]
    by_name = {h["name"]: h for h in items}
    # Sold-out partner hotel stays visible, with no price.
    assert "Test Hotel" in by_name
    assert by_name["Test Hotel"]["min_room_price"] is None
    # And it sorts below the available LiteAPI hotel.
    names = [h["name"] for h in items]
    assert names.index("Lite Avail") < names.index("Test Hotel")
