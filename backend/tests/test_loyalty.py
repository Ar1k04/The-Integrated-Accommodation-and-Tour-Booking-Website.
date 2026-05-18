"""Tests for loyalty awarding, redemption, and tier recomputation boundaries."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.loyalty_tier import LoyaltyTier
from app.models.loyalty_transaction import LoyaltyTransaction, LoyaltyTransactionType
from app.models.user import User
from app.services import loyalty_service
from app.services.loyalty_service import LoyaltyError


async def _make_booking(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Insert a minimal Booking row so loyalty_transaction FK is satisfied."""
    booking = Booking(id=uuid.uuid4(), user_id=user_id, total_price=0)
    db.add(booking)
    await db.flush()
    return booking.id


async def _seed_tiers(db: AsyncSession) -> dict[str, LoyaltyTier]:
    tiers = {
        "Bronze": LoyaltyTier(name="Bronze", min_points=0, max_points=499, discount_percent=0),
        "Silver": LoyaltyTier(name="Silver", min_points=500, max_points=1499, discount_percent=5),
        "Gold": LoyaltyTier(name="Gold", min_points=1500, max_points=4999, discount_percent=10),
        "Platinum": LoyaltyTier(name="Platinum", min_points=5000, max_points=999999, discount_percent=15),
    }
    for t in tiers.values():
        t.id = uuid.uuid4()
        db.add(t)
    await db.flush()
    return tiers


@pytest.mark.asyncio
async def test_award_points_creates_transaction(db_session, test_user):
    await _seed_tiers(db_session)
    txn = await loyalty_service.award_points(db_session, test_user.id, None, 100)

    assert txn.points == 100
    assert txn.type == "earn"
    refreshed = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert refreshed.loyalty_points == 100


@pytest.mark.asyncio
async def test_award_non_positive_rejected(db_session, test_user):
    await _seed_tiers(db_session)
    with pytest.raises(LoyaltyError):
        await loyalty_service.award_points(db_session, test_user.id, None, 0)


@pytest.mark.asyncio
async def test_award_increments_lifetime_too(db_session, test_user):
    """Earning points must update both spendable balance and lifetime total."""
    await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 100)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 100
    assert user.lifetime_loyalty_points == 100


@pytest.mark.asyncio
async def test_redeem_points_returns_discount(db_session, test_user):
    await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 500)

    txn, discount = await loyalty_service.redeem_points(db_session, test_user.id, None, 250)

    assert txn.points == -250
    assert txn.type == "redeem"
    assert discount == Decimal("2.50")
    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 250


@pytest.mark.asyncio
async def test_redeem_does_not_decrement_lifetime(db_session, test_user):
    """Redeeming balance should not affect lifetime_loyalty_points."""
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 1500)  # Gold
    await loyalty_service.redeem_points(db_session, test_user.id, None, 1000)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 500         # spendable balance reduced
    assert user.lifetime_loyalty_points == 1500  # lifetime untouched
    assert user.loyalty_tier_id == tiers["Gold"].id  # tier held by lifetime


@pytest.mark.asyncio
async def test_redeem_insufficient_points(db_session, test_user):
    await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 50)
    with pytest.raises(LoyaltyError):
        await loyalty_service.redeem_points(db_session, test_user.id, None, 100)


@pytest.mark.asyncio
async def test_tier_boundary_499_is_bronze(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 499)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_tier_id == tiers["Bronze"].id


@pytest.mark.asyncio
async def test_tier_boundary_500_is_silver(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 500)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_tier_id == tiers["Silver"].id


@pytest.mark.asyncio
async def test_tier_boundary_1500_is_gold(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 1500)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_tier_id == tiers["Gold"].id


@pytest.mark.asyncio
async def test_tier_stays_after_redemption(db_session, test_user):
    """After reaching Silver (600 lifetime), redeeming 200 should NOT demote to Bronze."""
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 600)
    await loyalty_service.redeem_points(db_session, test_user.id, None, 200)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    # lifetime_loyalty_points = 600 → Silver; spendable = 400
    assert user.loyalty_tier_id == tiers["Silver"].id
    assert user.loyalty_points == 400
    assert user.lifetime_loyalty_points == 600


@pytest.mark.asyncio
async def test_get_status_reports_progress(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 300)

    status = await loyalty_service.get_status(db_session, test_user.id)

    assert status["total_points"] == 300
    assert status["lifetime_points"] == 300
    assert status["current_tier"].id == tiers["Bronze"].id
    assert status["next_tier"].id == tiers["Silver"].id
    assert status["points_to_next_tier"] == 200
    assert len(status["recent_transactions"]) == 1


@pytest.mark.asyncio
async def test_reverse_booking_points_deducts_earned(db_session, test_user):
    """Cancelling a confirmed booking reverses earned points from balance and lifetime."""
    await _seed_tiers(db_session)
    booking_id = await _make_booking(db_session, test_user.id)
    await loyalty_service.award_points(db_session, test_user.id, booking_id, 100)

    await loyalty_service.reverse_booking_points(db_session, booking_id)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 0
    assert user.lifetime_loyalty_points == 0

    # Adjust transaction should be written
    txns = (await db_session.execute(
        select(LoyaltyTransaction)
        .where(LoyaltyTransaction.booking_id == booking_id,
               LoyaltyTransaction.type == LoyaltyTransactionType.adjust.value)
    )).scalars().all()
    assert len(txns) == 1
    assert txns[0].points == -100


@pytest.mark.asyncio
async def test_reverse_booking_points_caps_at_zero(db_session, test_user):
    """If user already spent some earned points, reversal caps deduction at 0."""
    await _seed_tiers(db_session)
    booking_id = await _make_booking(db_session, test_user.id)
    # Earn 100 from this booking
    await loyalty_service.award_points(db_session, test_user.id, booking_id, 100)
    # Spend 80 on a different booking (balance = 20, lifetime = 100)
    await loyalty_service.redeem_points(db_session, test_user.id, None, 80)

    await loyalty_service.reverse_booking_points(db_session, booking_id)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 0           # 20 - 20 (capped, not -80)
    assert user.lifetime_loyalty_points == 0  # 100 - 100 (full deduct from lifetime)


@pytest.mark.asyncio
async def test_reverse_booking_points_restores_redeemed(db_session, test_user):
    """Cancelling restores points that were redeemed at booking time."""
    await _seed_tiers(db_session)
    booking_id = await _make_booking(db_session, test_user.id)
    # Earn 500, then redeem 200 for this booking
    await loyalty_service.award_points(db_session, test_user.id, None, 500)
    await loyalty_service.redeem_points(db_session, test_user.id, booking_id, 200)

    await loyalty_service.reverse_booking_points(db_session, booking_id)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    # Balance: 500 - 200 + 200 (restored) = 500
    assert user.loyalty_points == 500
    # Lifetime unchanged by redeem/restore
    assert user.lifetime_loyalty_points == 500


@pytest.mark.asyncio
async def test_pending_booking_cancel_no_loyalty_change(db_session, test_user):
    """Cancelling a pending booking (never confirmed, no earn txns) is a no-op."""
    await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 200)

    # reverse_booking_points for a booking_id with no transactions is a no-op
    fake_booking_id = uuid.uuid4()
    await loyalty_service.reverse_booking_points(db_session, fake_booking_id)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_points == 200  # untouched
