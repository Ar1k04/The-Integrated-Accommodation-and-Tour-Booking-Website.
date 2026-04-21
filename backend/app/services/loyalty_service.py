"""Loyalty ledger: earning, redeeming, and tier recomputation.

- Earning rule: 1 point per $1 of booking total (excluding discount/redemption).
- Redemption rule: 1 point == $0.01 discount.
- Tier recompute runs after every points mutation and sets users.loyalty_tier_id
  according to loyalty_tier.min_points / max_points boundaries.
"""
import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loyalty_tier import LoyaltyTier
from app.models.loyalty_transaction import LoyaltyTransaction, LoyaltyTransactionType
from app.models.user import User


REDEEM_RATE = Decimal("0.01")


class LoyaltyError(ValueError):
    """Raised when loyalty operations cannot complete."""


async def _lock_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = (
        await db.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one_or_none()
    if not user:
        raise LoyaltyError("User not found")
    return user


async def award_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    booking_id: uuid.UUID | None,
    amount: int,
    description: str | None = None,
) -> LoyaltyTransaction:
    """Add `amount` points. Locks the user row to serialise concurrent writes."""

    if amount <= 0:
        raise LoyaltyError("Award amount must be positive")

    user = await _lock_user(db, user_id)
    user.loyalty_points = (user.loyalty_points or 0) + amount
    txn = LoyaltyTransaction(
        user_id=user_id,
        booking_id=booking_id,
        points=amount,
        type=LoyaltyTransactionType.earn.value,
        description=description or f"Earned {amount} pts",
    )
    db.add(txn)
    await db.flush()
    await recompute_tier(db, user)
    return txn


async def redeem_points(
    db: AsyncSession,
    user_id: uuid.UUID,
    booking_id: uuid.UUID | None,
    points: int,
    description: str | None = None,
) -> tuple[LoyaltyTransaction, Decimal]:
    """Deduct `points` from the user, return (transaction, discount_amount)."""

    if points <= 0:
        raise LoyaltyError("Redemption amount must be positive")

    user = await _lock_user(db, user_id)
    if (user.loyalty_points or 0) < points:
        raise LoyaltyError("Insufficient loyalty points")

    user.loyalty_points -= points
    txn = LoyaltyTransaction(
        user_id=user_id,
        booking_id=booking_id,
        points=-points,
        type=LoyaltyTransactionType.redeem.value,
        description=description or f"Redeemed {points} pts",
    )
    db.add(txn)
    await db.flush()
    await recompute_tier(db, user)
    discount = (Decimal(points) * REDEEM_RATE).quantize(Decimal("0.01"))
    return txn, discount


async def recompute_tier(db: AsyncSession, user: User) -> LoyaltyTier | None:
    """Map user.loyalty_points to the matching LoyaltyTier row."""

    points = user.loyalty_points or 0
    tier = (
        await db.execute(
            select(LoyaltyTier)
            .where(and_(LoyaltyTier.min_points <= points))
            .order_by(LoyaltyTier.min_points.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    user.loyalty_tier_id = tier.id if tier else None
    await db.flush()
    return tier


async def get_status(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Return tier + points + recent txns for UI display."""

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise LoyaltyError("User not found")

    current_tier = None
    next_tier = None
    if user.loyalty_tier_id:
        current_tier = (
            await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == user.loyalty_tier_id))
        ).scalar_one_or_none()
    next_tier = (
        await db.execute(
            select(LoyaltyTier)
            .where(LoyaltyTier.min_points > (user.loyalty_points or 0))
            .order_by(LoyaltyTier.min_points.asc())
            .limit(1)
        )
    ).scalar_one_or_none()

    recent = (
        await db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.user_id == user_id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .limit(10)
        )
    ).scalars().all()

    return {
        "user_id": user.id,
        "total_points": user.loyalty_points or 0,
        "current_tier": current_tier,
        "next_tier": next_tier,
        "points_to_next_tier": max(0, (next_tier.min_points - (user.loyalty_points or 0))) if next_tier else 0,
        "recent_transactions": recent,
    }
