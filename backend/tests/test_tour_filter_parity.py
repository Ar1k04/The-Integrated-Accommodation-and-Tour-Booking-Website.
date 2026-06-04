"""The Tours-page filters (tour type / features / duration) must narrow BOTH
Partner (DB) and Viator products. These tests create Partner tours and assert
each filter surfaces or hides them correctly, with Viator search mocked empty
so only the Partner rows are under test.
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.services import viator_service
from tests.conftest import auth_header

ADULT = {"age_band": "ADULT", "start_age": 18, "end_age": 99, "price": 50}


def _payload(**over):
    base = {
        "name": "Partner Hanoi Walking Tour",
        "city": "Hanoi",
        "country": "Vietnam",
        "category": "Walking Tours",
        "duration_days": 1,
        "duration_minutes": 180,
        "max_participants": 10,
        "price_per_person": 50,
        "flags": ["FREE_CANCELLATION"],
        "age_bands": [dict(ADULT)],
    }
    base.update(over)
    return base


async def _create(client, token, **over):
    res = await client.post("/api/v1/tours", json=_payload(**over), headers=auth_header(token))
    assert res.status_code == 201, res.text
    return res.json()


def _names(resp):
    return [i["name"] for i in resp.json()["items"]]


_EMPTY_VIATOR = {"products": [], "total": 0}


@pytest.mark.asyncio
async def test_partner_tour_create_round_trips_new_fields(client: AsyncClient, partner_token):
    data = await _create(client, partner_token)
    assert data["duration_minutes"] == 180
    assert data["flags"] == ["FREE_CANCELLATION"]


@pytest.mark.asyncio
async def test_create_rejects_non_partner_flag(client: AsyncClient, partner_token):
    res = await client.post(
        "/api/v1/tours",
        json=_payload(flags=["NEW_ON_VIATOR"]),
        headers=auth_header(partner_token),
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_tour_type_filter_matches_and_excludes_partner(client: AsyncClient, partner_token):
    await _create(client, partner_token)
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=_EMPTY_VIATOR)):
        # tag 12046 == "Walking Tours" → partner surfaces.
        match = await client.get("/api/v1/tours?city=Hanoi&tags=12046")
        # tag 21701 == "Cruises & Sailing" → partner excluded.
        miss = await client.get("/api/v1/tours?city=Hanoi&tags=21701")
    assert "Partner Hanoi Walking Tour" in _names(match)
    assert "Partner Hanoi Walking Tour" not in _names(miss)


@pytest.mark.asyncio
async def test_niche_tag_with_no_partner_equivalent_excludes_partner(client: AsyncClient, partner_token):
    await _create(client, partner_token)
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=_EMPTY_VIATOR)):
        resp = await client.get("/api/v1/tours?city=Hanoi&tags=99999")
    assert "Partner Hanoi Walking Tour" not in _names(resp)


@pytest.mark.asyncio
async def test_features_filter_matches_and_excludes_partner(client: AsyncClient, partner_token):
    await _create(client, partner_token, flags=["FREE_CANCELLATION"])
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=_EMPTY_VIATOR)):
        match = await client.get("/api/v1/tours?city=Hanoi&flags=FREE_CANCELLATION")
        miss = await client.get("/api/v1/tours?city=Hanoi&flags=SKIP_THE_LINE")
    assert "Partner Hanoi Walking Tour" in _names(match)
    assert "Partner Hanoi Walking Tour" not in _names(miss)


@pytest.mark.asyncio
async def test_duration_filter_matches_and_excludes_partner(client: AsyncClient, partner_token):
    await _create(client, partner_token, duration_minutes=180)  # 3h → 1–4h bucket
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=_EMPTY_VIATOR)):
        match = await client.get("/api/v1/tours?city=Hanoi&duration_min=60&duration_max=240")
        miss = await client.get("/api/v1/tours?city=Hanoi&duration_min=480")
    assert "Partner Hanoi Walking Tour" in _names(match)
    assert "Partner Hanoi Walking Tour" not in _names(miss)


@pytest.mark.asyncio
async def test_date_filter_keeps_partner_tours(client: AsyncClient, partner_token):
    """Travel-date range narrows Viator but never hides capacity-based Partner
    tours, which are bookable on any future date."""
    await _create(client, partner_token)
    with patch.object(viator_service, "search_tours", new=AsyncMock(return_value=_EMPTY_VIATOR)):
        resp = await client.get(
            "/api/v1/tours?city=Hanoi&start_date=2026-07-01&end_date=2026-07-31"
        )
    assert "Partner Hanoi Walking Tour" in _names(resp)
