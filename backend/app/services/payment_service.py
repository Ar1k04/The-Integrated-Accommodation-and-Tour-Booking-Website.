"""Stripe payment integration service."""
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.payment import Payment, PaymentStatus
from app.models.tour_booking import TourBooking
from app.models.user import User

stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_payment_intent(
    db: AsyncSession,
    user_id,
    booking_id=None,
    tour_booking_id=None,
    currency: str = "usd",
) -> tuple[Payment, str]:
    """Create a Stripe PaymentIntent and store the local Payment record."""
    if not booking_id and not tour_booking_id:
        raise ValueError("Provide either booking_id or tour_booking_id")

    amount_cents: int = 0

    if booking_id:
        booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
        if not booking:
            raise ValueError("Booking not found")
        if str(booking.user_id) != str(user_id):
            raise ValueError("Not your booking")
        amount_cents = int(float(booking.total_price) * 100)

    if tour_booking_id:
        tb = (await db.execute(select(TourBooking).where(TourBooking.id == tour_booking_id))).scalar_one_or_none()
        if not tb:
            raise ValueError("Tour booking not found")
        if str(tb.user_id) != str(user_id):
            raise ValueError("Not your booking")
        amount_cents = int(float(tb.total_price) * 100)

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        metadata={
            "booking_id": str(booking_id) if booking_id else "",
            "tour_booking_id": str(tour_booking_id) if tour_booking_id else "",
            "user_id": str(user_id),
        },
    )

    payment = Payment(
        booking_id=booking_id,
        stripe_payment_intent_id=intent.id,
        amount=amount_cents / 100,
        currency=currency,
        status=PaymentStatus.pending.value,
    )
    db.add(payment)
    await db.flush()
    await db.refresh(payment)

    return payment, intent.client_secret


async def handle_webhook_event(db: AsyncSession, event: dict) -> None:
    """Process Stripe webhook events."""
    event_type = event["type"]
    data_object = event["data"]["object"]
    pi_id = data_object.get("id")

    payment = (
        await db.execute(select(Payment).where(Payment.stripe_payment_intent_id == pi_id))
    ).scalar_one_or_none()

    if not payment:
        return

    if event_type == "payment_intent.succeeded":
        payment.status = PaymentStatus.succeeded.value

        if payment.booking_id:
            booking = (await db.execute(select(Booking).where(Booking.id == payment.booking_id))).scalar_one_or_none()
            if booking:
                booking.status = "confirmed"
                await _award_loyalty_points(db, booking.user_id, float(payment.amount))

    elif event_type == "payment_intent.payment_failed":
        payment.status = PaymentStatus.failed.value

    await db.flush()


async def refund_payment(db: AsyncSession, payment_id) -> Payment:
    """Issue a full refund via Stripe."""
    payment = (await db.execute(select(Payment).where(Payment.id == payment_id))).scalar_one_or_none()
    if not payment:
        raise ValueError("Payment not found")

    if payment.status != PaymentStatus.succeeded.value:
        raise ValueError("Can only refund succeeded payments")

    stripe.Refund.create(payment_intent=payment.stripe_payment_intent_id)
    payment.status = PaymentStatus.refunded.value

    if payment.booking_id:
        booking = (await db.execute(select(Booking).where(Booking.id == payment.booking_id))).scalar_one_or_none()
        if booking:
            booking.status = "cancelled"

    await db.flush()
    await db.refresh(payment)
    return payment


async def _award_loyalty_points(db: AsyncSession, user_id, amount: float) -> None:
    """Award 1 loyalty point per $1 spent."""
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user:
        user.loyalty_points += int(amount)
