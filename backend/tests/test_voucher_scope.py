"""Tests for cart-aware voucher rules and deferred usage (UC16, UC31)."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.booking import Booking
from app.models.voucher import Voucher
from app.models.voucher_usage import VoucherUsage
from app.services import voucher_service
from app.services.voucher_service import VoucherError
from sqlalchemy import select


async def _mk_voucher(db, admin_id, *, code="SCOPE10", applicable_to="all", max_uses=10):
    today = date.today()
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=admin_id,
        code=code,
        name=f"{code} voucher",
        discount_type="percentage",
        discount_value=10.0,
        min_order_value=0,
        max_uses=max_uses,
        valid_from=today - timedelta(days=1),
        valid_to=today + timedelta(days=30),
        status="active",
        applicable_to=applicable_to,
    )
    db.add(v)
    await db.flush()
    await db.refresh(v)
    return v


# ── UC16: applicable_to product-type restriction ──────────────────────────────

@pytest.mark.asyncio
async def test_applicable_to_rejects_wrong_product_type(db_session, admin_user, test_user):
    v = await _mk_voucher(db_session, admin_user.id, code="TOURONLY", applicable_to="tour")
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100"),
            item_types={"room"}, product_owners=[None],
        )


@pytest.mark.asyncio
async def test_applicable_to_hotel_allows_room_items(db_session, admin_user, test_user):
    # Voucher category "hotel" maps to booking item_type "room".
    v = await _mk_voucher(db_session, admin_user.id, code="HOTELONLY", applicable_to="hotel")
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100"),
        item_types={"room"}, product_owners=[None],
    )
    assert got.id == v.id


@pytest.mark.asyncio
async def test_applicable_to_all_allows_any(db_session, admin_user, test_user):
    v = await _mk_voucher(db_session, admin_user.id, code="ANY", applicable_to="all")
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100"),
        item_types={"tour"}, product_owners=[None],
    )
    assert got.id == v.id


# ── UC31: partner vouchers bound to the partner's own products ─────────────────

@pytest.mark.asyncio
async def test_partner_voucher_allows_own_products(db_session, partner_user, test_user):
    v = await _mk_voucher(db_session, partner_user.id, code="PARTOWN")
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100"),
        item_types={"room"}, product_owners=[partner_user.id],
    )
    assert got.id == v.id


@pytest.mark.asyncio
async def test_partner_voucher_rejects_other_owner(db_session, partner_user, test_user):
    v = await _mk_voucher(db_session, partner_user.id, code="PARTOTHER")
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100"),
            item_types={"room"}, product_owners=[uuid.uuid4()],
        )


@pytest.mark.asyncio
async def test_partner_voucher_rejects_supplier_items(db_session, partner_user, test_user):
    v = await _mk_voucher(db_session, partner_user.id, code="PARTSUPP")
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100"),
            item_types={"room"}, product_owners=[], has_supplier_items=True,
        )


@pytest.mark.asyncio
async def test_admin_voucher_stays_global(db_session, admin_user, test_user):
    # Platform-admin vouchers are not restricted to any owner/supplier.
    v = await _mk_voucher(db_session, admin_user.id, code="GLOBAL")
    got = await voucher_service.validate_voucher(
        db_session, v.code, test_user.id, Decimal("100"),
        item_types={"room"}, product_owners=[uuid.uuid4()], has_supplier_items=True,
    )
    assert got.id == v.id


# ── UC16: usage deferred to payment, then committed idempotently ───────────────

async def _mk_booking(db, user_id, voucher_id, discount):
    booking = Booking(
        id=uuid.uuid4(), user_id=user_id, total_price=Decimal("90"),
        status="pending", voucher_id=voucher_id, discount_amount=discount,
    )
    db.add(booking)
    await db.flush()
    return booking


@pytest.mark.asyncio
async def test_apply_voucher_reserves_usage_at_creation(db_session, admin_user, test_user):
    # Reserve-at-creation: usage is recorded immediately so a single-use voucher
    # cannot be double-applied across two concurrent pending carts (the second
    # validate sees the existing per-user usage and is rejected).
    v = await _mk_voucher(db_session, admin_user.id, code="RESERVE", max_uses=1)
    booking = await _mk_booking(db_session, test_user.id, None, Decimal("0"))
    booking.total_price = Decimal("100")

    discount = await voucher_service.apply_voucher(db_session, booking, v, test_user.id)
    assert discount == Decimal("10.00")
    await db_session.refresh(v)
    assert v.used_count == 1

    # A second cart by the same user cannot also redeem it.
    with pytest.raises(VoucherError):
        await voucher_service.validate_voucher(
            db_session, v.code, test_user.id, Decimal("100"),
            item_types={"room"}, product_owners=[None],
        )


@pytest.mark.asyncio
async def test_cancel_pending_booking_releases_voucher(db_session, admin_user, test_user):
    # UC16/UC17: an unpaid pending booking that expires must release the voucher.
    from sqlalchemy.orm import selectinload
    from app.models.booking import Booking as BookingModel
    from app.services.booking_service import cancel_pending_booking

    v = await _mk_voucher(db_session, admin_user.id, code="RELEASE", max_uses=1)
    booking = await _mk_booking(db_session, test_user.id, None, Decimal("0"))
    booking.total_price = Decimal("100")
    await voucher_service.apply_voucher(db_session, booking, v, test_user.id)
    await db_session.refresh(v)
    assert v.used_count == 1

    loaded = (await db_session.execute(
        select(BookingModel).options(selectinload(BookingModel.items))
        .where(BookingModel.id == booking.id)
    )).scalar_one()
    await cancel_pending_booking(db_session, loaded, redis=None)

    await db_session.refresh(v)
    assert v.used_count == 0  # released — customer can reuse it
    assert loaded.status == "cancelled"
    usage = (await db_session.execute(
        select(VoucherUsage).where(VoucherUsage.booking_id == booking.id)
    )).scalar_one_or_none()
    assert usage is None
