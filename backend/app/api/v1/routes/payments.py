import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import create_payment_intent, handle_webhook_event, refund_payment


WEBHOOK_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


def _owns_payment(payment: Payment, user) -> bool:
    if user.role in ("admin", "superadmin"):
        return True
    booking = payment.booking
    return bool(booking and booking.user_id == user.id)


async def _load_payment_for_user(
    db: AsyncSession, payment_id: uuid.UUID, user
) -> Payment:
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.booking))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment or not _owns_payment(payment, user):
        # Return 404 (not 403) to avoid leaking existence of other users' payments.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    try:
        payment, client_secret = await create_payment_intent(
            db=db,
            user_id=current_user.id,
            booking_id=data.booking_id,
            currency=data.currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "success": True,
        "data": {
            "payment_id": str(payment.id),
            "client_secret": client_secret,
            "amount": float(payment.amount),
            "currency": payment.currency,
        },
    }


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    return await _load_payment_for_user(db, payment_id, current_user)


@router.post("/webhooks", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str, Header()],
):
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    # Idempotency: Stripe retries webhooks; reject duplicates by event id within a 7-day window.
    redis = request.app.state.redis
    key = f"stripe:webhook:{event['id']}"
    added = await redis.set(key, "1", ex=WEBHOOK_IDEMPOTENCY_TTL_SECONDS, nx=True)
    if not added:
        return {"status": "duplicate"}

    await handle_webhook_event(db, event)
    return {"status": "ok"}


@router.delete("/{payment_id}", status_code=status.HTTP_200_OK)
async def refund(
    payment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    payment = await _load_payment_for_user(db, payment_id, current_user)
    try:
        payment = await refund_payment(db, payment.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"success": True, "data": PaymentResponse.model_validate(payment).model_dump()}
