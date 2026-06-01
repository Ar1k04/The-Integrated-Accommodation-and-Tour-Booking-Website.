"""Route tests cho /admin (cần DB test).

Trọng tâm: phân quyền — /stats & /bookings cho StaffUser (partner|admin),
/users cho AdminUser (chỉ admin). Test IDs: UT-BE-ADMIN-01..NN.
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


# ── /admin/stats (StaffUser: partner hoặc admin) ─────────────────────────────
@pytest.mark.asyncio
async def test_stats_unauthenticated_401(client: AsyncClient):
    res = await client.get("/api/v1/admin/stats")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_stats_forbidden_for_regular_user(client: AsyncClient, user_token):
    res = await client.get("/api/v1/admin/stats", headers=auth_header(user_token))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_stats_allowed_for_partner(client: AsyncClient, partner_token):
    res = await client.get("/api/v1/admin/stats", headers=auth_header(partner_token))
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_stats_allowed_for_admin(client: AsyncClient, admin_token):
    res = await client.get("/api/v1/admin/stats", headers=auth_header(admin_token))
    assert res.status_code == 200


# ── /admin/users (AdminUser: chỉ admin) ──────────────────────────────────────
@pytest.mark.asyncio
async def test_users_list_admin_only(client: AsyncClient, user_token, partner_token, admin_token):
    assert (await client.get("/api/v1/admin/users", headers=auth_header(user_token))).status_code == 403
    assert (await client.get("/api/v1/admin/users", headers=auth_header(partner_token))).status_code == 403
    ok = await client.get("/api/v1/admin/users", headers=auth_header(admin_token))
    assert ok.status_code == 200
    assert "items" in ok.json()


@pytest.mark.asyncio
async def test_get_user_by_id_admin(client: AsyncClient, admin_token, test_user):
    res = await client.get(f"/api/v1/admin/users/{test_user.id}", headers=auth_header(admin_token))
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, admin_token):
    res = await client.get(f"/api/v1/admin/users/{uuid.uuid4()}", headers=auth_header(admin_token))
    assert res.status_code == 404


# ── /admin/bookings (StaffUser) ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_bookings_list_requires_staff(client: AsyncClient, user_token, admin_token):
    assert (await client.get("/api/v1/admin/bookings", headers=auth_header(user_token))).status_code == 403
    assert (await client.get("/api/v1/admin/bookings", headers=auth_header(admin_token))).status_code == 200
