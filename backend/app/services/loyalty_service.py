"""Loyalty ledger: earning, redeeming, and tier recomputation.

- Earning rule: 1 point per $1 of booking total (excluding discount/redemption).
- Redemption rule: 1 point == $0.01 discount.
- Tier is driven by lifetime_loyalty_points (total ever earned) so redeeming
  the spendable balance never demotes the user's tier.
- Tier recompute runs after every points mutation.
"""
import uuid
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
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
    """Add `amount` points to both spendable balance and lifetime total."""

    if amount <= 0:
        raise LoyaltyError("Award amount must be positive")

    user = await _lock_user(db, user_id)
    user.loyalty_points = (user.loyalty_points or 0) + amount
    user.lifetime_loyalty_points = (user.lifetime_loyalty_points or 0) + amount
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
    """Deduct `points` from spendable balance only; lifetime total is unchanged."""

    if points <= 0:
        raise LoyaltyError("Redemption amount must be positive")

    # AUTHZ-05: a redemption tied to a booking must target the caller's own
    # booking — never let a user redeem against someone else's order.
    if booking_id is not None:
        booking = (
            await db.execute(select(Booking).where(Booking.id == booking_id))
        ).scalar_one_or_none()
        if booking is None:
            raise LoyaltyError("Booking not found")
        if booking.user_id != user_id:
            raise LoyaltyError("Booking does not belong to this user")

        # FE-02: idempotent per booking. If a redeem already exists for this
        # booking, return it instead of deducting again (safe FE retries /
        # lost responses).
        existing = (
            await db.execute(
                select(LoyaltyTransaction).where(
                    and_(
                        LoyaltyTransaction.booking_id == booking_id,
                        LoyaltyTransaction.type == LoyaltyTransactionType.redeem.value,
                    )
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, (Decimal(-existing.points) * REDEEM_RATE).quantize(Decimal("0.01"))

    user = await _lock_user(db, user_id)
    if (user.loyalty_points or 0) < points:
        raise LoyaltyError("Insufficient loyalty points")

    user.loyalty_points -= points
    # lifetime_loyalty_points intentionally not decremented — tier stays stable
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
    """Map user.lifetime_loyalty_points to the matching LoyaltyTier row."""

    lifetime = user.lifetime_loyalty_points or 0
    tier = (
        await db.execute(
            select(LoyaltyTier)
            .where(and_(LoyaltyTier.min_points <= lifetime))
            .order_by(LoyaltyTier.min_points.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    user.loyalty_tier_id = tier.id if tier else None
    await db.flush()
    return tier


async def reverse_booking_points(
    db: AsyncSession,
    booking_id: uuid.UUID,
) -> None:
    """Undo loyalty effects of a booking on cancellation.

    - Earned points: deduct from spendable balance and lifetime, each capped at 0.
    - Redeemed points: restore to spendable balance (lifetime stays put).
    Writes 'adjust' transactions for the audit trail.
    """
    from sqlalchemy import func

    # Sum earned for this booking (positive rows)
    earned_result = await db.execute(
        select(func.sum(LoyaltyTransaction.points))
        .where(
            LoyaltyTransaction.booking_id == booking_id,
            LoyaltyTransaction.type == LoyaltyTransactionType.earn.value,
        )
    )
    earned = int(earned_result.scalar() or 0)

    # Sum redeemed for this booking (negative rows, so negate)
    redeemed_result = await db.execute(
        select(func.sum(LoyaltyTransaction.points))
        .where(
            LoyaltyTransaction.booking_id == booking_id,
            LoyaltyTransaction.type == LoyaltyTransactionType.redeem.value,
        )
    )
    redeemed = abs(int(redeemed_result.scalar() or 0))

    if earned == 0 and redeemed == 0:
        return  # nothing to reverse (e.g. pending booking never confirmed)

    # Fetch a user_id from one of the transactions
    txn_ref = (
        await db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.booking_id == booking_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if not txn_ref:
        return

    user = await _lock_user(db, txn_ref.user_id)

    if earned > 0:
        to_deduct_balance = min(earned, user.loyalty_points or 0)
        to_deduct_lifetime = min(earned, user.lifetime_loyalty_points or 0)
        user.loyalty_points = (user.loyalty_points or 0) - to_deduct_balance
        user.lifetime_loyalty_points = (user.lifetime_loyalty_points or 0) - to_deduct_lifetime
        # MONEY-02: the deduction is capped at the current balance (we never
        # drive points negative). When capped, record the shortfall in the
        # audit trail so earned≠reversed is explainable.
        if to_deduct_balance < earned:
            reverse_desc = (
                f"Reversed earn (capped {to_deduct_balance}/{earned}) "
                f"from cancelled booking {booking_id}"
            )
        else:
            reverse_desc = f"Reversed earn from cancelled booking {booking_id}"
        db.add(LoyaltyTransaction(
            user_id=user.id,
            booking_id=booking_id,
            points=-to_deduct_balance,
            type=LoyaltyTransactionType.adjust.value,
            description=reverse_desc,
        ))

    if redeemed > 0:
        user.loyalty_points = (user.loyalty_points or 0) + redeemed
        db.add(LoyaltyTransaction(
            user_id=user.id,
            booking_id=booking_id,
            points=redeemed,
            type=LoyaltyTransactionType.adjust.value,
            description=f"Restored redeem from cancelled booking {booking_id}",
        ))

    await db.flush()
    await recompute_tier(db, user)


async def get_status(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Return tier + points + recent txns for UI display."""

    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise LoyaltyError("User not found")

    current_tier = None
    if user.loyalty_tier_id:
        current_tier = (
            await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == user.loyalty_tier_id))
        ).scalar_one_or_none()

    lifetime = user.lifetime_loyalty_points or 0
    next_tier = (
        await db.execute(
            select(LoyaltyTier)
            .where(LoyaltyTier.min_points > lifetime)
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
        "lifetime_points": lifetime,
        "current_tier": current_tier,
        "next_tier": next_tier,
        "points_to_next_tier": max(0, next_tier.min_points - lifetime) if next_tier else 0,
        "recent_transactions": recent,
    }
