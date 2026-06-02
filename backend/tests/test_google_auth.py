"""Login with Google (OAuth ID-token flow).

The ID token is verified server-side; we monkeypatch the Google verifier so the
tests never hit the network. Covers: create-new, auto-link to an existing email,
returning Google user, and the guard that blocks password login on a
Google-only account.
"""
import uuid

import pytest
from sqlalchemy import select

from app.core import config
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import (
    authenticate_google,
    authenticate_user,
    register_user,
)
from app.schemas.user import UserCreate


def _patch_google(monkeypatch, claims: dict):
    """Force settings.GOOGLE_CLIENT_ID and stub the Google profile fetch → claims."""
    monkeypatch.setattr(config.settings, "GOOGLE_CLIENT_ID", "test-client-id", raising=False)

    async def _fake_verify(access_token):
        if access_token == "BAD":
            raise ValueError("Invalid Google token")
        return claims

    monkeypatch.setattr(auth_service, "_verify_google_access_token", _fake_verify)


@pytest.mark.asyncio
async def test_google_creates_new_user(db_session, monkeypatch):
    email = f"gnew-{uuid.uuid4().hex[:8]}@example.com"
    _patch_google(monkeypatch, {
        "sub": f"sub-{uuid.uuid4().hex}",
        "email": email,
        "email_verified": True,
        "name": "Google Newbie",
        "picture": "https://example.com/a.png",
    })

    user, created = await authenticate_google(db_session, "TOKEN")
    assert created is True
    assert user.email == email
    assert user.role == "user"
    assert user.google_id is not None
    assert user.hashed_password is None
    assert user.avatar_url == "https://example.com/a.png"


@pytest.mark.asyncio
async def test_google_links_existing_email(db_session, monkeypatch):
    email = f"glink-{uuid.uuid4().hex[:8]}@example.com"
    existing = await register_user(
        db_session, UserCreate(email=email, password="Password1!", full_name="Existing")
    )
    assert existing.google_id is None

    _patch_google(monkeypatch, {
        "sub": "sub-link-123",
        "email": email,
        "email_verified": True,
        "name": "Existing",
    })

    user, created = await authenticate_google(db_session, "TOKEN")
    assert created is False
    assert user.id == existing.id
    assert user.google_id == "sub-link-123"


@pytest.mark.asyncio
async def test_google_returning_user_resolves_by_sub(db_session, monkeypatch):
    email = f"gret-{uuid.uuid4().hex[:8]}@example.com"
    claims = {"sub": "sub-ret-9", "email": email, "email_verified": True, "name": "Ret"}
    _patch_google(monkeypatch, claims)

    user1, created1 = await authenticate_google(db_session, "TOKEN")
    user2, created2 = await authenticate_google(db_session, "TOKEN")
    assert created1 is True and created2 is False
    assert user1.id == user2.id


@pytest.mark.asyncio
async def test_google_partner_starts_pending(db_session, monkeypatch):
    email = f"gpartner-{uuid.uuid4().hex[:8]}@example.com"
    _patch_google(monkeypatch, {
        "sub": f"sub-{uuid.uuid4().hex}", "email": email, "email_verified": True, "name": "P",
    })
    user, created = await authenticate_google(db_session, "TOKEN", requested_role="partner")
    assert created is True
    assert user.role == "partner"
    assert user.partner_status == "pending"


@pytest.mark.asyncio
async def test_google_rejects_unverified_email(db_session, monkeypatch):
    _patch_google(monkeypatch, {
        "sub": "s", "email": "x@example.com", "email_verified": False, "name": "X",
    })
    with pytest.raises(ValueError, match="not verified"):
        await authenticate_google(db_session, "TOKEN")


@pytest.mark.asyncio
async def test_google_rejects_bad_token(db_session, monkeypatch):
    _patch_google(monkeypatch, {})
    with pytest.raises(ValueError, match="Invalid Google token"):
        await authenticate_google(db_session, "BAD")


@pytest.mark.asyncio
async def test_password_login_blocked_for_google_only_account(db_session, monkeypatch):
    email = f"gonly-{uuid.uuid4().hex[:8]}@example.com"
    _patch_google(monkeypatch, {
        "sub": f"sub-{uuid.uuid4().hex}", "email": email, "email_verified": True, "name": "G",
    })
    await authenticate_google(db_session, "TOKEN")

    with pytest.raises(ValueError, match="Google sign-in"):
        await authenticate_user(db_session, email, "whatever")
