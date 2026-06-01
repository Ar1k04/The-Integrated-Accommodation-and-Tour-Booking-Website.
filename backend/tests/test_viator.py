"""Tests for Viator service layer with mocked HTTP responses."""
import time

import pytest
import httpx
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from app.services import viator_service
from app.services.viator_service import ViatorError


def _mock_response(status_code: int, json_data: dict) -> httpx.Response:
    return httpx.Response(status_code, json=json_data)


@pytest.fixture(autouse=True)
def _populate_dest_cache():
    """Pre-populate the /destinations cache so search_tours skips the HTTP
    call. Using the same fallback list the service ships with — it includes
    Hanoi (351), Halong Bay (776), and Vietnam (21)."""
    viator_service._DEST_CACHE["data"] = viator_service._FALLBACK_DESTINATIONS
    viator_service._DEST_CACHE["index"] = viator_service._build_dest_index(
        viator_service._FALLBACK_DESTINATIONS
    )
    viator_service._DEST_CACHE["fetched_at"] = time.time()
    yield
    viator_service._DEST_CACHE["data"] = None
    viator_service._DEST_CACHE["index"] = None
    viator_service._DEST_CACHE["fetched_at"] = 0.0


@pytest.mark.asyncio
async def test_search_tours_normalizes_response():
    raw = {
        "products": [
            {
                "productCode": "TOUR_VN_001",
                "title": "Hanoi Old Quarter Walking Tour",
                "description": "Explore the 36 streets",
                "duration": {"fixedDurationInMinutes": 240},
                "pricing": {"summary": {"fromPrice": 25.0}},
                "images": [
                    {"variants": [{"url": "https://example.com/tour.jpg", "width": 800, "height": 600}]}
                ],
                "reviews": {"combinedAverageRating": 4.5, "totalReviews": 312},
                "destinations": [{"name": "Hanoi", "primary": True}],
                "tags": [42],
            }
        ],
        "totalCount": 1,
    }

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        results = await viator_service.search_tours(city="Hanoi", limit=3)

    products = results["products"]
    assert results["total"] == 1
    assert len(products) == 1
    t = products[0]
    assert t["viator_product_code"] == "TOUR_VN_001"
    assert t["name"] == "Hanoi Old Quarter Walking Tour"
    assert t["city"] == "Hanoi"
    assert t["price_per_person"] == 25.0
    assert t["avg_rating"] == 4.5
    assert t["total_reviews"] == 312
    assert t["images"] == ["https://example.com/tour.jpg"]
    assert t["source"] == "viator"


@pytest.mark.asyncio
async def test_search_tours_sends_viator_filter_payload():
    raw = {"products": [], "totalCount": 0}

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        await viator_service.search_tours(
            city="Hanoi",
            tags=[21909, 11940],
            flags=["FREE_CANCELLATION", "PRIVATE_TOUR"],
            rating_from=4,
            duration_from_min=60,
            duration_to_min=240,
            lowest_price=10,
            highest_price=100,
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
            sort="PRICE",
            order="ASCENDING",
            start=3,
            count=5,
        )

    call = mock_client.post.await_args
    assert call.args[0] == "/products/search"
    assert call.kwargs["headers"]["Accept-Language"] == "en"
    body = call.kwargs["json"]
    assert body["filtering"] == {
        "destination": "351",
        "tags": [21909, 11940],
        "flags": ["FREE_CANCELLATION", "PRIVATE_TOUR"],
        "rating": {"from": 4.0},
        "durationInMinutes": {"from": 60, "to": 240},
        "lowestPrice": 10.0,
        "highestPrice": 100.0,
        "startDate": "2026-06-01",
        "endDate": "2026-06-30",
    }
    assert body["pagination"] == {"start": 3, "count": 5}
    assert body["sorting"] == {"sort": "PRICE", "order": "ASCENDING"}


@pytest.mark.asyncio
async def test_get_tags_preserves_locale_names():
    viator_service._TAG_CACHE["data"] = None
    viator_service._TAG_CACHE["fetched_at"] = 0
    raw = {
        "tags": [
            {
                "tagId": 21768,
                "parentTagIds": [21701, 21913],
                "allNamesByLocale": {
                    "en": "Shore Excursions",
                    "fr": "Excursions en bord de mer",
                },
            }
        ]
    }

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        tags = await viator_service.get_tags()

    assert tags == [
        {
            "tag_id": 21768,
            "parent_tag_id": 21701,
            "name": "Shore Excursions",
            "names_by_locale": {
                "en": "Shore Excursions",
                "fr": "Excursions en bord de mer",
            },
        }
    ]


