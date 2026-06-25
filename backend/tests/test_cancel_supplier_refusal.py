"""Regression tests cho fix 2026-06-25: cancel_booking nhánh flight/Viator phải
RAISE khi supplier từ chối/lỗi (không im lặng flip cancelled + nuốt refund).

Trước fix: Duffel/Viator trả None → vẫn flip status=cancelled, refund=None, no error
→ (1) desync trạng thái khi máy bay đã bay; (2) lỗi tạm thời → mất refund oan.
Sau fix: trả None (hoặc Viator status REJECTED) → raise SupplierCancelError, không
đổi gì (route map sang 409, rollback). Mirror đúng nhánh LiteAPI.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking, FlightBookingStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.services import booking_service
from app.services.booking_service import SupplierCancelError, cancel_booking


def _stripe_refund(refund_id: str, amount_cents: int) -> MagicMock:
    obj = MagicMock()
    obj.id = refund_id
    obj.amount = amount_cents
    obj.status = "succeeded"
    return obj


async def _reload(db, booking_id):
    return (
        await db.execute(
            select(Booking)
            .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
            .where(Booking.id == booking_id)
        )
    ).scalar_one()


async def _mk_confirmed_flight(db, user_id, *, duffel_order_id="ord_test123"):
    """A confirmed single-item flight booking backed by a succeeded payment."""
    booking = Booking(
        id=uuid.uuid4(), user_id=user_id,
        total_price=Decimal("123.45"), status=BookingStatus.confirmed.value,
    )
    db.add(booking)
    await db.flush()

    flight = FlightBooking(
        id=uuid.uuid4(),
        duffel_order_id=duffel_order_id,
        airline_name="Test Airways", flight_number="TA100",
        departure_airport="HAN", arrival_airport="SGN",
        departure_at=datetime.now(timezone.utc) + timedelta(days=30),
        arrival_at=datetime.now(timezone.utc) + timedelta(days=30, hours=2),
        passenger_name="Alice Doe", passenger_email="alice@example.com",
        base_amount=Decimal("123.45"), total_amount=Decimal("123.45"),
        currency="USD", status=FlightBookingStatus.confirmed.value,
        passenger_details={},
    )
    db.add(flight)
    await db.flush()

    db.add(BookingItem(
        id=uuid.uuid4(), booking_id=booking.id,
        item_type=BookingItemType.flight.value, flight_booking_id=flight.id,
        unit_price=Decimal("123.45"), subtotal=Decimal("123.45"),
        quantity=1, status=BookingItemStatus.confirmed.value,
    ))
    db.add(Payment(
        id=uuid.uuid4(), booking_id=booking.id, provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_{booking.id.hex[:12]}", amount=Decimal("123.45"),
        currency="usd", status=PaymentStatus.succeeded.value,
    ))
    await db.flush()
    return await _reload(db, booking.id)


async def _mk_confirmed_viator(db, user_id, *, viator_ref="VIATOR_REF_1"):
    """A confirmed single-item Viator tour booking backed by a succeeded payment."""
    booking = Booking(
        id=uuid.uuid4(), user_id=user_id,
        total_price=Decimal("80"), status=BookingStatus.confirmed.value,
    )
    db.add(booking)
    await db.flush()

    db.add(BookingItem(
        id=uuid.uuid4(), booking_id=booking.id,
        item_type=BookingItemType.tour.value,
        viator_product_code="PROD123", viator_booking_ref=viator_ref,
        unit_price=Decimal("80"), subtotal=Decimal("80"),
        quantity=1, status=BookingItemStatus.confirmed.value,
    ))
    db.add(Payment(
        id=uuid.uuid4(), booking_id=booking.id, provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_{booking.id.hex[:12]}", amount=Decimal("80"),
        currency="usd", status=PaymentStatus.succeeded.value,
    ))
    await db.flush()
    return await _reload(db, booking.id)


# ── Flight: Duffel refuses/fails (None) → raise, no flip, no refund ────────────
@pytest.mark.asyncio
async def test_flight_cancel_duffel_none_raises_and_keeps_state(db_session, test_user):
    booking = await _mk_confirmed_flight(db_session, test_user.id)
    flight = booking.items[0].flight_booking

    with patch.object(booking_service.duffel_service, "cancel_order",
                      new=AsyncMock(return_value=None)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        with pytest.raises(SupplierCancelError):
            await cancel_booking(db_session, booking, redis=None)

    # Flight item NOT flipped to cancelled, and no Stripe refund was attempted.
    assert flight.status != "cancelled"
    assert booking.items[0].status != BookingItemStatus.cancelled.value
    mock_refund.create.assert_not_called()


# ── Flight: Duffel cancels with a refund → happy path still works ─────────────
@pytest.mark.asyncio
async def test_flight_cancel_duffel_success_cancels_and_refunds(db_session, test_user):
    booking = await _mk_confirmed_flight(db_session, test_user.id)
    flight = booking.items[0].flight_booking

    with patch.object(
        booking_service.duffel_service, "cancel_order",
        new=AsyncMock(return_value={"status": "cancelled", "refund_amount": 123.45, "currency": "USD"}),
    ), patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_flight_ok", 12345)
        _booking, results, refund_info = await cancel_booking(db_session, booking, redis=None)

    assert flight.status == "cancelled"
    assert booking.items[0].status == BookingItemStatus.cancelled.value
    mock_refund.create.assert_called_once()  # refundable fare → refund issued
    assert refund_info["non_refundable"] is False


# ── Viator: transport/auth error (None) → raise, no refund ────────────────────
@pytest.mark.asyncio
async def test_viator_cancel_none_raises(db_session, test_user):
    booking = await _mk_confirmed_viator(db_session, test_user.id)

    with patch.object(booking_service.viator_service, "cancel_booking",
                      new=AsyncMock(return_value=None)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        with pytest.raises(SupplierCancelError):
            await cancel_booking(db_session, booking, redis=None)

    assert booking.items[0].status != BookingItemStatus.cancelled.value
    mock_refund.create.assert_not_called()


# ── Viator: explicit REJECTED → raise, no refund ──────────────────────────────
@pytest.mark.asyncio
async def test_viator_cancel_rejected_raises(db_session, test_user):
    booking = await _mk_confirmed_viator(db_session, test_user.id)

    with patch.object(
        booking_service.viator_service, "cancel_booking",
        new=AsyncMock(return_value={"status": "REJECTED", "refund_amount": None, "currency": None}),
    ), patch("app.services.payment_service.stripe.Refund") as mock_refund:
        with pytest.raises(SupplierCancelError):
            await cancel_booking(db_session, booking, redis=None)

    assert booking.items[0].status != BookingItemStatus.cancelled.value
    mock_refund.create.assert_not_called()
