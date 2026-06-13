"""Partner approval workflow (UC_A_PARTNERS).

A partner registers as ``pending`` and is blocked from every staff endpoint
(require_staff) until an admin approves. Admin can list/approve/reject.
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


async def _register_partner(client: AsyncClient, email: str) -> dict:
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Partner123!", "full_name": "New Partner", "role": "partner"},
    )
    assert res.status_code == 201, res.text
    return res.json()  # {access_token}


@pytest.mark.asyncio
async def test_new_partner_starts_pending_and_is_blocked(client: AsyncClient, db_session):
    email = f"pending-{uuid.uuid4().hex[:8]}@example.com"
    token = (await _register_partner(client, email))["access_token"]

    # /auth/me exposes partner_status = pending
    me = await client.get("/api/v1/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["partner_status"] == "pending"

    # A staff-only action is blocked (require_staff → 403).
    res = await client.post(
        "/api/v1/hotels",
        json={"name": "X", "city": "Hanoi", "country": "Vietnam", "base_price": 100},
        headers=auth_header(token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_approves_then_partner_can_act(client: AsyncClient, admin_token):
    email = f"approve-{uuid.uuid4().hex[:8]}@example.com"
    token = (await _register_partner(client, email))["access_token"]
    me = (await client.get("/api/v1/auth/me", headers=auth_header(token))).json()
    pid = me["id"]

    # Appears in the pending queue.
    q = await client.get("/api/v1/admin/partners?status=pending", headers=auth_header(admin_token))
    assert q.status_code == 200
    assert any(u["id"] == pid for u in q.json()["items"])

    # Approve.
    upd = await client.patch(
        f"/api/v1/admin/partners/{pid}", json={"partner_status": "approved"}, headers=auth_header(admin_token)
    )
    assert upd.status_code == 200
    assert upd.json()["partner_status"] == "approved"

    # Now the staff action succeeds.
    res = await client.post(
        "/api/v1/hotels",
        json={"name": "Approved Hotel", "city": "Hanoi", "country": "Vietnam", "base_price": 120},
        headers=auth_header(token),
    )
    assert res.status_code in (200, 201), res.text


@pytest.mark.asyncio
async def test_admin_can_reject(client: AsyncClient, admin_token):
    email = f"reject-{uuid.uuid4().hex[:8]}@example.com"
    token = (await _register_partner(client, email))["access_token"]
    pid = (await client.get("/api/v1/auth/me", headers=auth_header(token))).json()["id"]

    upd = await client.patch(
        f"/api/v1/admin/partners/{pid}", json={"partner_status": "rejected"}, headers=auth_header(admin_token)
    )
    assert upd.status_code == 200
    # Still blocked after rejection.
    res = await client.post(
        "/api/v1/hotels",
        json={"name": "Y", "city": "Hanoi", "country": "Vietnam", "base_price": 100},
        headers=auth_header(token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_partners_endpoint_is_admin_only(client: AsyncClient, user_token, partner_token):
    assert (await client.get("/api/v1/admin/partners", headers=auth_header(user_token))).status_code == 403
    assert (await client.get("/api/v1/admin/partners", headers=auth_header(partner_token))).status_code == 403


# ── Email-confirmation self-approval ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_partner_confirm_link_approves(client: AsyncClient):
    """Clicking the email confirmation link flips pending → approved without admin."""
    from app.services.auth_service import create_partner_confirm_token

    email = f"confirm-{uuid.uuid4().hex[:8]}@example.com"
    token = (await _register_partner(client, email))["access_token"]
    me = (await client.get("/api/v1/auth/me", headers=auth_header(token))).json()
    assert me["partner_status"] == "pending"

    confirm_token = create_partner_confirm_token(uuid.UUID(me["id"]))
    res = await client.post("/api/v1/auth/partner/confirm", json={"token": confirm_token})
    assert res.status_code == 200, res.text

    me2 = (await client.get("/api/v1/auth/me", headers=auth_header(token))).json()
    assert me2["partner_status"] == "approved"

    # And the previously-blocked staff action now succeeds.
    act = await client.post(
        "/api/v1/hotels",
        json={"name": "Confirmed Hotel", "city": "Hanoi", "country": "Vietnam", "base_price": 110},
        headers=auth_header(token),
    )
    assert act.status_code in (200, 201), act.text


@pytest.mark.asyncio
async def test_partner_confirm_rejects_bad_token(client: AsyncClient):
    res = await client.post("/api/v1/auth/partner/confirm", json={"token": "not-a-jwt"})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_partner_confirm_wrong_token_type_rejected(client: AsyncClient):
    """A password-reset token must not double as a partner-confirm token."""
    from app.models.user import User
    from app.services.auth_service import create_password_reset_token

    email = f"wrongtype-{uuid.uuid4().hex[:8]}@example.com"
    token = (await _register_partner(client, email))["access_token"]
    uid = (await client.get("/api/v1/auth/me", headers=auth_header(token))).json()["id"]

    reset_token = create_password_reset_token(
        User(id=uuid.UUID(uid), email=email, hashed_password=None)
    )
    res = await client.post("/api/v1/auth/partner/confirm", json={"token": reset_token})
    assert res.status_code == 400
