"""Stripe payment integration service."""
import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.booking import Booking
from app.models.booking_item import BookingItem, BookingItemType
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.user import User

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY
# Pin the Stripe API version so Stripe rolling out a breaking change
# can't silently affect this integration.
stripe.api_version = settings.STRIPE_API_VERSION


class OfferExpiredError(ValueError):
    """The Duffel offer is no longer valid — payment must not proceed."""

    def __init__(self, message: str, *, offer_id: str | None = None):
        super().__init__(message)
        self.offer_id = offer_id


async def _validate_flight_offers_alive(booking: Booking) -> None:
    """Re-fetch every Duffel offer on the booking right before we charge the
    card. If any offer is expired (or expires within 60s), abort.

    Without this guard, we'd take payment, then fail at create_order, then
    auto-refund — wasting the customer's time and a Stripe roundtrip.

    Imported lazily to keep payment_service free of supplier deps at module
    load (search/flights flow doesn't need Stripe at import).
    """
    from app.services import duffel_service
    from app.services.duffel_service import DuffelError
    from datetime import datetime, timezone

    flight_items = [
        item for item in (booking.items or [])
        if item.item_type == BookingItemType.flight.value and item.flight_booking
    ]
    for item in flight_items:
        flight = item.flight_booking
        offer_id = (flight.passenger_details or {}).get("offer_id")
        if not offer_id:
            # No offer to validate — order creation will fail with a clear
            # error later, but no need to block payment now.
            continue
        try:
            offer = await duffel_service.get_offer(offer_id)
        except DuffelError as exc:
            if exc.error_code == "offer_no_longer_available" or exc.status_code == 404:
                raise OfferExpiredError(
                    "Flight offer is no longer available. Please search again.",
                    offer_id=offer_id,
                )
            # Other transient errors → let payment proceed; create_order will
            # retry. Logging at warning level so this is still visible.
            logger.warning(
                "Pre-payment offer check failed for %s (%s): %s",
                offer_id, exc.status_code, exc.message,
            )
            continue
        expires_iso = offer.get("expires_at")
        if expires_iso:
            try:
                expires_at = datetime.fromisoformat(expires_iso.replace("Z", "+00:00"))
                seconds_left = (expires_at - datetime.now(timezone.utc)).total_seconds()
                # 90s buffer: PaymentIntent creation → user-side Stripe confirm
                # round-trip → backend Duffel create_order typically takes
                # 15-40 s; 90 s leaves headroom for slow connections.
                if seconds_left < 90:
                    raise OfferExpiredError(
                        "Flight offer is about to expire. Please search again.",
                        offer_id=offer_id,
                    )
            except OfferExpiredError:
                raise
            except (TypeError, ValueError):
                # Bad timestamp — don't block payment over a parsing issue.
                pass


def _to_cents(amount) -> int:
    """USD float/Decimal/str → integer cents with banker-safe rounding.

    `int(float(x) * 100)` truncates (19.99 → 1998); use Decimal to round.
    """
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


async def get_or_create_stripe_customer(user: User) -> str | None:
    """Return user's Stripe customer id, creating one if missing.

    Failures are non-fatal — Stripe outage should not block payment creation.
    """
    if not user:
        return None
    if user.stripe_customer_id:
        return user.stripe_customer_id
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or None,
            metadata={"user_id": str(user.id)},
            idempotency_key=f"user-{user.id}-customer",
        )
        user.stripe_customer_id = customer.id
        return customer.id
    except stripe.error.StripeError as exc:
        logger.warning("Stripe Customer create failed for user %s: %s", user.id, exc)
        return None


