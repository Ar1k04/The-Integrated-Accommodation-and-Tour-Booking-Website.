"""Tests cho 4 sửa lỗi logic sau buổi rà soát (2026-06-01).

#1 LiteAPI/Viator booking thất bại KHÔNG còn bị đánh dấu confirmed — item được
   đưa vào failed_items và hoàn tiền (giống Duffel).
#2 Khi confirm thất bại toàn phần → hoàn điểm đã redeem + nhả voucher.
#3 cancel_booking nhả voucher (reverse_voucher_for_booking).
#4 validate_voucher khóa hàng voucher (with_for_update) — ở đây kiểm tra
   happy-path + tái sử dụng sau khi nhả.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.voucher import Voucher
from app.models.voucher_usage import VoucherUsage
from app.services import booking_service, loyalty_service, voucher_service
from app.services.booking_service import cancel_booking, confirm_booking
from app.services.liteapi_service import LiteAPIError
from app.services.viator_service import ViatorError


def _stripe_refund(refund_id: str, amount_cents: int) -> MagicMock:
    obj = MagicMock()
    obj.id = refund_id
    obj.amount = amount_cents
    obj.status = "succeeded"
    return obj


async def _mk_voucher(db, admin_id, *, code="REV10", discount_value=20.0, budget=None):
    today = date.today()
    v = Voucher(
        id=uuid.uuid4(),
        admin_id=admin_id,
        code=code,
        name=f"{code} voucher",
        discount_type="fixed",
        discount_value=discount_value,
        min_order_value=0,
        max_uses=5,
        valid_from=today - timedelta(days=1),
        valid_to=today + timedelta(days=30),
        status="active",
        budget=budget,
        budget_used=0,
    )
    db.add(v)
    await db.flush()
    await db.refresh(v)
    return v


async def _reload(db, booking_id):
    return (
        await db.execute(
            select(Booking)
            .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
            .where(Booking.id == booking_id)
        )
    ).scalar_one()


# ── #3 + #4: reverse_voucher_for_booking releases usage / count / budget ──────
@pytest.mark.asyncio
async def test_reverse_voucher_releases_usage_count_and_budget(db_session, admin_user, test_user):
    voucher = await _mk_voucher(db_session, admin_user.id, code="BUD20", discount_value=20, budget=100)
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("100"), status=BookingStatus.pending.value)
    db_session.add(booking)
    await db_session.flush()

    discount = await voucher_service.apply_voucher(db_session, booking, voucher, test_user.id)
    await db_session.refresh(voucher)
    assert voucher.used_count == 1
    assert Decimal(str(voucher.budget_used)) == discount  # 20

    await voucher_service.reverse_voucher_for_booking(db_session, booking.id)
    await db_session.refresh(voucher)

    # used_count + budget restored, usage row gone.
    assert voucher.used_count == 0
    assert Decimal(str(voucher.budget_used)) == Decimal("0.00")
    usage = (
        await db_session.execute(select(VoucherUsage).where(VoucherUsage.booking_id == booking.id))
    ).scalar_one_or_none()
    assert usage is None
    # And the same user can validate (reuse) it again — UNIQUE(voucher,user) freed.
    again = await voucher_service.validate_voucher(db_session, voucher.code, test_user.id, Decimal("100"))
    assert again.id == voucher.id


@pytest.mark.asyncio
async def test_reverse_voucher_is_noop_without_usage(db_session):
    # No voucher used by this booking → safe no-op.
    await voucher_service.reverse_voucher_for_booking(db_session, uuid.uuid4())


# ── #2 + #3: cancel_booking reverses redeemed points AND releases voucher ─────
@pytest.mark.asyncio
async def test_cancel_reverses_points_and_voucher(db_session, admin_user, test_user, test_room):
    test_user.loyalty_points = 1000
    await db_session.flush()

    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("200"), status=BookingStatus.confirmed.value)
    db_session.add(booking)
    await db_session.flush()

    item = BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type=BookingItemType.room.value,
        room_id=test_room.id, check_in=date.today() + timedelta(days=5),
        check_out=date.today() + timedelta(days=7), unit_price=Decimal("200"),
        subtotal=Decimal("200"), quantity=1, status=BookingItemStatus.confirmed.value,
    )
    db_session.add(item)
    await db_session.flush()

    voucher = await _mk_voucher(db_session, admin_user.id, code="CXL20", discount_value=20)
    await voucher_service.apply_voucher(db_session, booking, voucher, test_user.id)
    await loyalty_service.redeem_points(db_session, user_id=test_user.id, booking_id=booking.id, points=500)
    await db_session.refresh(test_user)
    assert test_user.loyalty_points == 500  # spent

    loaded = await _reload(db_session, booking.id)
    await cancel_booking(db_session, loaded, redis=None)

    await db_session.refresh(test_user)
    await db_session.refresh(voucher)
    assert test_user.loyalty_points == 1000  # redeemed points restored
    assert voucher.used_count == 0  # voucher released
    usage = (
        await db_session.execute(select(VoucherUsage).where(VoucherUsage.booking_id == booking.id))
    ).scalar_one_or_none()
    assert usage is None


# ── #1 + #2: LiteAPI room book failure → not confirmed, cancelled, refunded ───
@pytest_asyncio.fixture
async def liteapi_room_pending(db_session, test_user):
    """Single LiteAPI-room booking in 'pending' (prebooked, not yet booked),
    backed by a succeeded $200 payment."""
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("200"), status=BookingStatus.pending.value)
    db_session.add(booking)
    await db_session.flush()
    item = BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type=BookingItemType.room.value,
        liteapi_prebook_id="pre_test_1", check_in=date.today() + timedelta(days=10),
        check_out=date.today() + timedelta(days=12), unit_price=Decimal("200"),
        subtotal=Decimal("200"), quantity=1, status=BookingItemStatus.pending.value,
    )
    db_session.add(item)
    payment = Payment(
        id=uuid.uuid4(), booking_id=booking.id, provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_{booking.id.hex[:12]}", amount=Decimal("200"),
        currency="usd", status=PaymentStatus.succeeded.value,
    )
    db_session.add(payment)
    await db_session.flush()
    return booking, payment


@pytest.mark.asyncio
async def test_liteapi_book_failure_refunds_and_does_not_confirm(db_session, admin_user, test_user, liteapi_room_pending):
    booking, payment = liteapi_room_pending

    # Spend points + a voucher before confirming, to verify they're returned.
    test_user.loyalty_points = 1000
    await db_session.flush()
    voucher = await _mk_voucher(db_session, admin_user.id, code="FAIL20", discount_value=20)
    await voucher_service.apply_voucher(db_session, booking, voucher, test_user.id)
    await loyalty_service.redeem_points(db_session, user_id=test_user.id, booking_id=booking.id, points=300)

    loaded = await _reload(db_session, booking.id)
    with patch.object(booking_service.liteapi_service, "book", new=AsyncMock(side_effect=LiteAPIError(502, "supplier down"))), \
         patch.object(booking_service.email_service, "send_flight_booking_failed", new=AsyncMock(return_value=True)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_room_fail", 20000)
        _, outcome = await confirm_booking(db_session, loaded, guest_email="u@test.com")

    # #1: item NOT confirmed; booking cancelled; refund issued; failed entry is a room.
    assert outcome["status"] == "failed"
    assert outcome["refund"]["issued"] is True
    assert outcome["failed_items"][0]["type"] == "room"
    reloaded = await _reload(db_session, booking.id)
    assert reloaded.status == BookingStatus.cancelled.value
    assert reloaded.items[0].status == BookingItemStatus.cancelled.value
    assert reloaded.items[0].supplier_status == "BOOK_FAILED"

    # #2: redeemed points restored + voucher released.
    await db_session.refresh(test_user)
    await db_session.refresh(voucher)
    assert test_user.loyalty_points == 1000
    assert voucher.used_count == 0
    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.refunded.value


# ── #1 partial: one item confirms, a failed Viator tour is refunded pro-rata ──
@pytest.mark.asyncio
async def test_partial_failure_confirms_good_item_refunds_failed_tour(db_session, test_user, test_room):
    booking = Booking(id=uuid.uuid4(), user_id=test_user.id, total_price=Decimal("300"), status=BookingStatus.pending.value)
    db_session.add(booking)
    await db_session.flush()
    # Local room (will confirm) — $200 share.
    room_item = BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type=BookingItemType.room.value,
        room_id=test_room.id, check_in=date.today() + timedelta(days=3),
        check_out=date.today() + timedelta(days=5), unit_price=Decimal("200"),
        subtotal=Decimal("200"), quantity=1, status=BookingItemStatus.pending.value,
    )
    # Viator tour (will fail) — $100 share.
    tour_item = BookingItem(
        id=uuid.uuid4(), booking_id=booking.id, item_type=BookingItemType.tour.value,
        viator_product_code="V123", check_in=date.today() + timedelta(days=4),
        unit_price=Decimal("100"), subtotal=Decimal("100"), quantity=2,
        adults_count=2, status=BookingItemStatus.pending.value,
    )
    db_session.add_all([room_item, tour_item])
    payment = Payment(
        id=uuid.uuid4(), booking_id=booking.id, provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_{booking.id.hex[:12]}", amount=Decimal("300"),
        currency="usd", status=PaymentStatus.succeeded.value,
    )
    db_session.add(payment)
    await db_session.flush()

    loaded = await _reload(db_session, booking.id)
    with patch.object(booking_service.viator_service, "book_tour", new=AsyncMock(side_effect=ViatorError(500, "tour down"))), \
         patch.object(booking_service.email_service, "send_booking_partial_failure", new=AsyncMock(return_value=True)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_partial", 10000)
        _, outcome = await confirm_booking(db_session, loaded, guest_email="u@test.com")

    # Booking stays confirmed (room is good); tour is the failed item, refunded.
    assert outcome["status"] == "partial"
    assert outcome["refund"]["issued"] is True
    assert [f["type"] for f in outcome["failed_items"]] == ["tour"]
    assert len(outcome["confirmed_items"]) == 1
    reloaded = await _reload(db_session, booking.id)
    assert reloaded.status == BookingStatus.confirmed.value
    statuses = {i.item_type: i.status for i in reloaded.items}
    assert statuses["room"] == BookingItemStatus.confirmed.value
    assert statuses["tour"] != BookingItemStatus.confirmed.value  # failed tour not confirmed
