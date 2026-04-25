import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

from app.core.config import settings
from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.schemas.payment import PaymentCreate, PaymentResponse, VnpayCreateRequest
from app.services import vnpay_service
from app.services.payment_service import (
    _award_loyalty_points,
    create_payment_intent,
    handle_webhook_event,
    refund_payment,
)


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


# ─── VNPay ────────────────────────────────────────────────────────────────────

@router.post("/vnpay/create", status_code=status.HTTP_201_CREATED)
async def create_vnpay_payment(
    data: VnpayCreateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Create a VNPay payment URL for a booking."""
    booking = (
        await db.execute(select(Booking).where(Booking.id == data.booking_id))
    ).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if str(booking.user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    amount_vnd = int(float(booking.total_price) * vnpay_service.USD_TO_VND)
    if amount_vnd <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid booking amount")

    client_ip = request.client.host if request.client else "127.0.0.1"
    payment_url = vnpay_service.create_payment_url(
        booking_id=str(booking.id),
        amount_vnd=amount_vnd,
        return_url=data.return_url,
        client_ip=client_ip,
        order_info=f"BookingPayment{str(booking.id).replace('-', '')[:12]}",
    )

    payment = Payment(
        booking_id=booking.id,
        provider=PaymentProvider.vnpay.value,
        amount=float(booking.total_price),
        currency="vnd",
        status=PaymentStatus.pending.value,
    )
    db.add(payment)
    await db.flush()

    return {
        "success": True,
        "data": {
            "payment_url": payment_url,
            "payment_id": str(payment.id),
            "amount_vnd": amount_vnd,
        },
    }


@router.get("/vnpay/return")
async def vnpay_return(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Verify VNPay return params (user redirect) and update booking status.
    Called by the frontend after VNPay redirects the user back.
    """
    params = dict(request.query_params)
    is_valid, cleaned = vnpay_service.verify_return_params(params)

    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid VNPay signature")

    booking_id = cleaned.get("vnp_TxnRef")
    response_code = cleaned.get("vnp_ResponseCode", "")
    txn_no = cleaned.get("vnp_TransactionNo", "")

    booking = (
        await db.execute(select(Booking).where(Booking.id == booking_id))
    ).scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    # Find the pending VNPay payment for this booking
    payment = (
        await db.execute(
            select(Payment)
            .where(
                Payment.booking_id == booking.id,
                Payment.provider == PaymentProvider.vnpay.value,
                Payment.status == PaymentStatus.pending.value,
            )
            .order_by(Payment.created_at.desc())
        )
    ).scalar_one_or_none()

    if response_code == "00":
        from app.services.booking_service import confirm_booking
        if payment:
            payment.status = PaymentStatus.succeeded.value
            payment.vnpay_transaction_id = txn_no
        booking_with_items = (
            await db.execute(
                select(Booking)
                .options(selectinload(Booking.items))
                .where(Booking.id == booking.id)
            )
        ).scalar_one()
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        fn = (user.full_name or "Guest").split(" ")[0] if user else "Guest"
        ln = " ".join((user.full_name or "Guest").split(" ")[1:]) or "Guest" if user else "Guest"
        email = user.email if user else "guest@example.com"
        await confirm_booking(db, booking_with_items, guest_first_name=fn, guest_last_name=ln, guest_email=email)
        await db.flush()
        return {
            "success": True,
            "data": {"booking_id": booking_id, "status": "confirmed"},
            "message": "Payment successful",
        }
    else:
        if payment:
            payment.status = PaymentStatus.failed.value
        await db.flush()
        return {
            "success": False,
            "data": {"booking_id": booking_id, "status": "failed"},
            "message": "Payment failed or cancelled",
        }


@router.post("/vnpay/ipn")
async def vnpay_ipn(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Server-to-server IPN callback from VNPay.
    Must return {"RspCode": "00"} to acknowledge receipt.
    """
    params = dict(request.query_params)
    is_valid, cleaned = vnpay_service.verify_return_params(params)

    if not is_valid:
        return {"RspCode": "97", "Message": "Invalid checksum"}

    booking_id = cleaned.get("vnp_TxnRef")
    response_code = cleaned.get("vnp_ResponseCode", "")
    txn_no = cleaned.get("vnp_TransactionNo", "")

    booking = (
        await db.execute(select(Booking).where(Booking.id == booking_id))
    ).scalar_one_or_none()
    if not booking:
        return {"RspCode": "01", "Message": "Booking not found"}

    # Idempotency: skip if already processed
    existing = (
        await db.execute(
            select(Payment).where(Payment.vnpay_transaction_id == txn_no)
        )
    ).scalar_one_or_none()
    if existing:
        return {"RspCode": "00", "Message": "Success"}

    payment = (
        await db.execute(
            select(Payment)
            .where(
                Payment.booking_id == booking.id,
                Payment.provider == PaymentProvider.vnpay.value,
                Payment.status == PaymentStatus.pending.value,
            )
            .order_by(Payment.created_at.desc())
        )
    ).scalar_one_or_none()

    if response_code == "00":
        from app.services.booking_service import confirm_booking
        if payment:
            payment.status = PaymentStatus.succeeded.value
            payment.vnpay_transaction_id = txn_no
        booking_with_items = (
            await db.execute(
                select(Booking)
                .options(selectinload(Booking.items))
                .where(Booking.id == booking.id)
            )
        ).scalar_one()
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        fn = (user.full_name or "Guest").split(" ")[0] if user else "Guest"
        ln = " ".join((user.full_name or "Guest").split(" ")[1:]) or "Guest" if user else "Guest"
        email = user.email if user else "guest@example.com"
        await confirm_booking(db, booking_with_items, guest_first_name=fn, guest_last_name=ln, guest_email=email)
        await db.flush()
        return {"RspCode": "00", "Message": "Success"}
    else:
        if payment:
            payment.status = PaymentStatus.failed.value
        await db.flush()
        return {"RspCode": "01", "Message": "Payment failed"}
