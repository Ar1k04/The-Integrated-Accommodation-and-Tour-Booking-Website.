"""Redis soft-lock for checkout inventory slots. TTL 900s = 15 min (proposal §1).

Prevents two users from simultaneously booking the same room/tour slot.

Internal rooms use per-day keys (one key per night in [check_in, check_out)) so
overlapping-but-not-identical date ranges collide. LiteAPI rooms use a single
key scoped to (hotel_id, room_name, check_in, check_out).

When Redis is unavailable, behaviour depends on `settings.REDIS_LOCK_STRICT`:
  - False (default): emit ERROR log + metric line, return True so the booking
    proceeds; the Postgres SELECT FOR UPDATE remains the safety floor.
  - True: raise RedisUnavailableError so the route returns 503.

Key namespaces (never clash with existing prefixes):
  checkout:lock:room:{room_id}:{YYYY-MM-DD}                 ← per-night
  checkout:lock:tour:{tour_id}:{tour_date}
  checkout:lock:liteapi:{hotel_id}:{room_name}:{ci}:{co}
  booking:locks:{booking_id}                                ← keys held per booking
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Iterable

from app.core.config import settings

logger = logging.getLogger(__name__)

CHECKOUT_LOCK_TTL = 900  # seconds — 15 min
KEY_PREFIX = "checkout:lock"
BOOKING_LOCKS_PREFIX = "booking:locks"

# Lua: atomic compare-and-delete — only DEL if current value matches owner.
_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""


class LockCollisionError(Exception):
    """Another user's checkout session is holding this slot."""


class RedisUnavailableError(Exception):
    """Raised in strict mode when Redis is unreachable — caller returns 503."""


def _emit_redis_down(key: str, exc: Exception | None = None) -> bool:
    """Log + metric for redis-down events. Returns True in lax mode, raises in strict mode."""
    logger.error(
        "metric=lock_service.redis_unavailable_total key=%s strict=%s err=%s",
        key,
        settings.REDIS_LOCK_STRICT,
        exc,
    )
    if settings.REDIS_LOCK_STRICT:
        raise RedisUnavailableError(
            "Booking system temporarily unavailable — please try again shortly."
        )
    return True


# ── key builders ──────────────────────────────────────────────────────────────

def room_day_key(room_id, day: date) -> str:
    """Per-night key. Two overlapping ranges share at least one such key."""
    return f"{KEY_PREFIX}:room:{room_id}:{day.isoformat()}"


def room_day_keys(room_id, check_in: date, check_out: date) -> list[str]:
    """All per-night keys for [check_in, check_out), sorted ascending by date.

    Sorted-order acquire prevents deadlock: two sessions touching overlapping
    ranges hit the first shared day in the same order, so one wins cleanly.
    """
    if check_out <= check_in:
        return []
    keys: list[str] = []
    cur = check_in
    while cur < check_out:
        keys.append(room_day_key(room_id, cur))
        cur += timedelta(days=1)
    return keys


def tour_key(tour_id, tour_date: date) -> str:
    return f"{KEY_PREFIX}:tour:{tour_id}:{tour_date.isoformat()}"


def liteapi_key(hotel_id: str, room_name: str, check_in: date, check_out: date) -> str:
    """Lock key for a LiteAPI room slot.

    room_name is normalised (strip + lower) to absorb cosmetic differences.
    Known limitation: LiteAPI does not expose a stable room_type_id, so two
    listings of the same room with materially different names will not collide
    here — see test_liteapi_lock_misses_when_room_name_varies.
    """
    normalised = (room_name or "").strip().lower()
    return f"{KEY_PREFIX}:liteapi:{hotel_id}:{normalised}:{check_in.isoformat()}:{check_out.isoformat()}"


def _booking_locks_key(booking_id) -> str:
    return f"{BOOKING_LOCKS_PREFIX}:{booking_id}"


# ── primitives ────────────────────────────────────────────────────────────────

async def acquire(redis, key: str, owner: str, ttl: int = CHECKOUT_LOCK_TTL) -> bool:
    """Atomically acquire a slot lock (SET NX EX).

    Returns True on success (first acquire OR same-owner re-acquire).
    Raises LockCollisionError when a *different* owner holds the key.
    Raises RedisUnavailableError when Redis is unreachable AND strict mode is on.
    """
    if redis is None:
        return _emit_redis_down(key)
    try:
        ok = await redis.set(key, owner, nx=True, ex=ttl)
        if ok:
            return True
        held_by = await redis.get(key)
        if held_by == owner:
            await redis.expire(key, ttl)  # extend TTL on re-acquire
            return True
        raise LockCollisionError(
            "This slot is currently held by another checkout. Please try again in a few minutes."
        )
    except LockCollisionError:
        raise
    except Exception as exc:
        return _emit_redis_down(key, exc)


async def release(redis, key: str, owner: str) -> bool:
    """Compare-and-delete: releases only if this owner still holds the key."""
    if redis is None:
        return True
    try:
        result = await redis.eval(_RELEASE_LUA, 1, key, owner)
        return bool(result)
    except Exception as exc:
        logger.warning("Lock release failed for %s: %s", key, exc)
        return False


async def release_many(redis, keys: Iterable[str], owner: str) -> None:
    for k in keys:
        await release(redis, k, owner)


# ── partner-write guards ──────────────────────────────────────────────────────

async def _scan_first_match(redis, pattern: str) -> bool:
    """Return True if any key matching `pattern` exists in Redis. Uses SCAN, not KEYS."""
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            return True
        if cursor == 0:
            return False


async def has_active_room_lock(redis, room_id) -> bool:
    """True if any checkout currently holds a per-day lock on this room.

    Used by partner write endpoints (DELETE / capacity-reducing PATCH) to refuse
    mutations that would strand a guest mid-checkout. Returns False when Redis
    is unreachable in lax mode; raises RedisUnavailableError in strict mode so
    the route returns 503.
    """
    pattern = f"{KEY_PREFIX}:room:{room_id}:*"
    if redis is None:
        _emit_redis_down(pattern)
        return False
    try:
        return await _scan_first_match(redis, pattern)
    except Exception as exc:
        _emit_redis_down(pattern, exc)
        return False


async def has_active_tour_lock(redis, tour_id) -> bool:
    """True if any checkout currently holds a lock on this tour. See `has_active_room_lock`."""
    pattern = f"{KEY_PREFIX}:tour:{tour_id}:*"
    if redis is None:
        _emit_redis_down(pattern)
        return False
    try:
        return await _scan_first_match(redis, pattern)
    except Exception as exc:
        _emit_redis_down(pattern, exc)
        return False


# ── booking-scoped helpers ────────────────────────────────────────────────────

async def store_booking_locks(redis, booking_id, keys: list[str], owner: str) -> None:
    """Persist the set of lock keys held for a booking so confirm/cancel can release them."""
    if redis is None or not keys:
        return
    try:
        payload = json.dumps({"keys": keys, "owner": owner})
        await redis.set(_booking_locks_key(booking_id), payload, ex=CHECKOUT_LOCK_TTL)
    except Exception as exc:
        logger.warning("store_booking_locks failed for %s: %s", booking_id, exc)


async def release_booking_locks(redis, booking_id) -> None:
    """Release all soft-locks held for a booking (call from confirm/cancel)."""
    if redis is None:
        return
    try:
        raw = await redis.get(_booking_locks_key(booking_id))
        if not raw:
            return
        data = json.loads(raw)
        await release_many(redis, data["keys"], data["owner"])
        await redis.delete(_booking_locks_key(booking_id))
    except Exception as exc:
        logger.warning("release_booking_locks failed for %s: %s", booking_id, exc)