async def create_payment_intent(
    db: AsyncSession,
    user_id,
    booking_id=None,
    currency: str = "usd",
) -> tuple[Payment, str]:
    """Create a Stripe PaymentIntent and store the local Payment record.

    For flight bookings: refuses to take payment if the Duffel offer has
    already expired (or is < 60s from expiry) — preventing the charge-then-
    refund roundtrip when we know booking is doomed.
    """
    if not booking_id:
        raise ValueError("Provide booking_id")

    booking = (
        await db.execute(
            select(Booking)
            .options(selectinload(Booking.items).selectinload(BookingItem.flight_booking))
            .where(Booking.id == booking_id)
        )
    ).scalar_one_or_none()
    if not booking:
        raise ValueError("Booking not found")
    if str(booking.user_id) != str(user_id):
        raise ValueError("Not your booking")

    # Fail-fast: if any flight item's Duffel offer has expired, don't charge
    # the card. The customer needs to re-search before they pay.
    await _validate_flight_offers_alive(booking)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    amount_cents = _to_cents(booking.total_price)
    customer_id = await get_or_create_stripe_customer(user) if user else None

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        # Card-only checkout. Apple Pay / Google Pay still show automatically
        # when the browser supports them — they ride on the card pipeline.
        payment_method_types=["card"],
        description=f"Booking {booking_id}",
        receipt_email=user.email if user else None,
        customer=customer_id,
        metadata={
            "booking_id": str(booking_id),
            "user_id": str(user_id),
        },
        idempotency_key=f"booking-{booking_id}-intent",
    )

    payment = Payment(
        booking_id=booking_id,
        provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=intent.id,
        amount=amount_cents / 100,
        currency=currency,
        status=PaymentStatus.pending.value,
    )
    db.add(payment)
    await db.flush()
    await db.refresh(payment)

    return payment, intent.client_secret


async def _confirm_succeeded_payment(db: AsyncSession, payment: Payment, redis=None) -> None:
    """Shared post-success logic: mark payment, confirm booking, send email."""
    from app.services.booking_service import confirm_booking

    payment.status = PaymentStatus.succeeded.value
    if not payment.booking_id:
        return

    from app.models.booking_item import BookingItem  # local import to avoid cycle
    booking = (
        await db.execute(
            select(Booking)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.flight_booking)
            )
            .where(Booking.id == payment.booking_id)
        )
    ).scalar_one_or_none()
    if not booking:
        return

    user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
    fn = (user.full_name or "Guest").split(" ")[0] if user else "Guest"
    ln = " ".join((user.full_name or "Guest").split(" ")[1:]) or "Guest" if user else "Guest"
    email = user.email if user else "guest@example.com"
    phone = user.phone if user and user.phone else None
    await confirm_booking(
        db, booking,
        guest_first_name=fn, guest_last_name=ln,
        guest_email=email, guest_phone=phone, redis=redis,
    )


async def handle_webhook_event(db: AsyncSession, event: dict, redis=None) -> None:
    """Process Stripe webhook events.

    Handles:
      payment_intent.succeeded   — confirm booking + send email
      payment_intent.payment_failed — record decline diagnostics
      payment_intent.canceled    — release the booking back to pending/cancelled
      charge.refunded            — sync refund total (in case admin refunded via Dashboard)
      refund.updated             — handle async refund failures
      charge.dispute.created     — chargeback alert
    """
    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "charge.dispute.created":
        await _handle_dispute_created(db, data_object)
        return

    if event_type in ("charge.refunded", "refund.updated"):
        await _handle_refund_event(db, event_type, data_object)
        return

    pi_id = data_object.get("id")
    if event_type.startswith("payment_intent."):
        # Look up our Payment by the PaymentIntent id
        payment = (
            await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id))
        ).scalar_one_or_none()
        if not payment:
            logger.info("Stripe webhook %s — no local Payment for %s, skipping", event_type, pi_id)
            return

        if event_type == "payment_intent.succeeded":
            if payment.status != PaymentStatus.succeeded.value:
                await _confirm_succeeded_payment(db, payment, redis=redis)

        elif event_type == "payment_intent.payment_failed":
            payment.status = PaymentStatus.failed.value
            err = data_object.get("last_payment_error") or {}
            payment.failure_code = err.get("code")
            payment.decline_code = err.get("decline_code")
            payment.failure_message = err.get("message")

        elif event_type == "payment_intent.canceled":
            payment.status = PaymentStatus.failed.value
            if payment.booking_id:
                booking = (
                    await db.execute(select(Booking).where(Booking.id == payment.booking_id))
                ).scalar_one_or_none()
                if booking and booking.status == "pending":
                    booking.status = "cancelled"

    await db.flush()


