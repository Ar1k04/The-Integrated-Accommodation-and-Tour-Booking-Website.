"""Partner-write lock checks — partner cannot delete a room/tour or shrink a
room's capacity while a guest is mid-checkout (Sprint 11 follow-up).

Covers:
  - DELETE /rooms/{id} blocked / allowed
  - PATCH /rooms/{id} capacity decrease blocked / increase allowed / name-only allowed
  - DELETE /tours/{id} blocked
  - DELETE /hotels/{id} cascade: one locked room blocks the whole hotel
  - Redis-down lax (proceeds) vs strict (503)
  - End-to-end against a real lock written by lock_service.acquire
"""
import logging
import uuid
from datetime import date

import pytest
from httpx import AsyncClient

from app.services import lock_service
from tests.conftest import auth_header


# ── shared fake-redis with SCAN support ───────────────────────────────────────

class StatefulFakeRedis:
    """In-memory Redis stand-in covering SET NX EX / GET / EVAL CAS / EXPIRE /
    DELETE / SCAN. Sufficient for the partner-lock tests below."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def eval(self, script, numkeys, key, value):
        if self.store.get(key) == value:
            del self.store[key]
            return 1
        return 0

    async def expire(self, key, ttl):
        return key in self.store

    async def delete(self, key):
        self.store.pop(key, None)
        return 1

    async def scan(self, cursor=0, match=None, count=100):
        """Return (next_cursor, matching_keys). Single-pass for simplicity."""
        import fnmatch
        keys = [k for k in self.store if fnmatch.fnmatch(k, match)] if match else list(self.store)
        return 0, keys


# ── helpers ───────────────────────────────────────────────────────────────────

async def _make_partner_hotel(db_session, partner_user):
    """Create a partner-owned hotel directly via the ORM (skips POST plumbing)."""
    from app.models.hotel import Hotel
    hotel = Hotel(
        id=uuid.uuid4(), name="P Hotel", slug=f"p-hotel-{uuid.uuid4().hex[:6]}",
        city="Hanoi", country="VN", base_price=100, star_rating=4,
        owner_id=partner_user.id,
    )
    db_session.add(hotel)
    await db_session.flush()
    return hotel


async def _make_room(db_session, hotel, total_quantity=3, name="Standard"):
    from app.models.room import Room
    room = Room(
        id=uuid.uuid4(), hotel_id=hotel.id, name=name, room_type="double",
        price_per_night=120.00, total_quantity=total_quantity, max_guests=2,
    )
    db_session.add(room)
    await db_session.flush()
    return room


async def _make_partner_tour(db_session, partner_user):
    from app.models.tour import Tour
    tour = Tour(
        id=uuid.uuid4(), name="P Tour", slug=f"p-tour-{uuid.uuid4().hex[:6]}",
        city="Hanoi", country="VN", price_per_person=50, duration_days=1,
        max_participants=10, owner_id=partner_user.id,
    )
    db_session.add(tour)
    await db_session.flush()
    return tour


def _set_scan_match(mock_redis, matching_keys: list[str]):
    """Configure the conftest AsyncMock so `scan(...)` returns the given keys once
    then terminates the cursor."""
    async def _scan(cursor=0, match=None, count=100):
        return 0, list(matching_keys)
    mock_redis.scan.side_effect = _scan


# ── Room DELETE ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_room_blocked_by_active_lock(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel)
    _set_scan_match(app.state.redis, [f"checkout:lock:room:{room.id}:2026-06-01"])

    res = await client.delete(f"/api/v1/rooms/{room.id}", headers=auth_header(partner_token))
    assert res.status_code == 409
    assert "active checkout" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_room_allowed_when_no_lock(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel)
    _set_scan_match(app.state.redis, [])

    res = await client.delete(f"/api/v1/rooms/{room.id}", headers=auth_header(partner_token))
    assert res.status_code == 204


# ── Room PATCH ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_room_capacity_decrease_blocked(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel, total_quantity=3)
    _set_scan_match(app.state.redis, [f"checkout:lock:room:{room.id}:2026-06-01"])

    res = await client.patch(
        f"/api/v1/rooms/{room.id}",
        json={"total_quantity": 1},
        headers=auth_header(partner_token),
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_patch_room_capacity_increase_allowed_with_active_lock(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    """A guest holding a lock should not block growing the inventory pool."""
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel, total_quantity=3)
    _set_scan_match(app.state.redis, [f"checkout:lock:room:{room.id}:2026-06-01"])

    res = await client.patch(
        f"/api/v1/rooms/{room.id}",
        json={"total_quantity": 5},
        headers=auth_header(partner_token),
    )
    assert res.status_code == 200
    assert res.json()["total_quantity"] == 5


@pytest.mark.asyncio
async def test_patch_room_non_capacity_field_allowed_with_active_lock(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    """Cosmetic edits (e.g. name) should never trigger the lock check."""
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel, name="Standard")
    _set_scan_match(app.state.redis, [f"checkout:lock:room:{room.id}:2026-06-01"])

    res = await client.patch(
        f"/api/v1/rooms/{room.id}",
        json={"name": "Renamed Standard"},
        headers=auth_header(partner_token),
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Renamed Standard"


# ── Tour DELETE ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_tour_blocked_by_active_lock(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    from app.main import app
    tour = await _make_partner_tour(db_session, partner_user)
    _set_scan_match(app.state.redis, [f"checkout:lock:tour:{tour.id}:2026-06-01"])

    res = await client.delete(f"/api/v1/tours/{tour.id}", headers=auth_header(partner_token))
    assert res.status_code == 409


# ── Hotel cascade ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_hotel_blocked_when_any_room_locked(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    """One of two rooms under the hotel has an active lock — DELETE must 409."""
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room_a = await _make_room(db_session, hotel, name="A")
    room_b = await _make_room(db_session, hotel, name="B")

    locked_keys = [f"checkout:lock:room:{room_a.id}:2026-06-01"]

    async def _scan(cursor=0, match=None, count=100):
        # Only the SCAN over room_a's pattern returns a hit.
        return 0, [k for k in locked_keys if match and k.startswith(match[:-1])]

    app.state.redis.scan.side_effect = _scan

    res = await client.delete(f"/api/v1/hotels/{hotel.id}", headers=auth_header(partner_token))
    assert res.status_code == 409
    # Sanity: hotel still exists.
    from sqlalchemy import select
    from app.models.hotel import Hotel
    still_there = (
        await db_session.execute(select(Hotel).where(Hotel.id == hotel.id))
    ).scalar_one_or_none()
    assert still_there is not None


@pytest.mark.asyncio
async def test_delete_hotel_allowed_when_no_rooms_locked(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    await _make_room(db_session, hotel, name="A")
    await _make_room(db_session, hotel, name="B")
    _set_scan_match(app.state.redis, [])

    res = await client.delete(f"/api/v1/hotels/{hotel.id}", headers=auth_header(partner_token))
    assert res.status_code == 204


# ── Redis-down behaviour ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partner_delete_proceeds_when_redis_down_in_lax_mode(
    client: AsyncClient, db_session, partner_user, partner_token, caplog,
):
    """Lax mode: SCAN failure is logged at ERROR but the DELETE proceeds."""
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel)
    app.state.redis.scan.side_effect = ConnectionError("Redis down")

    with caplog.at_level(logging.ERROR, logger="app.services.lock_service"):
        res = await client.delete(f"/api/v1/rooms/{room.id}", headers=auth_header(partner_token))

    assert res.status_code == 204
    assert any(
        "metric=lock_service.redis_unavailable_total" in r.message for r in caplog.records
    )


@pytest.mark.asyncio
async def test_partner_delete_returns_503_in_strict_mode(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    """Strict mode: SCAN failure → RedisUnavailableError → 503."""
    from app.core.config import settings
    from app.main import app

    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel)
    app.state.redis.scan.side_effect = ConnectionError("Redis down")

    original = settings.REDIS_LOCK_STRICT
    settings.REDIS_LOCK_STRICT = True
    try:
        res = await client.delete(f"/api/v1/rooms/{room.id}", headers=auth_header(partner_token))
        assert res.status_code == 503
    finally:
        settings.REDIS_LOCK_STRICT = original
        app.state.redis.scan.side_effect = None


# ── End-to-end with a real lock written by lock_service.acquire ───────────────

@pytest.mark.asyncio
async def test_end_to_end_real_lock_blocks_partner_delete(
    client: AsyncClient, db_session, partner_user, partner_token,
):
    """Wire a StatefulFakeRedis into app.state.redis, acquire a real per-day lock
    via lock_service.acquire (as the booking flow does), then confirm partner
    DELETE returns 409. Proves the SCAN helper finds keys set by acquire — no
    hand-mocked scan response."""
    from app.main import app
    hotel = await _make_partner_hotel(db_session, partner_user)
    room = await _make_room(db_session, hotel)

    original_redis = app.state.redis
    fake = StatefulFakeRedis()
    app.state.redis = fake
    try:
        # Real guest-side acquire — same path booking_service uses.
        key = lock_service.room_day_key(room.id, date(2026, 6, 1))
        assert await lock_service.acquire(fake, key, owner="guest-1") is True

        res = await client.delete(f"/api/v1/rooms/{room.id}", headers=auth_header(partner_token))
        assert res.status_code == 409
    finally:
        app.state.redis = original_redis
