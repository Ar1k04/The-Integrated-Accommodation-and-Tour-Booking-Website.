"""Tests for voucher validation and application."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voucher import Voucher
from app.services import voucher_service
from app.services.voucher_service import VoucherError


async def _mk_voucher(
    db: AsyncSession,
    admin_id: uuid.UUID,
    *,
    code: str = "SAVE10",
    discount_type: str = "percentage",
    discount_value: float = 10.0,
    min_order_value: float = 0,
    max_uses: int = 10,
    status: str = "active",
    valid_from: date | None = None,
    valid_to: date | None = None,
) -> Voucher:
    today = date.today()
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=admin_id,
        code=code,
        name=f"{code} voucher",
        discount_type=discount_type,
        discount_value=discount_value,
        min_order_value=min_order_value,
        max_uses=max_uses,
        valid_from=valid_from or today - timedelta(days=1),
        valid_to=valid_to or today + timedelta(days=30),
        status=status,
    )
    db.add(v)
    await db.flush()
    await db.refresh(v)
    return v


@pytest.mark.asyncio
async def test_validate_voucher_happy_path(db_session, admin_user, test_user):
    v = await _mk_voucher(db_session, admin_user.id)
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100")
    )
    assert got.id == v.id


@pytest.mark.asyncio
async def test_validate_voucher_below_minimum(db_session, admin_user, test_user):
    v = await _mk_voucher(db_session, admin_user.id, min_order_value=200)
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100")
        )


@pytest.mark.asyncio
async def test_validate_voucher_expired(db_session, admin_user, test_user):
    yesterday = date.today() - timedelta(days=1)
    v = await _mk_voucher(
        db_session,
        admin_user.id,
        code="OLD",
        valid_from=yesterday - timedelta(days=10),
        valid_to=yesterday,
    )
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100")
        )


@pytest.mark.asyncio
async def test_duplicate_voucher_use_blocked(
    db_session, admin_user, test_user, test_room
):
    from app.models.booking import Booking

    v = await _mk_voucher(db_session, admin_user.id)
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("150"),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    await voucher_service.apply_voucher(db_session, booking, v, test_user.id)
    await db_session.flush()

    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("150")
        )


def test_compute_percentage_discount():
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),
        code="X",
        name="X",
        discount_type="percentage",
        discount_value=15,
        min_order_value=0,
        max_uses=1,
        valid_from=date.today(),
        valid_to=date.today(),
        status="active",
    )
    assert voucher_service.compute_discount(v, Decimal("200")) == Decimal("30.00")


def test_compute_fixed_discount_capped_at_subtotal():
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),
        code="Y",
        name="Y",
        discount_type="fixed",
        discount_value=500,
        min_order_value=0,
        max_uses=1,
        valid_from=date.today(),
        valid_to=date.today(),
        status="active",
    )
    assert voucher_service.compute_discount(v, Decimal("100")) == Decimal("100.00")


# ---------------------------------------------------------------------------
# Phase 2 enhancements
# ---------------------------------------------------------------------------


def test_compute_percentage_respects_max_discount_cap():
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),
        code="CAPPED",
        name="Capped 50% off, max $50",
        discount_type="percentage",
        discount_value=50,
        maximum_discount_amount=50,
        currency="USD",
        min_order_value=0,
        budget=None,
        budget_used=0,
        max_uses=1,
        valid_from=date.today(),
        valid_to=date.today(),
        status="active",
        applicable_to="all",
        liteapi_sync_status="not_synced",
    )
    # 50% of 200 would be 100, but capped at 50.
    assert voucher_service.compute_discount(v, Decimal("200")) == Decimal("50.00")
    # On a small order, 50% < cap → no change.
    assert voucher_service.compute_discount(v, Decimal("80")) == Decimal("40.00")


@pytest.mark.asyncio
async def test_validate_voucher_guest_locked_rejects_other_user(
    db_session, admin_user, test_user
):
    v = await _mk_voucher(db_session, admin_user.id, code="GUESTONLY")
    v.guest_id = admin_user.id  # locked to a *different* user than test_user
    await db_session.flush()
    with pytest.raises(VoucherError, match="reserved"):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100")
        )


@pytest.mark.asyncio
async def test_validate_voucher_guest_locked_accepts_owner(
    db_session, admin_user, test_user
):
    v = await _mk_voucher(db_session, admin_user.id, code="GUESTOK")
    v.guest_id = test_user.id
    await db_session.flush()
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100")
    )
    assert got.id == v.id


@pytest.mark.asyncio
async def test_validate_voucher_budget_exhausted(db_session, admin_user, test_user):
    v = await _mk_voucher(
        db_session, admin_user.id, code="BUDGET", discount_value=20, max_uses=100
    )
    v.budget = Decimal("10")  # tiny budget
    v.budget_used = Decimal("0")
    await db_session.flush()
    # 20% of 100 = $20 discount, which exceeds budget of $10 → reject.
    with pytest.raises(VoucherError, match="budget"):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100")
        )


@pytest.mark.asyncio
async def test_apply_voucher_increments_budget_used(
    db_session, admin_user, test_user
):
    from app.models.booking import Booking

    v = await _mk_voucher(db_session, admin_user.id, code="POOL", max_uses=10)
    v.budget = Decimal("1000")
    v.budget_used = Decimal("0")
    await db_session.flush()

    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("500"),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    discount = await voucher_service.apply_voucher(db_session, booking, v, test_user.id)
    assert discount == Decimal("50.00")  # 10% of 500
    await db_session.refresh(v)
    assert Decimal(str(v.budget_used)) == Decimal("50.00")


@pytest.mark.asyncio
async def test_record_usage_only_does_not_double_discount(
    db_session, admin_user, test_user
):
    """When LiteAPI applied the voucher supplier-side, record_usage_only must
    track the discount for budget/reporting without re-deducting it from the
    booking total."""
    from app.models.booking import Booking

    v = await _mk_voucher(db_session, admin_user.id, code="SUPPLIER", max_uses=10)
    v.budget = Decimal("500")
    v.budget_used = Decimal("0")
    await db_session.flush()

    # booking.total_price is already post-discount (supplier returned $180 for
    # a $200 quote with a 10% voucher).
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("180"),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    supplier_discount = Decimal("20")
    await voucher_service.record_usage_only(
        db_session, booking, v, test_user.id, supplier_discount
    )
    await db_session.refresh(booking)
    await db_session.refresh(v)

    # Total stays at supplier price; discount_amount records the supplier discount.
    assert Decimal(str(booking.total_price)) == Decimal("180")
    assert Decimal(str(booking.discount_amount)) == Decimal("20.00")
    # Budget tracking incremented.
    assert Decimal(str(v.budget_used)) == Decimal("20.00")
    assert v.used_count == 1


@pytest.mark.asyncio
async def test_validate_voucher_backward_compat_all_new_fields_null(
    db_session, admin_user, test_user
):
    """An old-style voucher with no max-cap / budget / guest_id behaves exactly
    as before. Regression guard for migration 020."""
    v = await _mk_voucher(db_session, admin_user.id, code="LEGACY")
    # Don't touch any of the new fields.
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100")
    )
    assert got.id == v.id
    assert voucher_service.compute_discount(v, Decimal("100")) == Decimal("10.00")


def test_should_sync_respects_flag_and_eligibility():
    """sync helper: only hotel-applicable, non-guest-locked, flag-on vouchers sync."""
    from app.core.config import settings

    base = Voucher(
        id=uuid.uuid4(),
        admin_id=uuid.uuid4(),
        code="S",
        name="S",
        discount_type="percentage",
        discount_value=10,
        currency="USD",
        min_order_value=0,
        budget_used=0,
        max_uses=1,
        valid_from=date.today(),
        valid_to=date.today(),
        status="active",
        applicable_to="all",
        liteapi_sync_status="not_synced",
    )
    original = settings.LITEAPI_VOUCHER_SYNC_ENABLED
    try:
        settings.LITEAPI_VOUCHER_SYNC_ENABLED = False
        assert voucher_service._should_sync(base) is False
        settings.LITEAPI_VOUCHER_SYNC_ENABLED = True
        assert voucher_service._should_sync(base) is True
        # Tour vouchers cannot sync.
        base.applicable_to = "tour"
        assert voucher_service._should_sync(base) is False
        base.applicable_to = "all"
        # Guest-locked vouchers cannot sync.
        base.guest_id = uuid.uuid4()
        assert voucher_service._should_sync(base) is False
        base.guest_id = None
        # Explicitly disabled blocks sync.
        base.liteapi_sync_status = "disabled"
        assert voucher_service._should_sync(base) is False
    finally:
        settings.LITEAPI_VOUCHER_SYNC_ENABLED = original
