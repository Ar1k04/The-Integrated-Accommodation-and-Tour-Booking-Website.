"""Authorization-hardening tests for the LOGIC_AUDIT fixes.

Covers:
- AUTHZ-01: PATCH /auth/me must not accept role/is_active (privilege escalation).
- AUTHZ-02: PATCH /bookings/{id} must not accept status.
- AUTHZ-03: a partner may only read payments for bookings containing their own
  local hotel/tour items.
- AUTHZ-04: /admin/stats is scoped to the partner's own listings.
"""
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.hotel import Hotel
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.room import Room
from app.models.user import User
from tests.conftest import auth_header


async def _make_partner(db, email):
    from app.core.security import hash_password
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("PartnerPass1!"),
        full_name="Partner", role="partner", is_active=True,
        partner_status="approved", loyalty_points=0,
    )
    db.add(u)
    await db.flush()
    await db.refresh(u)
    return u, create_access_token(u.id, extra={"role": "partner"})


async def _owned_room(db, owner_id, *, city="Hanoi", price=200):
    hotel = Hotel(
        id=uuid.uuid4(), name=f"H-{uuid.uuid4().hex[:6]}", slug=f"h-{uuid.uuid4().hex[:6]}",
        city=city, country="Vietnam", base_price=price, star_rating=4, owner_id=owner_id,
    )
    db.add(hotel)
    await db.flush()
    room = Room(
        id=uuid.uuid4(), hotel_id=hotel.id, name="Std", room_type="double",
        price_per_night=price, total_quantity=5, max_guests=2,
    )
    db.add(room)
    await db.flush()
    return room


async def _booking_with_room(db, user_id, room, *, amount=200, status=BookingStatus.confirmed.value):
    booking = Booking(id=uuid.uuid4(), user_id=user_id, total_price=Decimal(amount), status=status)
    db.add(booking)
    await db.flush()
    item = BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type=BookingItemType.room.value,
        room_id=room.id, unit_price=Decimal(amount), subtotal=Decimal(amount), quantity=1,
        status=BookingItemStatus.confirmed.value,
    )
    db.add(item)
    payment = Payment(
        id=uuid.uuid4(), booking_id=booking.id, provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_{uuid.uuid4().hex[:12]}", amount=Decimal(amount),
        currency="usd", status=PaymentStatus.succeeded.value,
    )
    db.add(payment)
    await db.flush()
    return booking, payment


# ── AUTHZ-01 ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_self_profile_update_rejects_role(client: AsyncClient, user_token, test_user):
    res = await client.patch("/api/v1/auth/me", json={"role": "admin"}, headers=auth_header(user_token))
    assert res.status_code == 422  # extra='forbid' on SelfProfileUpdate
    assert test_user.role == "user"


@pytest.mark.asyncio
async def test_self_profile_update_rejects_is_active(client: AsyncClient, user_token):
    res = await client.patch("/api/v1/auth/me", json={"is_active": True}, headers=auth_header(user_token))
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_self_profile_update_allows_safe_fields(client: AsyncClient, user_token):
    res = await client.patch("/api/v1/auth/me", json={"full_name": "Renamed"}, headers=auth_header(user_token))
    assert res.status_code == 200
    assert res.json()["full_name"] == "Renamed"


# ── AUTHZ-02 ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_booking_update_rejects_status(client: AsyncClient, db_session, test_user, user_token):
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("100"), status=BookingStatus.pending.value)
    db_session.add(booking)
    await db_session.flush()
    res = await client.patch(
        f"/api/v1/bookings/{booking.id}", json={"status": "completed"}, headers=auth_header(user_token)
    )
    assert res.status_code == 422
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.pending.value


@pytest.mark.asyncio
async def test_booking_update_allows_special_requests(client: AsyncClient, db_session, test_user, user_token):
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("100"), status=BookingStatus.pending.value)
    db_session.add(booking)
    await db_session.flush()
    res = await client.patch(
        f"/api/v1/bookings/{booking.id}", json={"special_requests": "Late check-in"}, headers=auth_header(user_token)
    )
    assert res.status_code == 200


# ── AUTHZ-03 ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_partner_cannot_read_other_partner_payment(client: AsyncClient, db_session, test_user, user_token):
    partner_a, token_a = await _make_partner(db_session, "pa@example.com")
    partner_b, token_b = await _make_partner(db_session, "pb@example.com")
    room = await _owned_room(db_session, partner_a.id)
    booking, payment = await _booking_with_room(db_session, test_user.id, room)

    # Owner partner A can read it.
    r_a = await client.get(f"/api/v1/payments/{payment.id}", headers=auth_header(token_a))
    assert r_a.status_code == 200
    # Unrelated partner B cannot.
    r_b = await client.get(f"/api/v1/payments/{payment.id}", headers=auth_header(token_b))
    assert r_b.status_code == 404
    # The booking's own customer can.
    r_u = await client.get(f"/api/v1/payments/{payment.id}", headers=auth_header(user_token))
    assert r_u.status_code == 200


# ── AUTHZ-04 ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_admin_stats_scoped_to_partner(client: AsyncClient, db_session, test_user, admin_token):
    partner_a, token_a = await _make_partner(db_session, "pa-stats@example.com")
    room_a = await _owned_room(db_session, partner_a.id, price=200)
    await _booking_with_room(db_session, test_user.id, room_a, amount=200)

    # An unrelated booking/payment NOT owned by partner A ($500).
    other_partner, _ = await _make_partner(db_session, "other@example.com")
    room_o = await _owned_room(db_session, other_partner.id, price=500)
    await _booking_with_room(db_session, test_user.id, room_o, amount=500)

    # Partner A sees only their own $200; user growth hidden.
    r_a = await client.get("/api/v1/admin/stats", headers=auth_header(token_a))
    assert r_a.status_code == 200
    data_a = r_a.json()["data"]
    assert data_a["total_revenue"] == 200
    assert data_a["new_users"] == 0

    # Admin sees the platform-wide total ($700).
    r_admin = await client.get("/api/v1/admin/stats", headers=auth_header(admin_token))
    assert r_admin.json()["data"]["total_revenue"] == 700
