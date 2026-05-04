"""Regression tests for partner role scoping.

Partners can:
- Create hotels (owned by them)
- Manage their own hotels (PUT/PATCH/DELETE)
- NOT manage hotels owned by others (403)
- Access /admin/stats, /admin/bookings (staff-level endpoints)

Admins can:
- Manage any hotel regardless of ownership
- Access /admin/users (admin-only endpoint)
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_partner_can_create_hotel(client: AsyncClient, partner_user, partner_token):
    res = await client.post(
        "/api/v1/hotels",
        json={
            "name": "Partner Test Hotel",
            "city": "Hanoi",
            "country": "Vietnam",
            "star_rating": 3,
            "base_price": 50,
        },
        headers=auth_header(partner_token),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Partner Test Hotel"
    assert str(data["owner_id"]) == str(partner_user.id)


@pytest.mark.asyncio
async def test_partner_cannot_edit_other_hotel(client: AsyncClient, partner_token, admin_user):
    """Partner cannot PATCH a hotel owned by someone else."""
    from sqlalchemy import select
    # Create a hotel owned by admin_user, bypass API by checking admin can create
    # then try to patch as partner
    admin_res = await client.post(
        "/api/v1/hotels",
        json={"name": "Admin Hotel", "city": "HCMC", "country": "Vietnam",
              "star_rating": 4, "base_price": 100},
        headers=auth_header(
            __import__("app.core.security", fromlist=["create_access_token"]).create_access_token(
                admin_user.id, extra={"role": admin_user.role}
            )
        ),
    )
    assert admin_res.status_code == 201
    hotel_id = admin_res.json()["id"]

    res = await client.patch(
        f"/api/v1/hotels/{hotel_id}",
        json={"name": "Hacked Hotel Name"},
        headers=auth_header(partner_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_edit_any_hotel(client: AsyncClient, partner_user, partner_token, admin_user):
    """Full admin can edit hotels owned by partners."""
    from app.core.security import create_access_token
    admin_token = create_access_token(admin_user.id, extra={"role": admin_user.role})

    # Partner creates a hotel
    create_res = await client.post(
        "/api/v1/hotels",
        json={"name": "Partner Hotel", "city": "Danang", "country": "Vietnam",
              "star_rating": 3, "base_price": 70},
        headers=auth_header(partner_token),
    )
    assert create_res.status_code == 201
    hotel_id = create_res.json()["id"]

    # Admin patches it
    patch_res = await client.patch(
        f"/api/v1/hotels/{hotel_id}",
        json={"name": "Admin Updated Hotel"},
        headers=auth_header(admin_token),
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Admin Updated Hotel"


@pytest.mark.asyncio
async def test_partner_can_access_staff_stats(client: AsyncClient, partner_token):
    """Partner can reach /admin/stats (staff endpoint)."""
    res = await client.get("/api/v1/admin/stats", headers=auth_header(partner_token))
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_partner_cannot_access_admin_users(client: AsyncClient, partner_token):
    """Partner cannot access /admin/users (admin-only endpoint)."""
    res = await client.get("/api/v1/admin/users", headers=auth_header(partner_token))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_users(client: AsyncClient, admin_user):
    """Full admin can access /admin/users."""
    from app.core.security import create_access_token
    admin_token = create_access_token(admin_user.id, extra={"role": admin_user.role})
    res = await client.get("/api/v1/admin/users", headers=auth_header(admin_token))
    assert res.status_code == 200
