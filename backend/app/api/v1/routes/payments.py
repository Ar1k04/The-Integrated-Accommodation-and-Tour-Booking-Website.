import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import create_payment_intent, handle_webhook_event, refund_payment

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
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return payment


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

    await handle_webhook_event(db, event)
    return {"status": "ok"}


@router.delete("/{payment_id}", status_code=status.HTTP_200_OK)
async def refund(
    payment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    try:
        payment = await refund_payment(db, payment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"success": True, "data": PaymentResponse.model_validate(payment).model_dump()}
