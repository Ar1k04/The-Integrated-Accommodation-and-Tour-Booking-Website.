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
            passengers=[{
                "first_name": "John", "last_name": "Doe",
                "email": "john@example.com", "gender": "M",
                "born_on": "1990-01-01", "title": "mr",
            }],
            amount="123.45",
            currency="USD",
        )

    assert result["duffel_order_id"] == "ord_0000test"
    assert result["duffel_booking_ref"] == "DUFXYZ"
    assert result["status"] == "confirmed"


@pytest.mark.asyncio
async def test_create_order_multi_passenger_assigns_distinct_names():
    """Each Duffel pax_id receives the corresponding passenger dict, not a duplicate."""
    offer_raw_multi = {
        "data": {
            **_OFFER_RAW,
            "passengers": [
                {"id": "pas_001", "type": "adult"},
                {"id": "pas_002", "type": "adult"},
                {"id": "pas_003", "type": "adult"},
            ],
        }
    }
    order_raw = {
        "data": {
            "id": "ord_multi",
            "booking_reference": "MULTI1",
            "status": "confirmed",
            "total_amount": "370.35",
            "total_currency": "USD",
        }
    }

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, offer_raw_multi))
        mock_client.post = AsyncMock(return_value=_mock_response(200, order_raw))
        mock_client_fn.return_value = mock_client

        await duffel_service.create_order(
            duffel_offer_id="off_0000test",
            passengers=[
                {"first_name": "Alice", "last_name": "Doe", "email": "a@x.com",
                 "gender": "F", "born_on": "1990-01-01", "title": "ms"},
                {"first_name": "Bob", "last_name": "Smith", "email": "b@x.com",
                 "gender": "M", "born_on": "1985-05-10", "title": "mr"},
                {"first_name": "Carol", "last_name": "Lee", "email": "c@x.com",
                 "gender": "F", "born_on": "2010-08-20", "title": "ms"},
            ],
            amount="370.35",
            currency="USD",
        )

        call = mock_client.post.call_args
        body = call.kwargs.get("json") or call.args[1]
        sent_pax = body["data"]["passengers"]
        names = [p["given_name"] for p in sent_pax]
        assert names == ["Alice", "Bob", "Carol"]
        assert sent_pax[0]["id"] == "pas_001"
        assert sent_pax[1]["id"] == "pas_002"
        assert sent_pax[2]["id"] == "pas_003"


@pytest.mark.asyncio
async def test_search_offers_mixes_adult_type_and_child_age():
    """search_offers builds passengers payload with type:adult + age:N for kids."""
    raw = {"data": {"id": "orq_kids", "offers": []}}
    captured: dict = {}

    async def _capture_post(url, json):
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await duffel_service.search_offers(
            origin="HAN", destination="SGN",
            depart_date=date(2026, 7, 1),
            adults=2,
            child_ages=[8],
        )

    pax = captured["body"]["data"]["passengers"]
    # Two {type:adult} + one {age:8} — Duffel + the airline decide the
    # child vs infant_without_seat mapping themselves.
    assert pax == [
        {"type": "adult"},
        {"type": "adult"},
        {"age": 8},
    ]


@pytest.mark.asyncio
async def test_search_offers_back_compat_with_passengers_kw():
    """Old callsites that still send passengers=N keep working."""
    raw = {"data": {"id": "orq_legacy", "offers": []}}
    captured: dict = {}

    async def _capture_post(url, json):
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await duffel_service.search_offers(
            origin="HAN", destination="SGN",
            depart_date=date(2026, 7, 1),
            passengers=3,
        )

    pax = captured["body"]["data"]["passengers"]
    assert pax == [{"type": "adult"}] * 3


