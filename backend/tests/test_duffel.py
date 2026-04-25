"""Tests for Duffel flight service layer with mocked HTTP responses."""
import pytest
import httpx
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from app.services import duffel_service
from app.services.duffel_service import DuffelError


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(status_code, json=json_data)


_OFFER_RAW = {
    "id": "off_0000test",
    "total_amount": "123.45",
    "total_currency": "USD",
    "expires_at": "2026-07-01T23:59:00Z",
    "owner": {"name": "Duffel Airways", "iata_code": "ZZ"},
    "cabin_class": "economy",
    "passengers": [{"id": "pas_001", "type": "adult"}],
    "slices": [
        {
            "origin": {"iata_code": "HAN"},
            "destination": {"iata_code": "SGN"},
            "duration": "PT2H",
            "segments": [
                {
                    "departing_at": "2026-07-01T08:00:00",
                    "arriving_at": "2026-07-01T10:00:00",
                    "origin": {"iata_code": "HAN", "name": "Noi Bai"},
                    "destination": {"iata_code": "SGN", "name": "Tan Son Nhat"},
                    "marketing_carrier": {"name": "Duffel Airways", "iata_code": "ZZ"},
                    "operating_carrier_flight_number": "0001",
                    "aircraft": {"name": "Boeing 737"},
                }
            ],
        }
    ],
}


@pytest.mark.asyncio
async def test_search_offers_normalizes_response():
    raw = {"data": {"id": "orq_001", "offers": [_OFFER_RAW]}}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        results = await duffel_service.search_offers(
            origin="HAN", destination="SGN", depart_date=date(2026, 7, 1)
        )

    assert len(results) == 1
    o = results[0]
    assert o["duffel_offer_id"] == "off_0000test"
    assert o["total_amount"] == 123.45
    assert o["currency"] == "USD"
    assert o["airline_name"] == "Duffel Airways"
    assert o["airline_iata"] == "ZZ"
    assert o["source"] == "duffel"
    assert len(o["slices"]) == 1
    assert o["slices"][0]["origin"] == "HAN"
    assert o["slices"][0]["destination"] == "SGN"
    seg = o["slices"][0]["segments"][0]
    assert seg["origin_iata"] == "HAN"
    assert seg["destination_iata"] == "SGN"
    assert "ZZ" in seg["flight_number"]


@pytest.mark.asyncio
async def test_search_offers_round_trip_sends_two_slices():
    """Round-trip search builds two slices in the request body."""
    raw = {"data": {"id": "orq_002", "offers": []}}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        await duffel_service.search_offers(
            origin="HAN", destination="SGN",
            depart_date=date(2026, 7, 1), return_date=date(2026, 7, 8),
        )

        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["json"]
        slices = body["data"]["slices"]
        assert len(slices) == 2
        assert slices[0]["origin"] == "HAN"
        assert slices[1]["origin"] == "SGN"


@pytest.mark.asyncio
async def test_get_offer_normalizes_response():
    raw = {"data": _OFFER_RAW}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        offer = await duffel_service.get_offer("off_0000test")

    assert offer["duffel_offer_id"] == "off_0000test"
    assert offer["total_amount"] == 123.45
    assert offer["cabin_class"] == "economy"


@pytest.mark.asyncio
async def test_create_order_returns_order_id():
    offer_raw = {"data": _OFFER_RAW}
    order_raw = {
        "data": {
            "id": "ord_0000test",
            "booking_reference": "DUFXYZ",
            "status": "confirmed",
            "total_amount": "123.45",
            "total_currency": "USD",
        }
    }

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, offer_raw))
        mock_client.post = AsyncMock(return_value=_mock_response(200, order_raw))
        mock_client_fn.return_value = mock_client

        result = await duffel_service.create_order(
            duffel_offer_id="off_0000test",
            passenger={
                "first_name": "John", "last_name": "Doe",
                "email": "john@example.com", "gender": "M",
                "born_on": "1990-01-01", "title": "mr",
            },
            amount="123.45",
            currency="USD",
        )

    assert result["duffel_order_id"] == "ord_0000test"
    assert result["duffel_booking_ref"] == "DUFXYZ"
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
async def test_cancel_order_returns_true():
    cancel_raw = {"data": {"id": "oca_001"}}
    confirm_raw = {"data": {"id": "oca_001", "confirmed_at": "2026-07-01T12:00:00Z"}}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _mock_response(201, cancel_raw),
                _mock_response(200, confirm_raw),
            ]
        )
        mock_client_fn.return_value = mock_client

        ok = await duffel_service.cancel_order("ord_0000test")

    assert ok is True


@pytest.mark.asyncio
async def test_cancel_order_returns_false_on_error():
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(404, {"errors": [{"message": "Not found"}]}))
        mock_client_fn.return_value = mock_client

        ok = await duffel_service.cancel_order("ord_nonexistent")

    assert ok is False


@pytest.mark.asyncio
async def test_search_offers_raises_on_network_error():
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_fn.return_value = mock_client

        with pytest.raises(DuffelError) as exc_info:
            await duffel_service.search_offers("HAN", "SGN", date(2026, 7, 1))

    assert exc_info.value.status_code == 502