async def _handle_refund_event(db: AsyncSession, event_type: str, refund_or_charge: dict) -> None:
    """Sync local Payment with refund state from Stripe.

    `charge.refunded` carries the full Charge with `refunds.data[]`.
    `refund.updated` carries the Refund directly.
    """
    if event_type == "charge.refunded":
        pi_id = refund_or_charge.get("payment_intent")
        refunds = (refund_or_charge.get("refunds") or {}).get("data") or []
        latest = refunds[-1] if refunds else None
        refund_id = latest.get("id") if latest else None
        refund_status = latest.get("status") if latest else None
        total_refunded_cents = refund_or_charge.get("amount_refunded") or 0
    else:  # refund.updated
        refund_id = refund_or_charge.get("id")
        refund_status = refund_or_charge.get("status")
        pi_id = refund_or_charge.get("payment_intent")
        # `amount_refunded` on the charge is authoritative; fetch it on demand if needed
        total_refunded_cents = refund_or_charge.get("amount") or 0

    if not pi_id:
        return

    payment = (
        await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id))
    ).scalar_one_or_none()
    if not payment:
        return

    if refund_id and not payment.stripe_refund_id:
        payment.stripe_refund_id = refund_id

    if event_type == "refund.updated" and refund_status == "failed":
        # Async refund failure (e.g., closed destination card).
        # Roll the payment back so an admin can retry, and alert.
        payment.status = PaymentStatus.succeeded.value
        payment.refunded_amount = Decimal("0")
        logger.error(
            "Stripe refund failed for payment %s (refund=%s) — manual retry required",
            payment.id, refund_id,
        )
        # Best-effort admin alert; do not fail the webhook on email errors.
        try:
            from app.services import email_service
            await email_service.send_admin_alert(
                subject="Stripe refund failed",
                body=(
                    f"Refund {refund_id} for payment {payment.id} "
                    f"(booking {payment.booking_id}) failed. Retry via admin endpoint."
                ),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Admin alert for failed refund could not be sent: %s", exc)
        await db.flush()
        return

    # Successful / pending refund — sync the cumulative refunded amount.
    if total_refunded_cents:
        payment.refunded_amount = Decimal(total_refunded_cents) / Decimal(100)
        full_cents = _to_cents(payment.amount)
        if total_refunded_cents >= full_cents:
            payment.status = PaymentStatus.refunded.value
    await db.flush()


async def _handle_dispute_created(db: AsyncSession, dispute: dict) -> None:
    """Log + alert on a chargeback. We don't auto-respond; admin handles evidence."""
    pi_id = dispute.get("payment_intent")
    charge_id = dispute.get("charge")
    reason = dispute.get("reason")
    amount_cents = dispute.get("amount") or 0

    payment = None
    if pi_id:
        payment = (
            await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id))
        ).scalar_one_or_none()

    logger.error(
        "Stripe dispute created: charge=%s pi=%s reason=%s amount=%.2f booking=%s",
        charge_id, pi_id, reason, amount_cents / 100,
        payment.booking_id if payment else None,
    )
    try:
        from app.services import email_service
        await email_service.send_admin_alert(
            subject=f"Stripe dispute ({reason}) — booking {payment.booking_id if payment else 'unknown'}",
            body=(
                f"Charge {charge_id} (PaymentIntent {pi_id}) was disputed for "
                f"${amount_cents / 100:.2f}. Reason: {reason}. Respond via Stripe Dashboard."
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Admin alert for dispute could not be sent: %s", exc)


async def refund_for_booking(
    db: AsyncSession,
    booking_id,
    refund_amount_usd: float | Decimal | None = None,
    reason: str = "requested_by_customer",
) -> Payment | None:
    """Issue a Stripe refund for a booking's succeeded payment.

    - `refund_amount_usd=None` → full remaining refund.
    - Returns the updated Payment, or None if no eligible payment exists
      (no Stripe payment / not succeeded / fully refunded already).
    - Idempotent via Stripe `idempotency_key` on (booking_id, amount).
    - Stores the resulting `re_xxx` on Payment.stripe_refund_id.
    - Sets Payment.status to 'refunded' once cumulative refunded matches the charge;
      otherwise leaves it at 'succeeded' (partial refund — further refunds still allowed).
    """
    result = await db.execute(
        select(Payment)
        .where(
            Payment.booking_id == booking_id,
            Payment.provider == PaymentProvider.stripe.value,
            Payment.status == PaymentStatus.succeeded.value,
        )
        .order_by(Payment.created_at.desc())
    )
    payment = result.scalars().first()
    if not payment or not payment.stripe_payment_intent_id:
        return None

    full_cents = _to_cents(payment.amount)
    already_refunded_cents = _to_cents(payment.refunded_amount or 0)
    remaining_cents = full_cents - already_refunded_cents
    if remaining_cents <= 0:
        return None

    if refund_amount_usd is None:
        refund_cents = remaining_cents
    else:
        refund_cents = min(_to_cents(refund_amount_usd), remaining_cents)

    if refund_cents <= 0:
        return None

    refund = stripe.Refund.create(
        payment_intent=payment.stripe_payment_intent_id,
        amount=refund_cents,
        reason=reason,
        metadata={"booking_id": str(booking_id), "payment_id": str(payment.id)},
        idempotency_key=f"refund-booking-{booking_id}-{refund_cents}",
    )

    payment.stripe_refund_id = refund.id
    payment.refunded_amount = (Decimal(already_refunded_cents + refund_cents) / Decimal(100))
    if (already_refunded_cents + refund_cents) >= full_cents:
        payment.status = PaymentStatus.refunded.value

    await db.flush()
    await db.refresh(payment)
    return payment


async def create_change_payment_intent(
    db: AsyncSession,
    *,
    user_id,
    booking_id,
    order_change_id: str,
    amount_usd: float | Decimal,
    currency: str = "usd",
) -> tuple[str, str, int, str]:
    """Stripe PaymentIntent for the *difference* on a Duffel order change.

    Returns ``(payment_intent_id, client_secret, amount_cents, currency)``.

    Stores a standalone ``Payment`` row linked to the same booking with
    metadata ``change_for=order_change_id`` so refund/audit tooling can
    correlate. We deliberately do NOT extend the original Payment row —
    refund accounting stays cleaner this way (each ancillary or change has
    its own Stripe object).
    """
    booking = (
        await db.execute(select(Booking).where(Booking.id == booking_id))
    ).scalar_one_or_none()
    if not booking:
        raise ValueError("Booking not found")
    if str(booking.user_id) != str(user_id):
        raise ValueError("Not your booking")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    amount_cents = _to_cents(amount_usd)
    if amount_cents <= 0:
        raise ValueError("amount_usd must be positive for a charge")
    customer_id = await get_or_create_stripe_customer(user) if user else None

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency.lower(),
        payment_method_types=["card"],
        description=f"Booking {booking_id} change {order_change_id}",
        receipt_email=user.email if user else None,
        customer=customer_id,
        metadata={
            "booking_id": str(booking_id),
            "user_id": str(user_id),
            "order_change_id": order_change_id,
            "purpose": "order_change",
        },
        idempotency_key=f"change-{order_change_id}-intent",
    )

    payment = Payment(
        booking_id=booking_id,
        provider=PaymentProvider.stripe.value,
        stripe_payment_intent_id=intent.id,
        amount=amount_cents / 100,
        currency=currency,
        status=PaymentStatus.pending.value,
    )
    db.add(payment)
    await db.flush()
    return intent.id, intent.client_secret, amount_cents, currency.lower()


async def refund_payment(db: AsyncSession, payment_id) -> Payment:
    """Admin endpoint: issue a full refund for a specific Payment record."""
    payment = (await db.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not payment:
        raise ValueError("Payment not found")

    if payment.provider != PaymentProvider.stripe.value:
        raise ValueError("Only Stripe payments can be refunded here")
    if payment.status != PaymentStatus.succeeded.value:
        raise ValueError("Can only refund succeeded payments")

    refunded = await refund_for_booking(db, payment.booking_id, refund_amount_usd=None)
    if not refunded:
        raise ValueError("Nothing to refund")

    if refunded.booking_id:
        booking = (
            await db.execute(select(Booking).where(Booking.id == refunded.booking_id))
        ).scalar_one_or_none()
        if booking and booking.status != "cancelled":
            booking.status = "cancelled"
            await db.flush()

    return refunded