@pytest.mark.asyncio
async def test_create_order_attaches_age_for_minors_only():
    """Adults submit born_on; minors also submit `age`."""
    offer_raw_with_minor = {
        "data": {
            **_OFFER_RAW,
            "passengers": [
                {"id": "pas_a1", "type": "adult"},
                {"id": "pas_c1", "age": 8},
            ],
        }
    }
    order_raw = {
        "data": {
            "id": "ord_minor",
            "booking_reference": "MINOR1",
            "status": "confirmed",
            "total_amount": "200.00",
            "total_currency": "USD",
        }
    }
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, offer_raw_with_minor))
        mock_client.post = AsyncMock(return_value=_mock_response(200, order_raw))
        mock_client_fn.return_value = mock_client

        await duffel_service.create_order(
            duffel_offer_id="off_0000test",
            passengers=[
                {"first_name": "Alice", "last_name": "Doe", "email": "a@x.com",
                 "gender": "F", "born_on": "1990-01-01", "title": "ms"},
                {"first_name": "Bobby", "last_name": "Doe", "email": "b@x.com",
                 "gender": "M", "born_on": "2018-03-15", "title": "mr", "age": 8},
            ],
            amount="200.00",
            currency="USD",
        )

    body = mock_client.post.call_args.kwargs.get("json") or mock_client.post.call_args.args[1]
    sent_pax = body["data"]["passengers"]
    # Adult: no age field
    assert "age" not in sent_pax[0]
    # Child: age forwarded
    assert sent_pax[1]["age"] == 8


def test_normalize_offer_exposes_passenger_breakdown():
    """_normalize_offer surfaces per-pax type/age so the frontend can label
    each form field correctly."""
    raw = {
        **_OFFER_RAW,
        "passengers": [
            {"id": "pas_a1", "type": "adult"},
            {"id": "pas_c1", "age": 8},
        ],
    }
    offer = duffel_service._normalize_offer(raw)
    assert offer["passengers"] == 2
    breakdown = offer["passenger_breakdown"]
    assert len(breakdown) == 2
    assert breakdown[0]["type"] == "adult"
    assert breakdown[0]["age"] is None
    assert breakdown[1]["age"] == 8


@pytest.mark.asyncio
async def test_create_order_passenger_count_mismatch_raises_422():
    """Mismatch between offer pax_ids and provided passenger list must raise 422."""
    offer_raw_2pax = {
        "data": {
            **_OFFER_RAW,
            "passengers": [
                {"id": "pas_001", "type": "adult"},
                {"id": "pas_002", "type": "adult"},
            ],
        }
    }
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, offer_raw_2pax))
        mock_client.post = AsyncMock()
        mock_client_fn.return_value = mock_client

        with pytest.raises(DuffelError) as exc_info:
            await duffel_service.create_order(
                duffel_offer_id="off_0000test",
                passengers=[{
                    "first_name": "Alice", "last_name": "Doe", "email": "a@x.com",
                    "gender": "F", "born_on": "1990-01-01", "title": "ms",
                }],
                amount="246.90",
                currency="USD",
            )
        assert exc_info.value.status_code == 422
        mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_order_forwards_services_and_seats():
    """When services + selected_seats provided, they appear in the POST body."""
    offer_raw_2pax = {
        "data": {
            **_OFFER_RAW,
            "passengers": [
                {"id": "pas_001", "type": "adult"},
                {"id": "pas_002", "type": "adult"},
            ],
        }
    }
    order_raw = {"data": {"id": "ord_seats", "booking_reference": "SEATS1", "status": "confirmed",
                          "total_amount": "246.90", "total_currency": "USD"}}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, offer_raw_2pax))
        mock_client.post = AsyncMock(return_value=_mock_response(200, order_raw))
        mock_client_fn.return_value = mock_client

        await duffel_service.create_order(
            duffel_offer_id="off_0000test",
            passengers=[
                {"first_name": "Alice", "last_name": "Doe", "email": "a@x.com",
                 "gender": "F", "born_on": "1990-01-01", "title": "ms"},
                {"first_name": "Bob", "last_name": "Smith", "email": "b@x.com",
                 "gender": "M", "born_on": "1985-05-10", "title": "mr"},
            ],
            amount="246.90",
            currency="USD",
            services=[{"id": "ase_bag123", "quantity": 1}],
            selected_seats={"0": "ase_seat12A", "1": "ase_seat12B"},
        )

        body = mock_client.post.call_args.kwargs["json"]["data"]
        assert body["services"] == [{"id": "ase_bag123", "quantity": 1}]
        assert body["passengers"][0]["seat"] == "ase_seat12A"
        assert body["passengers"][1]["seat"] == "ase_seat12B"


