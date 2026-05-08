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
