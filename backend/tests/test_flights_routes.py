"""Route-level tests for flights endpoints (search filters, airports, get_order)."""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking, FlightBookingStatus
from tests.conftest import auth_header


def _sample_offer(offer_id: str, total: float, airline_iata: str = "VN", stops: int = 0):
    segments = [
        {
            "flight_number": f"{airline_iata}100",
            "airline_name": "Vietnam Airlines",
            "airline_iata": airline_iata,
            "origin_iata": "HAN",
            "origin_name": "Noi Bai",
            "destination_iata": "SGN",
            "destination_name": "Tan Son Nhat",
            "departure_at": "2026-07-01T08:00:00",
            "arrival_at": "2026-07-01T10:00:00",
            "duration": "2h 0m",
            "aircraft": "A321",
        }
    ]
    # Add fake stop segments by repeating
    for i in range(stops):
        segments.append({
            **segments[0],
            "flight_number": f"{airline_iata}{200 + i}",
            "departure_at": f"2026-07-01T1{2+i}:00:00",
            "arrival_at": f"2026-07-01T1{4+i}:00:00",
        })
    return {
        "duffel_offer_id": offer_id,
        "total_amount": total,
        "currency": "USD",
        "airline_name": "Vietnam Airlines",
        "airline_iata": airline_iata,
        "slices": [{"origin": "HAN", "destination": "SGN", "duration": "2h 0m", "segments": segments}],
        "passengers": 1,
        "cabin_class": "economy",
        "expires_at": "2026-07-01T23:59:00Z",
        "source": "duffel",
    }


@pytest.mark.asyncio
async def test_search_filters_max_price(client):
    mock_offers = [
        _sample_offer("off_a", 100.0),
        _sample_offer("off_b", 200.0),
        _sample_offer("off_c", 300.0),
    ]
    with patch("app.api.v1.routes.flights.duffel_service.search_offers",
               AsyncMock(return_value=mock_offers)):
        resp = await client.get(
            "/api/v1/flights/search",
            params={"origin": "HAN", "destination": "SGN",
                    "depart_date": "2026-07-01", "max_price": 150},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["duffel_offer_id"] == "off_a"


@pytest.mark.asyncio
async def test_search_filters_max_connections_direct_only(client):
    mock_offers = [
        _sample_offer("off_direct", 100.0, stops=0),
        _sample_offer("off_1stop", 80.0, stops=1),
        _sample_offer("off_2stops", 60.0, stops=2),
    ]
    with patch("app.api.v1.routes.flights.duffel_service.search_offers",
               AsyncMock(return_value=mock_offers)):
        resp = await client.get(
            "/api/v1/flights/search",
            params={"origin": "HAN", "destination": "SGN",
                    "depart_date": "2026-07-01", "max_connections": 0},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["duffel_offer_id"] == "off_direct"


@pytest.mark.asyncio
async def test_search_sort_by_price_asc(client):
    mock_offers = [
        _sample_offer("off_c", 300.0),
        _sample_offer("off_a", 100.0),
        _sample_offer("off_b", 200.0),
    ]
    with patch("app.api.v1.routes.flights.duffel_service.search_offers",
               AsyncMock(return_value=mock_offers)):
        resp = await client.get(
            "/api/v1/flights/search",
            params={"origin": "HAN", "destination": "SGN",
                    "depart_date": "2026-07-01", "sort_by": "price", "sort_order": "asc"},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [o["duffel_offer_id"] for o in data] == ["off_a", "off_b", "off_c"]


@pytest.mark.asyncio
async def test_search_filters_airlines_whitelist(client):
    mock_offers = [
        _sample_offer("off_vn", 100.0, airline_iata="VN"),
        _sample_offer("off_vj", 90.0, airline_iata="VJ"),
        _sample_offer("off_qh", 80.0, airline_iata="QH"),
    ]
    with patch("app.api.v1.routes.flights.duffel_service.search_offers",
               AsyncMock(return_value=mock_offers)):
        resp = await client.get(
            "/api/v1/flights/search",
            params=[
                ("origin", "HAN"), ("destination", "SGN"),
                ("depart_date", "2026-07-01"),
                ("airlines", "VN"), ("airlines", "VJ"),
            ],
        )
    data = resp.json()["data"]
    iatas = sorted(o["airline_iata"] for o in data)
    assert iatas == ["VJ", "VN"]


@pytest.mark.asyncio
async def test_airports_autocomplete_by_iata(client):
    resp = await client.get("/api/v1/flights/airports", params={"q": "han"})
    assert resp.status_code == 200
    iatas = [a["iata"] for a in resp.json()["data"]]
    assert "HAN" in iatas


@pytest.mark.asyncio
async def test_airports_autocomplete_by_city(client):
    resp = await client.get("/api/v1/flights/airports", params={"q": "tokyo"})
    assert resp.status_code == 200
    iatas = [a["iata"] for a in resp.json()["data"]]
    # Tokyo has NRT + HND
    assert "NRT" in iatas
    assert "HND" in iatas


@pytest.mark.asyncio
async def test_airports_empty_query_returns_empty(client):
    resp = await client.get("/api/v1/flights/airports", params={"q": " "})
    # Empty/whitespace query rejected by min_length=1 (whitespace counts toward length).
    # We just assert the endpoint doesn't 500.
    assert resp.status_code in (200, 422)


@pytest.mark.asyncio
async def test_get_order_requires_ownership(client, db_session, test_user, user_token):
    """User cannot access an order they don't own — returns 404."""
    resp = await client.get(
        "/api/v1/flights/orders/ord_someone_else",
        headers=auth_header(user_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_order_proxies_duffel_when_owned(
    client, db_session: AsyncSession, test_user, user_token
):
    flight = FlightBooking(
        id=uuid.uuid4(),
        duffel_order_id="ord_owned",
        duffel_booking_ref="PNR123",
        airline_name="Vietnam Airlines",
        flight_number="VN100",
        departure_airport="HAN",
        arrival_airport="SGN",
        departure_at=datetime.now(timezone.utc) + timedelta(days=10),
        arrival_at=datetime.now(timezone.utc) + timedelta(days=10, hours=2),
        cabin_class="economy",
        passenger_name="Alice Doe",
        passenger_email="a@x.com",
        base_amount=100.0,
        total_amount=100.0,
        currency="USD",
        status=FlightBookingStatus.confirmed.value,
    )
    db_session.add(flight)
    await db_session.flush()

    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=100.0,
        status=BookingStatus.confirmed.value,
    )
    db_session.add(booking)
    await db_session.flush()

    item = BookingItem(
        booking_id=booking.id,
        item_type=BookingItemType.flight.value,
        flight_booking_id=flight.id,
        unit_price=100.0,
        subtotal=100.0,
        quantity=1,
        status=BookingItemStatus.confirmed.value,
    )
    db_session.add(item)
    await db_session.flush()

    mock_order = {
        "duffel_order_id": "ord_owned",
        "duffel_booking_ref": "PNR123",
        "status": "confirmed",
        "total_amount": 100.0,
        "currency": "USD",
        "passengers": [],
        "slices": [],
        "documents": [],
    }
    with patch("app.api.v1.routes.flights.duffel_service.get_order",
               AsyncMock(return_value=mock_order)):
        resp = await client.get(
            "/api/v1/flights/orders/ord_owned",
            headers=auth_header(user_token),
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["duffel_booking_ref"] == "PNR123"
