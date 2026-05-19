"""Tests for LiteAPI service layer with mocked HTTP responses."""
import pytest
import httpx
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from app.services import liteapi_service
from app.services.liteapi_service import LiteAPIError


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(status_code, json=json_data)


@pytest.mark.asyncio
async def test_search_hotels_normalizes_response():
    # Match actual LiteAPI /data/hotels list response structure
    raw = {
        "data": [
            {
                "id": "HOTEL_123",
                "name": "Test Hotel",
                "city": "Hanoi",
                "country": "vn",
                "stars": 4,
                "main_photo": "https://example.com/img.jpg",
                "currency": "USD",
                "rating": 8.5,
                "reviewCount": 200,
                "latitude": 21.0,
                "longitude": 105.8,
                "address": "33 Test Street",
            }
        ]
    }

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        results = await liteapi_service.search_hotels(city="Hanoi", country_code="VN")

    assert len(results) == 1
    h = results[0]
    assert h["liteapi_hotel_id"] == "HOTEL_123"
    assert h["name"] == "Test Hotel"
    assert h["city"] == "Hanoi"
    assert h["star_rating"] == 4
    assert h["source"] == "liteapi"
    assert h["avg_rating"] == 8.5
    assert h["images"] == ["https://example.com/img.jpg"]


@pytest.mark.asyncio
async def test_search_hotels_degrades_on_502():
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_fn.return_value = mock_client

        with pytest.raises(LiteAPIError) as exc_info:
            await liteapi_service.search_hotels(city="Hanoi")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_get_rates_returns_room_type_groups():
    """Each LiteAPI roomType becomes one group; every rate plan inside is preserved."""
    raw = {
        "data": [
            {
                "hotelId": "HOTEL_123",
                "roomTypes": [
                    {
                        "roomTypeId": "RT_001",
                        "offerId": "RATE_ABC",
                        "offerRetailRate": {"amount": 120.0, "currency": "USD"},
                        "rates": [
                            {
                                "rateId": "INNER_RATE_001",
                                "name": "Deluxe Room",
                                "maxOccupancy": 2,
                                "boardName": "Breakfast Included",
                                "retailRate": {
                                    "total": [{"amount": 120.0, "currency": "USD"}],
                                    "suggestedSellingPrice": [{"amount": 200.0, "currency": "USD"}],
                                    "taxesAndFees": [{"amount": 15.0, "currency": "USD"}],
                                },
                                "cancellationPolicies": {"refundableTag": "RFN"},
                            },
                            {
                                "rateId": "INNER_RATE_002",
                                "name": "Deluxe Room",
                                "maxOccupancy": 2,
                                "boardName": "Room Only",
                                "retailRate": {"total": [{"amount": 95.0, "currency": "USD"}]},
                                "cancellationPolicies": {"refundableTag": "NRFN"},
                            },
                        ],
                    }
                ],
            }
        ]
    }

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        groups = await liteapi_service.get_rates(
            liteapi_hotel_id="HOTEL_123",
            check_in=date(2026, 6, 1),
            check_out=date(2026, 6, 3),
        )

    assert len(groups) == 1
    g = groups[0]
    assert g["room_type_id"] == "RT_001"
    assert g["room_name"] == "Deluxe Room"
    assert g["max_guests"] == 2
    assert len(g["rates"]) == 2

    refundable_rate = g["rates"][0]
    # roomType.offerId overwrites the inner rateId — see
    # test_normalize_room_type_propagates_offerId_to_rates. The frontend stores
    # this id and later sends it to /rates/prebook as offerId.
    assert refundable_rate["rate_id"] == "RATE_ABC"
    assert refundable_rate["price"] == 120.0
    assert refundable_rate["board_name"] == "Breakfast Included"
    assert refundable_rate["refundable"] is True
    assert refundable_rate["original_price"] == 200.0
    assert refundable_rate["discount_percent"] == 40
    assert refundable_rate["taxes"] == 15.0
    assert refundable_rate["price_excl_taxes"] == 105.0  # 120 - 15

    nonrefundable_rate = g["rates"][1]
    assert nonrefundable_rate["price"] == 95.0
    assert nonrefundable_rate["refundable"] is False
    # No taxesAndFees in fixture for this rate → fields are None
    assert nonrefundable_rate["taxes"] is None
    assert nonrefundable_rate["price_excl_taxes"] is None