@pytest.mark.asyncio
async def test_search_tours_degrades_on_unknown_city():
    """City with no known destination ID raises ViatorError(400) — caller should degrade gracefully."""
    with pytest.raises(ViatorError) as exc_info:
        await viator_service.search_tours(city="Atlantis")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_resolve_destination_handles_vietnamese_diacritics():
    """'Hà Nội' must resolve to Hanoi (351) — not the country and not Halong Bay."""
    match = await viator_service.resolve_destination("Hà Nội")
    assert match is not None
    assert match["destinationId"] == "351"
    assert match["name"] == "Hanoi"
    assert match["type"] == "CITY"


@pytest.mark.asyncio
async def test_resolve_destination_halong_bay_separate_from_hanoi():
    """'Hạ Long' must resolve to Halong Bay (22692 in the real Viator catalog),
    not fall through to Hanoi."""
    match = await viator_service.resolve_destination("Hạ Long")
    assert match is not None
    assert match["destinationId"] == "22692"
    assert match["name"] == "Halong Bay"


@pytest.mark.asyncio
async def test_resolve_destination_prefers_city_over_country():
    """Bare 'Hanoi' must hit the CITY destination, not Vietnam (the country)."""
    match = await viator_service.resolve_destination("Hanoi")
    assert match is not None
    assert match["destinationId"] == "351"
    assert match["type"] == "CITY"


@pytest.mark.asyncio
async def test_resolve_destination_alias_saigon_to_ho_chi_minh():
    """User types 'Saigon' but Viator catalogs it as 'Ho Chi Minh City' (352)."""
    match = await viator_service.resolve_destination("saigon")
    assert match is not None
    assert match["destinationId"] == "352"
    assert match["name"] == "Ho Chi Minh City"


@pytest.mark.asyncio
async def test_resolve_destination_returns_none_for_unknown():
    assert await viator_service.resolve_destination("Atlantis") is None
    assert await viator_service.resolve_destination("") is None
    assert await viator_service.resolve_destination("   ") is None


@pytest.mark.asyncio
async def test_search_destinations_autocomplete_ranks_exact_first():
    """Autocomplete on 'han' returns Hanoi at top; on 'ha' it includes Halong Bay and Hanoi."""
    matches = await viator_service.search_destinations("han", limit=5)
    assert matches, "expected at least one match for 'han'"
    assert matches[0]["destinationId"] == "351"

    matches_ha = await viator_service.search_destinations("ha", limit=10)
    ids = [m["destinationId"] for m in matches_ha]
    assert "351" in ids  # Hanoi prefix
    assert "22692" in ids  # Halong Bay prefix


@pytest.mark.asyncio
async def test_normalize_product_exposes_all_destinations_and_departs_from():
    """A Halong-cruise-from-Hanoi product visited via Hanoi search should set
    departs_from=Hanoi so the card can show context.

    Mirrors the real /products/search shape: each destination is
    {ref, primary} — names are resolved via the cached /destinations index.
    """
    raw = {
        "products": [
            {
                "productCode": "TOUR_VN_002",
                "title": "Halong Bay Day Cruise from Hanoi",
                "destinations": [
                    {"ref": "22692", "primary": True},   # Halong Bay
                    {"ref": "351", "primary": False},    # Hanoi
                ],
                "pricing": {"summary": {"fromPrice": 89.0}},
            }
        ],
        "totalCount": 1,
    }
    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        results = await viator_service.search_tours(city="Hanoi")

    p = results["products"][0]
    assert p["city"] == "Halong Bay"
    assert p["destinations"] == ["Halong Bay", "Hanoi"]
    assert p["departs_from"] == "Hanoi"


@pytest.mark.asyncio
async def test_search_tours_degrades_on_api_error():
    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_fn.return_value = mock_client

        with pytest.raises(ViatorError) as exc_info:
            await viator_service.search_tours(city="Hanoi")

    assert exc_info.value.status_code == 502


@pytest.mark.asyncio
async def test_check_availability_available():
    # check_availability tries POST /availability/check first,
    # falls back to GET /availability/schedules on 403.
    # Simulate 403 → schedules fallback with fromPrice=30.0
    schedules_raw = {
        "productCode": "TOUR_VN_001",
        "currency": "USD",
        "summary": {"fromPrice": 30.0},
        "bookableItems": [],
    }

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(403, {"code": "FORBIDDEN", "message": "Endpoint access denied"}))
        mock_client.get = AsyncMock(return_value=_mock_response(200, schedules_raw))
        mock_client_fn.return_value = mock_client

        result = await viator_service.check_availability("TOUR_VN_001", date(2026, 6, 1), guests=2)

    assert result["available"] is True
    assert result["price"] == 30.0
    assert result["currency"] == "USD"


