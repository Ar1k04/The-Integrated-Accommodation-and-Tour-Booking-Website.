"""Tests for loyalty awarding, redemption, and tier recomputation boundaries."""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.loyalty_tier import LoyaltyTier
from app.models.loyalty_transaction import LoyaltyTransaction
from app.models.user import User
from app.services import loyalty_service
from app.services.loyalty_service import LoyaltyError


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
async def test_tier_recomputes_after_redemption(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 600)
    await loyalty_service.redeem_points(db_session, test_user.id, None, 200)

    user = (await db_session.execute(select(User).where(User.id == test_user.id))).scalar_one()
    assert user.loyalty_tier_id == tiers["Bronze"].id


@pytest.mark.asyncio
async def test_get_status_reports_progress(db_session, test_user):
    tiers = await _seed_tiers(db_session)
    await loyalty_service.award_points(db_session, test_user.id, None, 300)

    status = await loyalty_service.get_status(db_session, test_user.id)

    assert status["total_points"] == 300
    assert status["current_tier"].id == tiers["Bronze"].id
    assert status["next_tier"].id == tiers["Silver"].id
    assert status["points_to_next_tier"] == 200
    assert len(status["recent_transactions"]) == 1
