"""Admin loyalty-tier CRUD (UC_A_TIERS)."""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_tier_crud_as_admin(client: AsyncClient, admin_token):
    # Create
    res = await client.post(
        "/api/v1/admin/loyalty-tiers",
        json={"name": f"Gold-{uuid.uuid4().hex[:6]}", "min_points": 1000, "max_points": 4999, "discount_percent": 5},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 201
    tier = res.json()
    assert tier["discount_percent"] == 5

    # List (ordered by min_points)
    res = await client.get("/api/v1/admin/loyalty-tiers", headers=auth_header(admin_token))
    assert res.status_code == 200
    assert any(t["id"] == tier["id"] for t in res.json())

    # Update
    res = await client.patch(
        f"/api/v1/admin/loyalty-tiers/{tier['id']}",
        json={"discount_percent": 8}, headers=auth_header(admin_token),
    )
    assert res.status_code == 200
    assert res.json()["discount_percent"] == 8

    # Delete
    res = await client.delete(f"/api/v1/admin/loyalty-tiers/{tier['id']}", headers=auth_header(admin_token))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_tier_duplicate_name_409(client: AsyncClient, admin_token):
    name = f"Plat-{uuid.uuid4().hex[:6]}"
    r1 = await client.post("/api/v1/admin/loyalty-tiers", json={"name": name, "min_points": 5000}, headers=auth_header(admin_token))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/admin/loyalty-tiers", json={"name": name, "min_points": 6000}, headers=auth_header(admin_token))
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_tier_forbidden_for_non_admin(client: AsyncClient, user_token, partner_token):
    body = {"name": "Hacker", "min_points": 0}
    assert (await client.post("/api/v1/admin/loyalty-tiers", json=body, headers=auth_header(user_token))).status_code == 403
    assert (await client.post("/api/v1/admin/loyalty-tiers", json=body, headers=auth_header(partner_token))).status_code == 403


@pytest.mark.asyncio
async def test_validation_rejects_bad_discount(client: AsyncClient, admin_token):
    res = await client.post(
        "/api/v1/admin/loyalty-tiers",
        json={"name": "BadPct", "min_points": 0, "discount_percent": 150},
        headers=auth_header(admin_token),
    )
    assert res.status_code == 422
