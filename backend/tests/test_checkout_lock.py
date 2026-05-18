"""Tests for the Redis soft-lock checkout mechanism (Sprint 10).

Verifies that:
  - acquire() succeeds on first call
  - acquire() succeeds for same owner (re-acquire / idempotent)
  - acquire() raises LockCollisionError for a different owner
  - release() clears the lock via Lua CAS script
  - release_many() is a no-op when list is empty
  - create_booking() raises LockCollisionError on slot collision → route returns 409
  - create_booking() succeeds when Redis is None (graceful degradation)
  - store/release booking locks round-trips correctly
"""
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.services import lock_service
from app.services.lock_service import LockCollisionError


# ── unit tests: lock primitives ───────────────────────────────────────────────

class TestAcquire:
    @pytest.mark.asyncio
    async def test_first_acquire_succeeds(self):
        redis = AsyncMock()
        redis.set.return_value = True  # NX succeeded
        result = await lock_service.acquire(redis, "checkout:lock:room:1", "user-a")
        assert result is True
        redis.set.assert_called_once_with(
            "checkout:lock:room:1", "user-a", nx=True, ex=lock_service.CHECKOUT_LOCK_TTL
        )

    @pytest.mark.asyncio
    async def test_same_owner_reacquire_extends_ttl(self):
        redis = AsyncMock()
        redis.set.return_value = None  # NX failed (key exists)
        redis.get.return_value = "user-a"  # same owner
        result = await lock_service.acquire(redis, "checkout:lock:room:1", "user-a")
        assert result is True
        redis.expire.assert_called_once_with(
            "checkout:lock:room:1", lock_service.CHECKOUT_LOCK_TTL
        )

    @pytest.mark.asyncio
    async def test_different_owner_raises_collision(self):
        redis = AsyncMock()
        redis.set.return_value = None   # NX failed
        redis.get.return_value = "user-b"  # different owner
        with pytest.raises(LockCollisionError):
            await lock_service.acquire(redis, "checkout:lock:room:1", "user-a")

    @pytest.mark.asyncio
    async def test_redis_none_returns_true(self):
        result = await lock_service.acquire(None, "checkout:lock:room:1", "user-a")
        assert result is True

    @pytest.mark.asyncio
    async def test_redis_error_returns_true_gracefully(self):
        redis = AsyncMock()
        redis.set.side_effect = ConnectionError("Redis down")
        result = await lock_service.acquire(redis, "checkout:lock:room:1", "user-a")
        assert result is True  # graceful degradation


class TestRelease:
    @pytest.mark.asyncio
    async def test_release_calls_lua(self):
        redis = AsyncMock()
        redis.eval.return_value = 1
        result = await lock_service.release(redis, "checkout:lock:room:1", "user-a")
        assert result is True
        redis.eval.assert_called_once_with(lock_service._RELEASE_LUA, 1, "checkout:lock:room:1", "user-a")

    @pytest.mark.asyncio
    async def test_release_returns_false_when_owner_mismatch(self):
        redis = AsyncMock()
        redis.eval.return_value = 0  # Lua returned 0 = owner mismatch
        result = await lock_service.release(redis, "checkout:lock:room:1", "user-a")
        assert result is False

    @pytest.mark.asyncio
    async def test_release_many_calls_release_for_each(self):
        redis = AsyncMock()
        redis.eval.return_value = 1
        keys = ["key1", "key2", "key3"]
        await lock_service.release_many(redis, keys, "user-a")
        assert redis.eval.call_count == 3


class TestStoreReleaseLocks:
    @pytest.mark.asyncio
    async def test_store_and_release_round_trip(self):
        redis = AsyncMock()
        booking_id = uuid.uuid4()
        keys = ["checkout:lock:room:abc:2026-06-01:2026-06-03"]

        # Store
        redis.set.return_value = True
        await lock_service.store_booking_locks(redis, booking_id, keys, "user-x")
        stored_payload = json.dumps({"keys": keys, "owner": "user-x"})
        redis.set.assert_called_once_with(
            f"booking:locks:{booking_id}",
            stored_payload,
            ex=lock_service.CHECKOUT_LOCK_TTL,
        )

        # Release
        redis.get.return_value = stored_payload
        redis.eval.return_value = 1
        redis.delete.return_value = 1
        await lock_service.release_booking_locks(redis, booking_id)
        redis.delete.assert_called_once_with(f"booking:locks:{booking_id}")

    @pytest.mark.asyncio
    async def test_release_no_op_when_key_missing(self):
        redis = AsyncMock()
        redis.get.return_value = None
        await lock_service.release_booking_locks(redis, uuid.uuid4())
        redis.eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_skips_when_no_keys(self):
        redis = AsyncMock()
        await lock_service.store_booking_locks(redis, uuid.uuid4(), [], "user-a")
        redis.set.assert_not_called()