@pytest.mark.asyncio
async def test_check_availability_not_available():
    raw = {"bookableItems": []}

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        result = await viator_service.check_availability("TOUR_VN_001", date(2026, 6, 1))

    assert result["available"] is False
    assert result["price"] == 0.0


@pytest.mark.asyncio
async def test_book_tour_returns_booking_ref():
    raw = {
        "bookingRef": "VIATOR-BR-001",
        "bookingStatus": "CONFIRMED",
    }

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        result = await viator_service.book_tour(
            viator_product_code="TOUR_VN_001",
            tour_date=date(2026, 6, 1),
            guests=2,
            guest_first_name="John",
            guest_last_name="Doe",
            guest_email="john@example.com",
        )

    assert result["viator_booking_ref"] == "VIATOR-BR-001"
    assert result["status"] == "CONFIRMED"


def test_map_ages_to_paxmix_splits_child_and_infant():
    bands = [
        {"age_band": "ADULT", "start_age": 13, "end_age": 99},
        {"age_band": "CHILD", "start_age": 4, "end_age": 12},
        {"age_band": "INFANT", "start_age": 0, "end_age": 3},
    ]
    result = viator_service._map_ages_to_paxmix([2, 8, 11], bands)
    # Aggregated: 1 INFANT (age 2) + 2 CHILD (8, 11). ADULT is never returned
    # from this helper — adults are added at the call site separately.
    by_band = {entry["ageBand"]: entry["numberOfTravelers"] for entry in result}
    assert by_band == {"INFANT": 1, "CHILD": 2}


def test_map_ages_to_paxmix_uses_supplier_specific_ranges():
    # A supplier where YOUTH covers 8–17 — age 8 must NOT map to CHILD.
    bands = [
        {"age_band": "ADULT", "start_age": 18, "end_age": 99},
        {"age_band": "YOUTH", "start_age": 8, "end_age": 17},
        {"age_band": "CHILD", "start_age": 3, "end_age": 7},
    ]
    result = viator_service._map_ages_to_paxmix([8], bands)
    assert result == [{"ageBand": "YOUTH", "numberOfTravelers": 1}]


def test_map_ages_to_paxmix_rejects_unmatched_age():
    bands = [
        {"age_band": "ADULT", "start_age": 18, "end_age": 99},
        {"age_band": "CHILD", "start_age": 6, "end_age": 12},
    ]
    # Age 3 doesn't fit any child band — supplier doesn't accept toddlers.
    with pytest.raises(ViatorError) as exc:
        viator_service._map_ages_to_paxmix([3], bands)
    assert "outside this tour's accepted age bands" in exc.value.message


def test_map_ages_to_paxmix_rejects_adults_only_tour():
    bands = [{"age_band": "ADULT", "start_age": 18, "end_age": 99}]
    with pytest.raises(ViatorError) as exc:
        viator_service._map_ages_to_paxmix([8], bands)
    assert "only accepts adults" in exc.value.message


@pytest.mark.asyncio
async def test_check_availability_sends_multi_band_paxmix():
    raw = {
        "bookableItems": [
            {
                "available": True,
                "totalPrice": {
                    "price": {"recommendedRetailPrice": {"price": 90.0}}
                },
            }
        ],
        "currency": "USD",
    }
    captured: dict = {}

    async def _capture_post(url, json, headers=None):
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await viator_service.check_availability(
            "TOUR_VN_001",
            date(2026, 6, 1),
            adults=2,
            children_ages=[8],
            age_bands=[
                {"age_band": "ADULT", "start_age": 13, "end_age": 99},
                {"age_band": "CHILD", "start_age": 4, "end_age": 12},
            ],
        )

    paxmix = captured["body"]["paxMix"]
    by_band = {entry["ageBand"]: entry["numberOfTravelers"] for entry in paxmix}
    assert by_band == {"ADULT": 2, "CHILD": 1}


@pytest.mark.asyncio
async def test_check_availability_back_compat_with_guests_kw():
    raw = {
        "bookableItems": [
            {
                "available": True,
                "totalPrice": {
                    "price": {"recommendedRetailPrice": {"price": 100.0}}
                },
            }
        ],
        "currency": "USD",
    }
    captured: dict = {}

    async def _capture_post(url, json, headers=None):
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        # Legacy callers (booking_service before the migration) still pass guests=N.
        await viator_service.check_availability(
            "TOUR_VN_001", date(2026, 6, 1), guests=3,
        )

    paxmix = captured["body"]["paxMix"]
    assert paxmix == [{"ageBand": "ADULT", "numberOfTravelers": 3}]


