"""Partner tours share the Viator tour format: age bands + per-band pricing,
the unified availability endpoint, and the create-time ADULT-band requirement.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

BANDS = [
    {"age_band": "ADULT", "start_age": 18, "end_age": 99, "price": 50},
    {"age_band": "CHILD", "start_age": 6, "end_age": 17, "price": 25},
    {"age_band": "INFANT", "start_age": 0, "end_age": 5, "price": 0},
]


# ── Unit: pricing helpers ─────────────────────────────────────────────────────

def test_adult_band_price():
    from app.core.pricing import adult_band_price
    assert adult_band_price(BANDS, 999) == Decimal("50")
    assert adult_band_price([], 30) == Decimal("30")  # no ADULT band → fallback


def test_match_age_band_excludes_adult():
    from app.core.pricing import match_age_band
    assert match_age_band(8, BANDS)["age_band"] == "CHILD"
    assert match_age_band(3, BANDS)["age_band"] == "INFANT"
    # ADULT is the catch-all and is excluded from child matching.
    assert match_age_band(40, BANDS) is None


def test_compute_subtotal_from_bands():
    from app.core.pricing import compute_tour_subtotal_from_bands
    # 2 adults + 1 child(8) = 50 + 50 + 25
    assert compute_tour_subtotal_from_bands(BANDS, 2, [8], 50) == Decimal("125.00")
    # 1 adult + 1 infant(3) = 50 + 0
    assert compute_tour_subtotal_from_bands(BANDS, 1, [3], 50) == Decimal("50.00")


def test_compute_subtotal_band_price_fallback():
    from app.core.pricing import compute_tour_subtotal_from_bands
    bands = [
        {"age_band": "ADULT", "start_age": 18, "end_age": 99, "price": 40},
        {"age_band": "CHILD", "start_age": 2, "end_age": 17},  # no explicit price
    ]
    # child band without price falls back to the tour base price
    assert compute_tour_subtotal_from_bands(bands, 1, [10], 40) == Decimal("80.00")


def test_compute_subtotal_age_outside_bands_raises():
    from app.core.pricing import compute_tour_subtotal_from_bands, AgeBandError
    adult_only = [{"age_band": "ADULT", "start_age": 18, "end_age": 99, "price": 50}]
    with pytest.raises(AgeBandError):
        compute_tour_subtotal_from_bands(adult_only, 1, [8], 50)


# ── API: create ──────────────────────────────────────────────────────────────

def _payload(**over):
    base = {
        "name": "Partner Age-Band Tour",
        "city": "Hanoi",
        "country": "Vietnam",
        "category": "cultural",
        "duration_days": 1,
        "max_participants": 10,
        "price_per_person": 50,
        "age_bands": [dict(b) for b in BANDS],
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_partner_create_tour_with_age_bands(client: AsyncClient, partner_token):
    res = await client.post("/api/v1/tours", json=_payload(), headers=auth_header(partner_token))
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["source"] == "local"
    assert data["slug"]  # auto-generated from name
    assert data["price_per_person"] == 50  # synced to ADULT band
    bands = {b["age_band"]: b for b in data["age_bands"]}
    assert bands["CHILD"]["price"] == 25
    assert bands["INFANT"]["price"] == 0


@pytest.mark.asyncio
async def test_create_tour_without_age_bands_rejected(client: AsyncClient, partner_token):
    payload = _payload()
    del payload["age_bands"]
    res = await client.post("/api/v1/tours", json=payload, headers=auth_header(partner_token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_tour_without_adult_band_rejected(client: AsyncClient, partner_token):
    payload = _payload(age_bands=[{"age_band": "CHILD", "start_age": 6, "end_age": 17, "price": 25}])
    res = await client.post("/api/v1/tours", json=payload, headers=auth_header(partner_token))
    assert res.status_code == 422


# ── API: availability (same shape as Viator endpoint) ─────────────────────────

@pytest.mark.asyncio
async def test_partner_tour_availability_prices_by_band(client: AsyncClient, partner_token):
    created = await client.post("/api/v1/tours", json=_payload(), headers=auth_header(partner_token))
    tour_id = created.json()["id"]
    # 2 adults + child(8) → subtotal 125 over 3 travelers ⇒ 41.67 per person.
    res = await client.get(
        f"/api/v1/tours/{tour_id}/availability",
        params={"tour_date": "2026-07-01", "adults": 2, "child_ages": "8"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is True
    assert body["currency"] == "USD"
    assert round(body["price"], 2) == round(125 / 3, 2)


@pytest.mark.asyncio
async def test_partner_tour_availability_age_out_of_band(client: AsyncClient, partner_token):
    created = await client.post(
        "/api/v1/tours",
        json=_payload(age_bands=[{"age_band": "ADULT", "start_age": 18, "end_age": 99, "price": 50}]),
        headers=auth_header(partner_token),
    )
    tour_id = created.json()["id"]
    res = await client.get(
        f"/api/v1/tours/{tour_id}/availability",
        params={"tour_date": "2026-07-01", "adults": 1, "child_ages": "8"},
    )
    assert res.status_code == 400