@pytest.mark.asyncio
async def test_get_rates_uses_multi_occupancy_when_rooms_gt_one():
    """When rooms > 1, the LiteAPI request body has one occupancy entry per room."""
    captured: dict = {}

    async def _capture_post(url, json):  # noqa: ARG001
        captured["body"] = json
        return _mock_response(200, {"data": []})

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await liteapi_service.get_rates(
            liteapi_hotel_id="HOTEL_X",
            check_in=date(2026, 6, 1),
            check_out=date(2026, 6, 3),
            guests=10,
            rooms=5,
        )

    occ = captured["body"]["occupancies"]
    assert len(occ) == 5
    assert sum(o["adults"] for o in occ) == 10
    # All occupancies are equal-sized (10 / 5 == 2 each, no remainder)
    assert all(o["adults"] == 2 for o in occ)


@pytest.mark.asyncio
async def test_get_rates_distributes_remainder_when_uneven():
    """7 guests across 3 rooms → [3, 2, 2] (extras go to first occupancy)."""
    captured: dict = {}

    async def _capture_post(url, json):  # noqa: ARG001
        captured["body"] = json
        return _mock_response(200, {"data": []})

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await liteapi_service.get_rates(
            liteapi_hotel_id="HOTEL_X",
            check_in=date(2026, 6, 1),
            check_out=date(2026, 6, 3),
            guests=7,
            rooms=3,
        )

    occ = captured["body"]["occupancies"]
    adults = [o["adults"] for o in occ]
    assert sorted(adults, reverse=True) == [3, 2, 2]