@pytest.mark.asyncio
async def test_book_tour_sends_multi_band_paxmix():
    raw = {"bookingRef": "VIATOR-BR-002", "bookingStatus": "CONFIRMED"}
    captured: dict = {}

    async def _capture_post(url, json, headers=None):
        captured["body"] = json
        return _mock_response(200, raw)

    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=_capture_post)
        mock_client_fn.return_value = mock_client

        await viator_service.book_tour(
            "TOUR_VN_001",
            date(2026, 6, 1),
            adults=2,
            children_ages=[10],
            age_bands=[
                {"age_band": "ADULT", "start_age": 13, "end_age": 99},
                {"age_band": "CHILD", "start_age": 4, "end_age": 12},
            ],
        )

    by_band = {e["ageBand"]: e["numberOfTravelers"] for e in captured["body"]["paxMix"]}
    assert by_band == {"ADULT": 2, "CHILD": 1}


@pytest.mark.asyncio
async def test_cancel_booking_returns_refund_dict():
    # Cancel is now POST /bookings/{ref}/cancel and returns a refund dict.
    raw = {
        "status": "ACCEPTED",
        "refundDetails": {"refundAmount": 35.0, "currencyCode": "USD"},
    }
    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, raw))
        mock_client_fn.return_value = mock_client

        result = await viator_service.cancel_booking("VIATOR-BR-001")

    assert result == {"status": "ACCEPTED", "refund_amount": 35.0, "currency": "USD"}


@pytest.mark.asyncio
async def test_cancel_booking_non_refundable_returns_none_amount():
    # Viator may return status without a refundDetails block for non-refundable bookings.
    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(200, {"status": "ACCEPTED"}))
        mock_client_fn.return_value = mock_client

        result = await viator_service.cancel_booking("VIATOR-NR-001")

    assert result is not None
    assert result["refund_amount"] is None


@pytest.mark.asyncio
async def test_cancel_booking_returns_none_on_error():
    with patch.object(viator_service, "_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=_mock_response(404, {"message": "Booking not found"}))
        mock_client_fn.return_value = mock_client

        result = await viator_service.cancel_booking("NONEXISTENT")

    assert result is None


@pytest.mark.asyncio
async def test_hybrid_search_includes_viator_tours(client):
    """Tour search with city filter returns Viator results tagged source=viator."""
    fake_viator_results = [
        {
            "viator_product_code": "VIATOR_HANOI_001",
            "name": "Viator Hanoi Tour",
            "city": "Hanoi",
            "country": "VN",
            "duration_days": 1,
            "max_participants": 15,
            "price_per_person": 25.0,
            "currency": "USD",
            "images": [],
            "avg_rating": 4.5,
            "total_reviews": 100,
            "source": "viator",
        }
    ]

    fake_payload = {"products": fake_viator_results, "total": len(fake_viator_results)}
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=fake_payload)):
        resp = await client.get("/api/v1/tours?city=Hanoi")

    assert resp.status_code == 200
    items = resp.json()["items"]
    viator_names = [i["name"] for i in items if i.get("source") == "viator"]
    assert "Viator Hanoi Tour" in viator_names


@pytest.mark.asyncio
async def test_hybrid_search_forwards_advanced_filters(client):
    fake_payload = {"products": [], "total": 0}
    search_mock = AsyncMock(return_value=fake_payload)

    with patch.object(viator_service, "search_tours", new=search_mock):
        resp = await client.get(
            "/api/v1/tours"
            "?city=Hanoi"
            "&tags=21909&tags=11940"
            "&flags=FREE_CANCELLATION&flags=PRIVATE_TOUR"
            "&rating_min=4"
            "&duration_min=60&duration_max=240"
            "&min_price=10&max_price=100"
            "&start_date=2026-06-01&end_date=2026-06-30"
            "&sort_by=price_per_person&sort_order=asc"
            "&page=2&per_page=5"
        )

    assert resp.status_code == 200
    search_mock.assert_awaited_once()
    kwargs = search_mock.await_args.kwargs
    assert kwargs["city"] == "Hanoi"
    assert kwargs["tags"] == [21909, 11940]
    assert kwargs["flags"] == ["FREE_CANCELLATION", "PRIVATE_TOUR"]
    assert kwargs["rating_from"] == 4
    assert kwargs["duration_from_min"] == 60
    assert kwargs["duration_to_min"] == 240
    assert kwargs["lowest_price"] == 10
    assert kwargs["highest_price"] == 100
    assert kwargs["start_date"] == date(2026, 6, 1)
    assert kwargs["end_date"] == date(2026, 6, 30)
    assert kwargs["sort"] == "PRICE"
    assert kwargs["order"] == "ASCENDING"
    # Tour search caches a batch and paginates in-memory, so it always fetches
    # from start=1; the page-2 cold path requests the full batch size (50).
    assert kwargs["start"] == 1
    assert kwargs["count"] == 50
