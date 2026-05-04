"""Stripe payment integration service."""
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.booking import Booking
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.user import User
from app.services import loyalty_service

stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_payment_intent(
    db: AsyncSession,
    user_id,
    booking_id=None,
    currency: str = "usd",
) -> tuple[Payment, str]:
    """Create a Stripe PaymentIntent and store the local Payment record."""
    if not booking_id:
        raise ValueError("Provide booking_id")

    booking = (await db.execute(select(Booking).where(Booking.id == booking_id))).scalar_one_or_none()
    if not booking:
        raise ValueError("Booking not found")
    if str(booking.user_id) != str(user_id):
        raise ValueError("Not your booking")
    amount_cents = int(float(booking.total_price) * 100)

    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        metadata={
            "booking_id": str(booking_id),
            "user_id": str(user_id),
        },
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


async def handle_webhook_event(db: AsyncSession, event: dict, redis=None) -> None:
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
            from app.services.booking_service import confirm_booking
            booking = (
                await db.execute(
                    select(Booking)
                    .options(selectinload(Booking.items))
                    .where(Booking.id == payment.booking_id)
                )
            ).scalar_one_or_none()
            if booking:
                user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
                fn = (user.full_name or "Guest").split(" ")[0] if user else "Guest"
                ln = " ".join((user.full_name or "Guest").split(" ")[1:]) or "Guest" if user else "Guest"
                email = user.email if user else "guest@example.com"
                await confirm_booking(db, booking, guest_first_name=fn, guest_last_name=ln, guest_email=email, redis=redis)

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


async def _award_loyalty_points(db: AsyncSession, user_id, booking_id, amount: float) -> None:
    """Award 1 loyalty point per $1 spent via the loyalty ledger."""
    pts = int(amount)
    if pts <= 0:
        return
    try:
        await loyalty_service.award_points(
            db,
            user_id=user_id,
            booking_id=booking_id,
            amount=pts,
            description=f"Earned {pts} pts from payment",
        )
    except loyalty_service.LoyaltyError:
        pass
