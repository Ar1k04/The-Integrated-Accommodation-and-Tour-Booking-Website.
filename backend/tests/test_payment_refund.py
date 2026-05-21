"""Tests for refund_for_booking with Stripe SDK mocked.

Covers:
- Decimal precision: 19.99 → 1999 cents (not 1998)
- Full refund: status flips to 'refunded', stripe_refund_id stored
- Partial refund: status stays 'succeeded', refunded_amount tracks running total
- Repeated full refund: returns None instead of double-charging
- Non-Stripe payment (VNPay-only): returns None, never calls Stripe
- No payment at all: returns None
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

from app.models.booking import Booking
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.services.payment_service import _to_cents, refund_for_booking


def _stripe_refund(refund_id: str, amount: int) -> MagicMock:
    obj = MagicMock()
    obj.id = refund_id
    obj.amount = amount
    obj.status = "succeeded"
    return obj


@pytest_asyncio.fixture
async def booking_with_stripe_payment(db_session, test_user):
    """A confirmed booking with a succeeded Stripe payment for $100.00."""
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("100.00"),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()

    payment = Payment(
        id=uuid.uuid4(),
        booking_id=booking.id,
        provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_test_{booking.id.hex[:12]}",
        amount=Decimal("100.00"),
        currency="usd",
        status=PaymentStatus.succeeded.value,
    )
    db_session.add(payment)
    await db_session.flush()
    return booking, payment


def test_to_cents_no_truncation():
    """19.99 must round to 1999 cents, not truncate to 1998."""
    assert _to_cents(Decimal("19.99")) == 1999
    assert _to_cents("19.99") == 1999
    assert _to_cents(19.99) == 1999
    # Half-up rounding
    assert _to_cents("0.005") == 1
    assert _to_cents("0.004") == 0


@pytest.mark.asyncio
async def test_full_refund_marks_payment_refunded(db_session, booking_with_stripe_payment):
    booking, payment = booking_with_stripe_payment

    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_full_123", 10000)
        result = await refund_for_booking(db_session, booking.id)

    assert result is not None
    assert result.stripe_refund_id == "re_full_123"
    assert float(result.refunded_amount) == 100.00
    assert result.status == PaymentStatus.refunded.value

    # Stripe call inspected
    call = mock_refund.create.call_args
    assert call.kwargs["amount"] == 10000
    assert call.kwargs["payment_intent"] == payment.stripe_payment_intent_id
    assert call.kwargs["idempotency_key"] == f"refund-booking-{booking.id}-10000"


@pytest.mark.asyncio
async def test_partial_refund_keeps_payment_succeeded(db_session, booking_with_stripe_payment):
    booking, _ = booking_with_stripe_payment

    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_partial_456", 8000)
        result = await refund_for_booking(db_session, booking.id, refund_amount_usd=80.00)

    assert result is not None
    assert result.stripe_refund_id == "re_partial_456"
    assert float(result.refunded_amount) == 80.00
    # Status stays 'succeeded' — further partial refunds still allowed
    assert result.status == PaymentStatus.succeeded.value


@pytest.mark.asyncio
async def test_no_double_refund_after_full(db_session, booking_with_stripe_payment):
    booking, payment = booking_with_stripe_payment

    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_full_x", 10000)
        await refund_for_booking(db_session, booking.id)
        # Payment is now status='refunded' which excludes it from the lookup
        result2 = await refund_for_booking(db_session, booking.id)

    assert result2 is None
    assert mock_refund.create.call_count == 1


@pytest.mark.asyncio
async def test_vnpay_only_booking_returns_none(db_session, test_user):
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("50.00"),
        status="confirmed",
    )
    db_session.add(booking)
    await db_session.flush()

    vnpay = Payment(
        id=uuid.uuid4(),
        booking_id=booking.id,
        provider=PaymentProvider.vnpay.value,
        amount=Decimal("50.00"),
        currency="vnd",
        status=PaymentStatus.succeeded.value,
    )
    db_session.add(vnpay)
    await db_session.flush()

    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        result = await refund_for_booking(db_session, booking.id)

    assert result is None
    mock_refund.create.assert_not_called()


@pytest.mark.asyncio
async def test_booking_without_payment_returns_none(db_session, test_user):
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("25.00"),
        status="pending",
    )
    db_session.add(booking)
    await db_session.flush()

    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        result = await refund_for_booking(db_session, booking.id)

    assert result is None
    mock_refund.create.assert_not_called()


@pytest.mark.asyncio
async def test_refund_amount_capped_at_remaining(db_session, booking_with_stripe_payment):
    """Asking to refund more than the remaining balance refunds only what's left."""
    booking, payment = booking_with_stripe_payment

    # First refund 70 of 100
    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_p1", 7000)
        await refund_for_booking(db_session, booking.id, refund_amount_usd=70.00)

    # Then ask for 80 more — only 30 remains, so Stripe is called with 3000 cents
    with patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_p2", 3000)
        result = await refund_for_booking(db_session, booking.id, refund_amount_usd=80.00)

    assert result is not None
    assert mock_refund.create.call_args.kwargs["amount"] == 3000
    assert float(result.refunded_amount) == 100.00
    assert result.status == PaymentStatus.refunded.value
