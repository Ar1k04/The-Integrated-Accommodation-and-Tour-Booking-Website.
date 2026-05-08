"""Redis soft-lock for checkout inventory slots. TTL 900s = 15 min (proposal §1).

Prevents two users from simultaneously booking the same room/tour slot.
Falls back to no-op (logs warning) when Redis is unavailable, so DB-level
SELECT FOR UPDATE remains the last line of defence.

Key namespaces (never clash with existing prefixes):
  checkout:lock:room:{room_id}:{check_in}:{check_out}
  checkout:lock:tour:{tour_id}:{tour_date}
  booking:locks:{booking_id}  ← stores the keys held by a booking
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Iterable

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


# ── key builders ──────────────────────────────────────────────────────────────

def room_key(room_id, check_in: date, check_out: date) -> str:
    return f"{KEY_PREFIX}:room:{room_id}:{check_in.isoformat()}:{check_out.isoformat()}"


def tour_key(tour_id, tour_date: date) -> str:
    return f"{KEY_PREFIX}:tour:{tour_id}:{tour_date.isoformat()}"


def _booking_locks_key(booking_id) -> str:
    return f"{BOOKING_LOCKS_PREFIX}:{booking_id}"


# ── primitives ────────────────────────────────────────────────────────────────

async def acquire(redis, key: str, owner: str, ttl: int = CHECKOUT_LOCK_TTL) -> bool:
    """Atomically acquire a slot lock (SET NX EX).

    Returns True on success (first acquire OR same-owner re-acquire).
    Raises LockCollisionError when a *different* owner holds the key.
    Returns True without locking when redis is None (graceful degradation).
    """
    if redis is None:
        logger.debug("Redis unavailable — soft-lock skipped for %s", key)
        return True
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
        logger.warning("Lock acquire failed for %s: %s — proceeding without lock", key, exc)
        return True


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
