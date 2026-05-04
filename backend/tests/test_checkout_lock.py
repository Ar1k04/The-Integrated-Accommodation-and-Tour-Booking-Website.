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

def test_room_key_format():
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    key = lock_service.room_key(rid, date(2026, 6, 1), date(2026, 6, 3))
    assert key == f"checkout:lock:room:{rid}:2026-06-01:2026-06-03"


def test_tour_key_format():
    tid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    key = lock_service.tour_key(tid, date(2026, 7, 15))
    assert key == f"checkout:lock:tour:{tid}:2026-07-15"