@pytest.mark.asyncio
async def test_get_order_normalizes_response():
    raw = {
        "data": {
            "id": "ord_xyz",
            "booking_reference": "PNR123",
            "status": "confirmed",
            "total_amount": "200.00",
            "total_currency": "USD",
            "passengers": [
                {"id": "pas_1", "given_name": "Alice", "family_name": "Doe",
                 "email": "a@x.com", "title": "ms", "born_on": "1990-01-01"},
            ],
            "slices": _OFFER_RAW["slices"],
            "documents": [{"type": "electronic_ticket", "unique_identifier": "TICKET-1"}],
        }
    }
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        order = await duffel_service.get_order("ord_xyz")

    assert order["duffel_order_id"] == "ord_xyz"
    assert order["duffel_booking_ref"] == "PNR123"
    assert order["passengers"][0]["given_name"] == "Alice"
    assert order["documents"][0]["type"] == "electronic_ticket"
    assert len(order["slices"]) == 1


@pytest.mark.asyncio
async def test_get_seat_maps_returns_empty_on_404():
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(404, {}))
        mock_client_fn.return_value = mock_client

        result = await duffel_service.get_seat_maps("off_no_seats")

    assert result == []


@pytest.mark.asyncio
async def test_get_available_services_returns_list():
    raw = {
        "data": {
            **_OFFER_RAW,
            "available_services": [
                {"id": "ase_bag1", "type": "baggage", "total_amount": "25.00", "total_currency": "USD"},
            ],
        }
    }
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        services = await duffel_service.get_available_services("off_0000test")

    assert len(services) == 1
    assert services[0]["type"] == "baggage"


@pytest.mark.asyncio
async def test_cancel_order_returns_refund_dict():
    cancel_raw = {"data": {"id": "oca_001"}}
    confirm_raw = {
        "data": {
            "id": "oca_001",
            "confirmed_at": "2026-07-01T12:00:00Z",
            "refund_amount": "120.50",
            "refund_currency": "USD",
        }
    }

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _mock_response(201, cancel_raw),
                _mock_response(200, confirm_raw),
            ]
        )
        mock_client_fn.return_value = mock_client

        result = await duffel_service.cancel_order("ord_0000test")

    assert result == {"status": "cancelled", "refund_amount": 120.5, "currency": "USD"}


@pytest.mark.asyncio
async def test_cancel_order_non_refundable():
    cancel_raw = {"data": {"id": "oca_002"}}
    confirm_raw = {"data": {"id": "oca_002", "confirmed_at": "2026-07-01T12:00:00Z"}}

    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _mock_response(201, cancel_raw),
                _mock_response(200, confirm_raw),
            ]
        )
        mock_client_fn.return_value = mock_client

        result = await duffel_service.cancel_order("ord_nonrefundable")

    assert result is not None
    assert result["refund_amount"] is None


@pytest.mark.asyncio
async def test_cancel_order_returns_none_on_error():
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(404, {"errors": [{"message": "Not found"}]}))
        mock_client_fn.return_value = mock_client

        result = await duffel_service.cancel_order("ord_nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_search_offers_raises_on_network_error():
    with patch.object(duffel_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_fn.return_value = mock_client

        with pytest.raises(DuffelError) as exc_info:
            await duffel_service.search_offers("HAN", "SGN", date(2026, 7, 1))

    assert exc_info.value.status_code == 502