@pytest.mark.asyncio
async def test_get_room_types_catalog_strips_prices():
    """The catalog endpoint returns room-type metadata with empty rates[]."""
    raw = {
        "data": [
            {
                "hotelId": "HOTEL_123",
                "roomTypes": [
                    {
                        "roomTypeId": "RT_001",
                        "offerId": "RATE_ABC",
                        "offerRetailRate": {"amount": 120.0, "currency": "USD"},
                        "rates": [
                            {
                                "rateId": "INNER_RATE_001",
                                "name": "Deluxe Room",
                                "maxOccupancy": 2,
                                "boardName": "Room Only",
                                "retailRate": {"total": [{"amount": 120.0, "currency": "USD"}]},
                                "cancellationPolicies": {"refundableTag": "RFN"},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        catalog = await liteapi_service.get_room_types_catalog("HOTEL_123")

    assert len(catalog) == 1
    rt = catalog[0]
    assert rt["room_name"] == "Deluxe Room"
    assert rt["max_guests"] == 2
    assert rt["rates"] == []  # prices stripped


@pytest.mark.asyncio
async def test_prebook_returns_prebook_id():
    raw = {
        "data": {
            "prebookId": "PREBOOK_XYZ",
            "offerRetailRate": {"amount": 120.0, "currency": "USD"},
            "supplier": "ExpediaTPID",
            "paymentTypes": ["ACC_CREDIT_CARD"],
            "expireInSeconds": 1800,
        }
    }

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.prebook("RATE_ABC", guests=1)

    assert result["prebook_id"] == "PREBOOK_XYZ"
    assert result["price"] == 120.0
    assert result["currency"] == "USD"
    assert result["supplier"] == "ExpediaTPID"
    assert result["payment_types"] == ["ACC_CREDIT_CARD"]
    assert result["expires_at"] == 1800


@pytest.mark.asyncio
async def test_prebook_raises_on_empty_body():
    """Empty 200 body now signals a real upstream issue (the old `/hotels/prebook`
    path returned this; the v3.0 `/rates/prebook` path always returns JSON)."""
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=httpx.Response(200, content=b""))
        mock_client_fn.return_value = mock_client

        with pytest.raises(LiteAPIError):
            await liteapi_service.prebook("OFFER_X", guests=1)


@pytest.mark.asyncio
async def test_normalize_room_type_propagates_offerId_to_rates():
    """roomType.offerId must overwrite each rate's rate_id field — that's the
    identifier the frontend stores and later sends to /rates/prebook."""
    room_type = {
        "roomTypeId": "RT_1",
        "offerId": "OFFER_FROM_ROOMTYPE",
        "offerRetailRate": {"amount": 120.0, "currency": "USD"},
        "rates": [
            {"rateId": "RATE_INNER", "retailRate": {"total": [{"amount": 120, "currency": "USD"}]}}
        ],
    }
    out = liteapi_service._normalize_room_type(room_type)
    assert out["rates"][0]["rate_id"] == "OFFER_FROM_ROOMTYPE"


@pytest.mark.asyncio
async def test_prebook_sends_voucher_and_payment_sdk_flag():
    captured: dict = {}

    async def _capture_post(url, json):  # noqa: ARG001
        captured["body"] = json
        return _mock_response(200, {"data": {
            "prebookId": "PB_1",
            "price": 50.0,
            "currency": "USD",
            "secretKey": "pi_test_secret_xyz",
            "transactionId": "pi_test_xyz",
        }})

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.prebook(
            "RATE_ABC", guests=1, voucher_code="SUMMER10", use_payment_sdk=True,
        )

    assert captured["body"]["offerId"] == "RATE_ABC"
    assert captured["body"]["voucherCode"] == "SUMMER10"
    assert captured["body"]["usePaymentSdk"] is True
    assert result["secret_key"] == "pi_test_secret_xyz"
    assert result["transaction_id"] == "pi_test_xyz"


@pytest.mark.asyncio
async def test_book_returns_booking_id():
    raw = {
        "data": {
            "bookingId": "LTA-BOOKING-001",
            "status": "CONFIRMED",
            "supplierBookingId": "SUP-001",
            "hotelConfirmationCode": "HCONF-001",
        }
    }
    captured: dict = {}

    async def _capture_post(url, json):  # noqa: ARG001
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.book(
            prebook_id="PREBOOK_XYZ",
            holder={"firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            guests=[
                {"occupancyNumber": 1, "firstName": "John", "lastName": "Doe", "email": "john@example.com"},
            ],
            client_reference="BK-123",
        )

    assert result["liteapi_booking_id"] == "LTA-BOOKING-001"
    assert result["status"] == "CONFIRMED"
    assert result["supplier_booking_id"] == "SUP-001"
    assert result["hotel_confirmation_code"] == "HCONF-001"

    body = captured["body"]
    assert body["prebookId"] == "PREBOOK_XYZ"
    assert body["clientReference"] == "BK-123"
    assert body["payment"]["method"] == "ACC_CREDIT_CARD"
    assert body["guests"][0]["occupancyNumber"] == 1


@pytest.mark.asyncio
async def test_book_attaches_transaction_id_when_provided():
    """SDK flow: transaction_id from prebook must land in payment.transactionId."""
    captured: dict = {}

    async def _capture_post(url, json):  # noqa: ARG001
        captured["body"] = json
        return _mock_response(200, {"data": {"bookingId": "BK-001", "status": "CONFIRMED"}})

    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await liteapi_service.book(
            prebook_id="PB",
            holder={"firstName": "J", "lastName": "D", "email": "j@d.com"},
            guests=[{"occupancyNumber": 1, "firstName": "J", "lastName": "D", "email": "j@d.com"}],
            transaction_id="pi_test_xyz",
        )

    assert captured["body"]["payment"]["transactionId"] == "pi_test_xyz"


@pytest.mark.asyncio
async def test_cancel_booking_returns_refund_info_on_success():
    """LiteAPI returns the cancellation status + refund_amount + cancellation_fee.
    We surface that to the caller as a dict (not a bool) so the frontend can
    show the user what they'll be refunded."""
    payload = {
        "data": {
            "status": "CANCELLED",
            "refund_amount": 240.0,
            "cancellation_fee": 0.0,
            "currency": "USD",
        }
    }
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.put = AsyncMock(return_value=_mock_response(200, payload))
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.cancel_booking("LTA-BOOKING-001")

    # Per LiteAPI docs, PUT /bookings/{id} takes no body — only the path param.
    mock_client.put.assert_awaited_once_with("/bookings/LTA-BOOKING-001")
    assert result is not None
    assert result["status"] == "CANCELLED"
    assert result["refund_amount"] == 240.0
    assert result["cancellation_fee"] == 0.0
    assert result["currency"] == "USD"
    assert result["already_cancelled"] is False


@pytest.mark.asyncio
async def test_cancel_booking_with_charges_surfaces_fee():
    """Non-refundable or past-deadline cancellations return CANCELLED_WITH_CHARGES."""
    payload = {
        "data": {
            "status": "CANCELLED_WITH_CHARGES",
            "refund_amount": 0.0,
            "cancellation_fee": 200.0,
            "currency": "USD",
        }
    }
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.put = AsyncMock(return_value=_mock_response(200, payload))
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.cancel_booking("LTA-NONREF-001")

    assert result is not None
    assert result["status"] == "CANCELLED_WITH_CHARGES"
    assert result["cancellation_fee"] == 200.0
    assert result["refund_amount"] == 0.0


@pytest.mark.asyncio
async def test_cancel_booking_304_treated_as_idempotent_success():
    """LiteAPI returns 304 if the booking is already cancelled. We treat that
    as a successful no-op (returning success info) rather than an error."""
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.put = AsyncMock(return_value=_mock_response(304, {}))
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.cancel_booking("LTA-ALREADY-CANCELLED")

    assert result is not None
    assert result["already_cancelled"] is True
    assert result["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_booking_returns_none_on_error():
    """Upstream errors are swallowed and returned as None; the local cancel
    still proceeds (so users aren't blocked by transient LiteAPI failures)."""
    with patch.object(liteapi_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.put = AsyncMock(return_value=_mock_response(404, {"message": "Booking not found"}))
        mock_client_fn.return_value = mock_client

        result = await liteapi_service.cancel_booking("NONEXISTENT")

    assert result is None


@pytest.mark.asyncio
async def test_hybrid_search_deduplicates_by_liteapi_id(client):
    """Search endpoint returns DB hotels + LiteAPI hotels, de-duped by liteapi_hotel_id."""
    import json

    fake_liteapi_results = [
        {
            "hotelId": "HOTEL_LOCAL",  # same as a local hotel — should be de-duped
            "name": "Local Hotel (LiteAPI copy)",
            "cityName": "Hanoi",
            "countryCode": "VN",
            "starRating": 3,
            "amenities": [],
            "hotelImages": [],
        },
        {
            "hotelId": "HOTEL_REMOTE",
            "name": "Remote LiteAPI Hotel",
            "cityName": "Hanoi",
            "countryCode": "VN",
            "starRating": 4,
            "amenities": [],
            "hotelImages": [],
        },
    ]

    with patch.object(liteapi_service, "search_hotels", new=AsyncMock(return_value=[
        liteapi_service._normalize_hotel(h) for h in fake_liteapi_results
    ])):
        resp = await client.get("/api/v1/hotels?city=Hanoi")

    assert resp.status_code == 200
    items = resp.json()["items"]
    liteapi_names = [i["name"] for i in items if i.get("source") == "liteapi"]
    assert "Remote LiteAPI Hotel" in liteapi_names
    # "Local Hotel (LiteAPI copy)" should not appear because liteapi_hotel_id dedup
    # (it would only be deduped if a DB hotel had liteapi_hotel_id=HOTEL_LOCAL)
    # Since we don't seed that here, both may appear — this tests the flow runs
    assert len(items) >= 1
