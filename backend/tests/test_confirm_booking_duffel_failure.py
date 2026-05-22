"""Tests for the Duffel silent-failure fix in confirm_booking().

Covers the scenarios documented in the audit plan:

1. Happy path — Duffel returns an order; booking confirmed, no refund.
2. Retryable transient failure resolves on retry — order confirmed, error
   blob cleared from passenger_details.
3. Retryable failure exhausts attempts — booking cancelled, Stripe refund
   issued, last_error persisted, failure email queued.
4. Permanent error (offer expired) skips retries — booking cancelled,
   Stripe refund issued, only ONE call to create_order.
5. Idempotency — re-calling confirm_booking after a terminal state returns
   a cached outcome from passenger_details, NO new Duffel/Stripe calls.

These tests pin the contract that came out of the diagnosis:
``BookingItem.status`` MUST NOT be confirmed when Duffel rejected the order.
"""
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking, FlightBookingStatus
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.services import booking_service
from app.services.booking_service import confirm_booking
from app.services.duffel_service import DuffelError


def _stripe_refund(refund_id: str, amount: int) -> MagicMock:
    obj = MagicMock()
    obj.id = refund_id
    obj.amount = amount
    obj.status = "succeeded"
    return obj


async def _reload_with_items(db_session, booking_id):
    """Re-fetch the booking + items + flight_booking after confirm_booking().
    confirm_booking internally calls db.refresh() which expires relationships,
    so test assertions need a fresh eager-loaded copy.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    return (await db_session.execute(
        select(Booking)
        .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
        .where(Booking.id == booking_id)
    )).scalar_one()


@pytest_asyncio.fixture
async def flight_booking_pending(db_session, test_user):
    """A single-item flight Booking sitting in 'pending' awaiting Duffel finalization,
    backed by a succeeded Stripe payment for $123.45.
    """
    booking = Booking(
        id=uuid.uuid4(),
        user_id=test_user.id,
        total_price=Decimal("123.45"),
        status=BookingStatus.pending.value,
    )
    db_session.add(booking)
    await db_session.flush()

    flight = FlightBooking(
        id=uuid.uuid4(),
        duffel_order_id=None,
        airline_name="Test Airways",
        flight_number="TA100",
        departure_airport="HAN",
        arrival_airport="SGN",
        departure_at=datetime.now(timezone.utc) + timedelta(days=30),
        arrival_at=datetime.now(timezone.utc) + timedelta(days=30, hours=2),
        passenger_name="Alice Doe",
        passenger_email="alice@example.com",
        base_amount=Decimal("123.45"),
        total_amount=Decimal("123.45"),
        currency="USD",
        status=FlightBookingStatus.pending.value,
        passenger_details={
            "offer_id": "off_test_123",
            "passengers": [{
                "first_name": "Alice", "last_name": "Doe",
                "email": "alice@example.com", "gender": "F",
                "born_on": "1990-01-01", "title": "ms",
            }],
        },
    )
    db_session.add(flight)
    await db_session.flush()

    item = BookingItem(
        id=uuid.uuid4(),
        booking_id=booking.id,
        item_type=BookingItemType.flight.value,
        flight_booking_id=flight.id,
        unit_price=Decimal("123.45"),
        subtotal=Decimal("123.45"),
        quantity=1,
        status=BookingItemStatus.pending.value,
    )
    db_session.add(item)
    await db_session.flush()

    payment = Payment(
        id=uuid.uuid4(),
        booking_id=booking.id,
        provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=f"pi_test_{booking.id.hex[:12]}",
        amount=Decimal("123.45"),
        currency="usd",
        status=PaymentStatus.succeeded.value,
    )
    db_session.add(payment)
    await db_session.flush()

    # Re-load with items relationship populated for confirm_booking.
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    loaded = (await db_session.execute(
        select(Booking)
        .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
        .where(Booking.id == booking.id)
    )).scalar_one()
    return loaded, payment


@pytest.mark.asyncio
async def test_happy_path_marks_confirmed(db_session, flight_booking_pending):
    booking, payment = flight_booking_pending

    async def fake_create_order(**_kwargs):
        return {
            "duffel_order_id": "ord_test_001",
            "duffel_booking_ref": "ABC123",
            "status": "confirmed",
            "total_amount": 123.45,
            "currency": "USD",
        }

    with patch.object(booking_service.duffel_service, "create_order", side_effect=fake_create_order) as mock_create, \
         patch.object(booking_service.email_service, "send_booking_confirmation", new=AsyncMock(return_value=True)):
        _, outcome = await confirm_booking(db_session, booking, guest_email="alice@example.com")

    assert outcome["status"] == "confirmed"
    assert outcome["failed_items"] == []
    assert outcome["refund"] is None
    assert mock_create.await_count == 1
    reloaded = await _reload_with_items(db_session, booking.id)
    item = reloaded.items[0]
    assert item.status == BookingItemStatus.confirmed.value
    assert item.flight_booking.duffel_order_id == "ord_test_001"
    assert "last_error" not in (item.flight_booking.passenger_details or {})


@pytest.mark.asyncio
async def test_retryable_resolves_on_second_attempt(db_session, flight_booking_pending):
    booking, _ = flight_booking_pending

    calls = {"n": 0}

    async def flaky_create_order(**_kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise DuffelError(503, "Service unavailable")
        return {
            "duffel_order_id": "ord_retry_ok",
            "duffel_booking_ref": "RETRY1",
            "status": "confirmed",
            "total_amount": 123.45,
            "currency": "USD",
        }

    # Speed up retry backoff for tests.
    async def fast_sleep(_):
        return None

    with patch.object(booking_service.duffel_service, "create_order", side_effect=flaky_create_order), \
         patch.object(booking_service.asyncio, "sleep", side_effect=fast_sleep), \
         patch.object(booking_service.email_service, "send_booking_confirmation", new=AsyncMock(return_value=True)):
        _, outcome = await confirm_booking(db_session, booking, guest_email="alice@example.com")

    assert outcome["status"] == "confirmed"
    assert calls["n"] == 2
    reloaded = await _reload_with_items(db_session, booking.id)
    flight = reloaded.items[0].flight_booking
    assert flight.duffel_order_id == "ord_retry_ok"
    # last_error from attempt 1 must be cleared after success.
    assert "last_error" not in (flight.passenger_details or {})


@pytest.mark.asyncio
async def test_retryable_all_attempts_fail_triggers_full_refund(db_session, flight_booking_pending):
    booking, payment = flight_booking_pending

    async def always_503(**_kwargs):
        raise DuffelError(503, "Still down")

    async def fast_sleep(_):
        return None

    with patch.object(booking_service.duffel_service, "create_order", side_effect=always_503) as mock_create, \
         patch.object(booking_service.asyncio, "sleep", side_effect=fast_sleep), \
         patch.object(booking_service.email_service, "send_flight_booking_failed", new=AsyncMock(return_value=True)) as mock_email, \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_fail_001", 12345)
        _, outcome = await confirm_booking(db_session, booking, guest_email="alice@example.com")

    # Three attempts before giving up.
    assert mock_create.await_count == 3
    assert outcome["status"] == "failed"
    assert outcome["refund"]["issued"] is True
    assert outcome["refund"]["stripe_refund_id"] == "re_fail_001"
    assert outcome["failed_items"][0]["error_code"] is None
    mock_email.assert_awaited_once()

    # Booking marked cancelled, item NOT confirmed, last_error persisted.
    assert booking.status == BookingStatus.cancelled.value
    item = booking.items[0]
    assert item.status == BookingItemStatus.cancelled.value
    last_err = (item.flight_booking.passenger_details or {}).get("last_error")
    assert last_err is not None
    assert last_err["status_code"] == 503
    assert last_err["attempts"] == 3

    # Payment refunded.
    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.refunded.value
    assert payment.stripe_refund_id == "re_fail_001"


@pytest.mark.asyncio
async def test_permanent_offer_expired_skips_retries(db_session, flight_booking_pending):
    booking, payment = flight_booking_pending

    async def expired_offer(**_kwargs):
        raise DuffelError(
            422,
            "This offer is no longer available",
            error_type="validation_error",
            error_code="offer_no_longer_available",
        )

    with patch.object(booking_service.duffel_service, "create_order", side_effect=expired_offer) as mock_create, \
         patch.object(booking_service.email_service, "send_flight_booking_failed", new=AsyncMock(return_value=True)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_expired_001", 12345)
        _, outcome = await confirm_booking(db_session, booking, guest_email="alice@example.com")

    # Permanent error → exactly one call, no retries.
    assert mock_create.await_count == 1
    assert outcome["status"] == "failed"
    assert outcome["failed_items"][0]["error_code"] == "offer_no_longer_available"
    # User-friendly message must not leak the raw Duffel internals.
    assert "search again" in outcome["failed_items"][0]["user_message"].lower()
    assert booking.status == BookingStatus.cancelled.value


@pytest.mark.asyncio
async def test_idempotent_recall_after_cancellation(db_session, flight_booking_pending):
    """A second invocation after the booking is already cancelled should NOT
    re-run Duffel or Stripe. The cached outcome is reconstructed from
    passenger_details.last_error.
    """
    booking, _ = flight_booking_pending

    async def fail_perm(**_kwargs):
        raise DuffelError(
            422, "Expired",
            error_type="validation_error",
            error_code="offer_no_longer_available",
        )

    with patch.object(booking_service.duffel_service, "create_order", side_effect=fail_perm) as mock_create, \
         patch.object(booking_service.email_service, "send_flight_booking_failed", new=AsyncMock(return_value=True)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_idem_001", 12345)
        # First pass — runs the full failure flow.
        await confirm_booking(db_session, booking, guest_email="alice@example.com")
        # Second pass — must short-circuit.
        _, outcome2 = await confirm_booking(db_session, booking, guest_email="alice@example.com")

    # create_order called only once (during first pass).
    assert mock_create.await_count == 1
    # Outcome reconstructed from persisted state.
    assert outcome2["status"] == "failed"
    assert outcome2["failed_items"][0]["error_code"] == "offer_no_longer_available"


@pytest.mark.asyncio
async def test_permanent_failure_persists_last_error_payload(db_session, flight_booking_pending):
    booking, _ = flight_booking_pending

    async def fail_perm(**_kwargs):
        raise DuffelError(
            422, "Bad pax",
            error_type="validation_error",
            error_code="passenger_data_invalid",
        )

    with patch.object(booking_service.duffel_service, "create_order", side_effect=fail_perm), \
         patch.object(booking_service.email_service, "send_flight_booking_failed", new=AsyncMock(return_value=True)), \
         patch("app.services.payment_service.stripe.Refund") as mock_refund:
        mock_refund.create.return_value = _stripe_refund("re_perm_001", 12345)
        await confirm_booking(db_session, booking, guest_email="alice@example.com")

    last_err = booking.items[0].flight_booking.passenger_details.get("last_error") or {}
    assert last_err["status_code"] == 422
    assert last_err["error_type"] == "validation_error"
    assert last_err["error_code"] == "passenger_data_invalid"
    assert last_err["offer_id"] == "off_test_123"
    assert last_err["passenger_count"] == 1
    assert last_err["currency"] == "USD"
    assert "occurred_at" in last_err
