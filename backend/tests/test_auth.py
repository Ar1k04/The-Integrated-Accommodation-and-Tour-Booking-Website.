"""Tests for the auth flow: register, login, me, token refresh."""
import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "StrongPass1!",
        "full_name": "New User",
    })
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate(client: AsyncClient, test_user):
    res = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "StrongPass1!",
        "full_name": "Dup User",
    })
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    res = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "TestPassword1!",
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    res = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword!",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, test_user, user_token):
    res = await client.get("/api/v1/auth/me", headers=auth_header(user_token))
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    res = await client.get("/api/v1/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_update_me(client: AsyncClient, test_user, user_token):
    res = await client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Updated Name"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 200
    assert res.json()["full_name"] == "Updated Name"


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_user, user_token):
    res = await client.post("/api/v1/auth/logout", headers=auth_header(user_token))
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_user_preferences_defaults(client: AsyncClient, test_user, user_token):
    res = await client.get("/api/v1/auth/me", headers=auth_header(user_token))
    assert res.status_code == 200
    data = res.json()
    assert data["preferred_locale"] == "en"
    assert data["preferred_currency"] == "USD"


@pytest.mark.asyncio
async def test_update_preferences(client: AsyncClient, test_user, user_token):
    res = await client.patch(
        "/api/v1/auth/me",
        json={"preferred_locale": "vi", "preferred_currency": "VND"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["preferred_locale"] == "vi"
    assert data["preferred_currency"] == "VND"


@pytest.mark.asyncio
async def test_invalid_locale_rejected(client: AsyncClient, test_user, user_token):
    res = await client.patch(
        "/api/v1/auth/me",
        json={"preferred_locale": "fr"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 422