# ── integration: create_booking with mock redis ───────────────────────────────

class TestCreateBookingLock:
    @pytest.mark.asyncio
    async def test_lock_collision_raises_error(
        self, db_session, test_user, test_room
    ):
        """When a lock exists for another user, create_booking raises LockCollisionError."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        data = BookingCreate(
            items=[
                RoomItemCreate(
                    item_type="room",
                    room_id=test_room.id,
                    check_in=date.today() + timedelta(days=10),
                    check_out=date.today() + timedelta(days=12),
                    quantity=1,
                    guests_count=1,
                )
            ]
        )

        redis = AsyncMock()
        redis.set.return_value = None   # NX failed — key already exists
        redis.get.return_value = "other-user-id"  # different owner holds it

        with pytest.raises(LockCollisionError):
            await create_booking(db_session, test_user.id, data, redis=redis)

    @pytest.mark.asyncio
    async def test_redis_none_booking_succeeds(self, db_session, test_user, test_room):
        """create_booking works fine when redis=None (degraded mode)."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        data = BookingCreate(
            items=[
                RoomItemCreate(
                    item_type="room",
                    room_id=test_room.id,
                    check_in=date.today() + timedelta(days=20),
                    check_out=date.today() + timedelta(days=22),
                    quantity=1,
                    guests_count=1,
                )
            ]
        )

        booking = await create_booking(db_session, test_user.id, data, redis=None)
        assert booking.id is not None
        assert booking.status == "pending"


# ── API: 409 on collision ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_returns_409_on_lock_collision(client, user_token, test_room):
    """POST /bookings returns 409 when the slot is locked by another session."""
    from app.main import app

    # Simulate another user holding the lock
    app.state.redis.set.return_value = None
    app.state.redis.get.return_value = "other-user-id"

    payload = {
        "items": [
            {
                "item_type": "room",
                "room_id": str(test_room.id),
                "check_in": str(date.today() + timedelta(days=30)),
                "check_out": str(date.today() + timedelta(days=32)),
                "quantity": 1,
                "guests_count": 1,
            }
        ]
    }
    resp = await client.post(
        "/api/v1/bookings",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 409
    assert "slot" in resp.json()["detail"].lower() or "held" in resp.json()["detail"].lower()

    # Reset mock for other tests
    app.state.redis.set.return_value = True
    app.state.redis.get.return_value = None


# ── key builder helpers ───────────────────────────────────────────────────────

def test_room_day_key_format():
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    key = lock_service.room_day_key(rid, date(2026, 6, 1))
    assert key == f"checkout:lock:room:{rid}:2026-06-01"


def test_room_day_keys_sorted_ascending():
    """Per-night keys must be returned in ascending date order to prevent deadlock."""
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    keys = lock_service.room_day_keys(rid, date(2026, 6, 1), date(2026, 6, 4))
    assert keys == [
        f"checkout:lock:room:{rid}:2026-06-01",
        f"checkout:lock:room:{rid}:2026-06-02",
        f"checkout:lock:room:{rid}:2026-06-03",
    ]
    # check_out is exclusive — 3 nights, 3 keys
    assert len(keys) == 3


def test_room_day_keys_empty_for_invalid_range():
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert lock_service.room_day_keys(rid, date(2026, 6, 1), date(2026, 6, 1)) == []
    assert lock_service.room_day_keys(rid, date(2026, 6, 3), date(2026, 6, 1)) == []


def test_tour_key_format():
    tid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    key = lock_service.tour_key(tid, date(2026, 7, 15))
    assert key == f"checkout:lock:tour:{tid}:2026-07-15"


def test_liteapi_key_normalises_room_name():
    key = lock_service.liteapi_key(
        "hotel-123", "  Deluxe King  ", date(2026, 6, 1), date(2026, 6, 3)
    )
    assert key == "checkout:lock:liteapi:hotel-123:deluxe king:2026-06-01:2026-06-03"


# ── stateful fake redis ───────────────────────────────────────────────────────

class StatefulFakeRedis:
    """Minimal in-memory Redis stand-in covering SET NX EX / GET / EVAL CAS /
    EXPIRE / DELETE. Sufficient for the soft-lock tests below."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple] = []

    async def set(self, key, value, nx=False, ex=None):
        self.set_calls.append((key, value, nx, ex))
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
        # No real TTL simulation needed; record the call site of the most recent EXPIRE.
        if key in self.store:
            self._last_expire = (key, ttl)
            return True
        return False

    async def delete(self, key):
        self.store.pop(key, None)
        return 1


# ── Fix 1: per-day overlap detection ──────────────────────────────────────────

class TestPerDayOverlap:
    @pytest.mark.asyncio
    async def test_overlapping_ranges_collide_on_shared_day(self, db_session, test_user, test_room):
        """May 20-23 and May 22-25 must collide (shared night = May 22)."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        # Bump capacity to 1 so DB layer would also fail — but we want to assert
        # Redis fast-fail BEFORE the DB. Room.total_quantity defaults to 2 in the
        # fixture, which would let both succeed at DB level if Redis missed.
        # The collision must come from the Redis layer.
        redis = StatefulFakeRedis()

        # User A creates the second user separately to ensure different owners.
        from app.models.user import User
        from app.core.security import hash_password
        user_b = User(
            id=uuid.uuid4(), email="b@example.com",
            hashed_password=hash_password("Pwd12345!"),
            full_name="User B", role="user", is_active=True, loyalty_points=0,
        )
        db_session.add(user_b)
        await db_session.flush()

        data_a = BookingCreate(items=[RoomItemCreate(
            item_type="room", room_id=test_room.id,
            check_in=date(2026, 5, 20), check_out=date(2026, 5, 23),
            quantity=1, guests_count=1,
        )])
        data_b = BookingCreate(items=[RoomItemCreate(
            item_type="room", room_id=test_room.id,
            check_in=date(2026, 5, 22), check_out=date(2026, 5, 25),
            quantity=1, guests_count=1,
        )])

        await create_booking(db_session, test_user.id, data_a, redis=redis)

        with pytest.raises(LockCollisionError):
            await create_booking(db_session, user_b.id, data_b, redis=redis)

    @pytest.mark.asyncio
    async def test_non_overlapping_ranges_both_succeed(self, db_session, test_user, test_room):
        """Same room_id, distant date ranges → no Redis collision."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        redis = StatefulFakeRedis()

        data_a = BookingCreate(items=[RoomItemCreate(
            item_type="room", room_id=test_room.id,
            check_in=date(2026, 5, 20), check_out=date(2026, 5, 22),
            quantity=1, guests_count=1,
        )])
        data_b = BookingCreate(items=[RoomItemCreate(
            item_type="room", room_id=test_room.id,
            check_in=date(2026, 8, 10), check_out=date(2026, 8, 12),
            quantity=1, guests_count=1,
        )])

        booking_a = await create_booking(db_session, test_user.id, data_a, redis=redis)
        booking_b = await create_booking(db_session, test_user.id, data_b, redis=redis)
        assert booking_a.id is not None
        assert booking_b.id is not None


# ── Fix 1: deadlock-free reverse contention ───────────────────────────────────

@pytest.mark.asyncio
async def test_deadlock_free_reverse_contention():
    """Two concurrent acquires of opposite-direction overlapping ranges must not
    deadlock. Because room_day_keys returns ascending order, both contenders hit
    the shared day in the same order, so one wins cleanly and the other raises."""
    import asyncio

    redis = StatefulFakeRedis()
    rid = uuid.uuid4()
    keys_forward = lock_service.room_day_keys(rid, date(2026, 5, 20), date(2026, 5, 25))
    keys_reverse = lock_service.room_day_keys(rid, date(2026, 5, 22), date(2026, 5, 27))

    async def book(keys, owner):
        acquired = []
        try:
            for k in keys:
                await lock_service.acquire(redis, k, owner)
                acquired.append(k)
            return "ok", owner
        except LockCollisionError:
            await lock_service.release_many(redis, acquired, owner)
            return "collision", owner

    results = await asyncio.wait_for(
        asyncio.gather(book(keys_forward, "u-1"), book(keys_reverse, "u-2")),
        timeout=2.0,
    )
    outcomes = {r[0] for r in results}
    assert outcomes == {"ok", "collision"}  # exactly one of each


# ── Fix 3: LiteAPI Redis lock ─────────────────────────────────────────────────

class TestLiteapiLock:
    @pytest.mark.asyncio
    async def test_duplicate_prebook_blocked_before_http_call(self, db_session, test_user):
        """Second session must 409 before liteapi_service.prebook is even called."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        redis = StatefulFakeRedis()

        from app.models.user import User
        from app.core.security import hash_password
        user_b = User(
            id=uuid.uuid4(), email="lb@example.com",
            hashed_password=hash_password("Pwd12345!"),
            full_name="LB", role="user", is_active=True, loyalty_points=0,
        )
        db_session.add(user_b)
        await db_session.flush()

        data = BookingCreate(items=[RoomItemCreate(
            item_type="room",
            liteapi_rate_id="rate-xyz",
            liteapi_hotel_id="hotel-1",
            liteapi_room_name="Deluxe King",
            liteapi_price=100.0,
            check_in=date(2026, 5, 20), check_out=date(2026, 5, 22),
            quantity=1, guests_count=1,
        )])

        with patch(
            "app.services.liteapi_service.prebook",
            new=AsyncMock(return_value={
                "prebook_id": "pb-1", "price": 100.0, "currency": "USD", "expires_at": None,
            }),
        ) as mock_prebook:
            await create_booking(db_session, test_user.id, data, redis=redis)

            with pytest.raises(LockCollisionError):
                await create_booking(db_session, user_b.id, data, redis=redis)

            # Critical assertion: prebook called exactly once (for user A).
            # User B's collision happens at the Redis layer before the HTTP call.
            assert mock_prebook.call_count == 1

    @pytest.mark.asyncio
    async def test_lock_ttl_shrinks_to_prebook_expiry(self, db_session, test_user):
        """When LiteAPI returns expires_at 60s out, Redis TTL must shrink to 60s."""
        from datetime import datetime, timezone as _tz
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import create_booking

        redis = StatefulFakeRedis()
        expires_at = (datetime.now(tz=_tz.utc) + timedelta(seconds=60)).isoformat()

        data = BookingCreate(items=[RoomItemCreate(
            item_type="room",
            liteapi_rate_id="rate-xyz",
            liteapi_hotel_id="hotel-1",
            liteapi_room_name="Deluxe King",
            liteapi_price=100.0,
            check_in=date(2026, 5, 20), check_out=date(2026, 5, 22),
            quantity=1, guests_count=1,
        )])

        with patch(
            "app.services.liteapi_service.prebook",
            new=AsyncMock(return_value={
                "prebook_id": "pb-1", "price": 100.0, "currency": "USD",
                "expires_at": expires_at,
            }),
        ):
            await create_booking(db_session, test_user.id, data, redis=redis)

        # We expect EXPIRE was called with ttl ≤ 60 on the LiteAPI lock key.
        last = getattr(redis, "_last_expire", None)
        assert last is not None, "redis.expire was never called"
        key, ttl = last
        assert key.startswith("checkout:lock:liteapi:hotel-1:deluxe king:")
        assert 0 < ttl <= 60

    @pytest.mark.asyncio
    async def test_prebook_failure_releases_lock(self, db_session, test_user):
        """If LiteAPI prebook raises after the lock is acquired, the lock must be released."""
        from app.schemas.booking import BookingCreate
        from app.schemas.booking_item import RoomItemCreate
        from app.services.booking_service import BookingServiceError, create_booking
        from app.services.liteapi_service import LiteAPIError

        redis = StatefulFakeRedis()
        data = BookingCreate(items=[RoomItemCreate(
            item_type="room",
            liteapi_rate_id="rate-xyz",
            liteapi_hotel_id="hotel-1",
            liteapi_room_name="Deluxe King",
            liteapi_price=100.0,
            check_in=date(2026, 5, 20), check_out=date(2026, 5, 22),
            quantity=1, guests_count=1,
        )])

        expected_key = lock_service.liteapi_key(
            "hotel-1", "Deluxe King", date(2026, 5, 20), date(2026, 5, 22)
        )

        with patch(
            "app.services.liteapi_service.prebook",
            new=AsyncMock(side_effect=LiteAPIError(502, "upstream down")),
        ):
            with pytest.raises(BookingServiceError):
                await create_booking(db_session, test_user.id, data, redis=redis)

        # (a) lock key no longer in Redis
        assert await redis.get(expected_key) is None
        # (c) immediate retry can acquire cleanly
        assert await lock_service.acquire(redis, expected_key, "retry-owner") is True

    @pytest.mark.asyncio
    async def test_lock_misses_when_room_name_varies(self):
        """KNOWN LIMITATION: LiteAPI doesn't expose a stable room_type_id, so we use
        liteapi_room_name (normalised) as the room-type proxy. Two listings of the
        SAME underlying room with materially different names will NOT collide here;
        the conflict surfaces later at the LiteAPI prebook layer.

        If/when LiteAPI exposes a stable room_type_id, replace this proxy and flip
        the assertion below to `pytest.raises(LockCollisionError)`.
        """
        redis = StatefulFakeRedis()
        ci, co = date(2026, 5, 20), date(2026, 5, 22)
        key_a = lock_service.liteapi_key("hotel-1", "Deluxe King", ci, co)
        key_b = lock_service.liteapi_key("hotel-1", "Deluxe King Room", ci, co)
        assert key_a != key_b

        assert await lock_service.acquire(redis, key_a, "u-1") is True
        # Currently does NOT collide — recording the limitation.
        assert await lock_service.acquire(redis, key_b, "u-2") is True


# ── Fix 4: strict-mode + Redis-down handling ──────────────────────────────────

class TestStrictMode:
    @pytest.mark.asyncio
    async def test_lax_mode_logs_error_and_proceeds(self, caplog):
        """Default (lax): Redis exception → ERROR log + metric line + return True."""
        import logging
        redis = AsyncMock()
        redis.set.side_effect = ConnectionError("Redis down")

        with caplog.at_level(logging.ERROR, logger="app.services.lock_service"):
            result = await lock_service.acquire(redis, "checkout:lock:room:1", "u-1")

        assert result is True
        assert any(
            "metric=lock_service.redis_unavailable_total" in r.message for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_strict_mode_raises_redis_unavailable(self):
        """REDIS_LOCK_STRICT=True: Redis exception → RedisUnavailableError."""
        from app.core.config import settings
        from app.services.lock_service import RedisUnavailableError

        redis = AsyncMock()
        redis.set.side_effect = ConnectionError("Redis down")

        original = settings.REDIS_LOCK_STRICT
        settings.REDIS_LOCK_STRICT = True
        try:
            with pytest.raises(RedisUnavailableError):
                await lock_service.acquire(redis, "checkout:lock:room:1", "u-1")
        finally:
            settings.REDIS_LOCK_STRICT = original

    @pytest.mark.asyncio
    async def test_api_returns_503_in_strict_mode(self, client, user_token, test_room):
        """End-to-end: strict mode + Redis raising → HTTP 503."""
        from app.core.config import settings
        from app.main import app

        app.state.redis.set.side_effect = ConnectionError("Redis down")
        original = settings.REDIS_LOCK_STRICT
        settings.REDIS_LOCK_STRICT = True
        try:
            payload = {
                "items": [{
                    "item_type": "room",
                    "room_id": str(test_room.id),
                    "check_in": str(date(2026, 6, 1)),
                    "check_out": str(date(2026, 6, 3)),
                    "quantity": 1,
                    "guests_count": 1,
                }]
            }
            resp = await client.post(
                "/api/v1/bookings", json=payload,
                headers={"Authorization": f"Bearer {user_token}"},
            )
            assert resp.status_code == 503
        finally:
            settings.REDIS_LOCK_STRICT = original
            app.state.redis.set.side_effect = None
            app.state.redis.set.return_value = True
