import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

from app.core.config import settings
from app.core.dependencies import StaffUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.schemas.payment import PaymentCreate, PaymentResponse, VnpayCreateRequest
from app.services import vnpay_service
from app.services.payment_service import (
    _to_cents,
    create_payment_intent,
    handle_webhook_event,
    refund_payment,
    OfferExpiredError,
)


WEBHOOK_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


def _owns_payment(payment: Payment, user) -> bool:
    if user.role in ("partner", "admin"):
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
    except OfferExpiredError as exc:
        # 409 Conflict — semantically correct for "the resource you're trying to
        # pay for is no longer in a payable state." Frontend reads error_code
        # to show a "search again" CTA instead of a generic toast.
        #
        # We also mark the booking + its items as cancelled so it doesn't sit
        # in My Bookings as a stale `pending` row forever. The booking was
        # created on the previous request (POST /bookings) and never gets a
        # chance to reach the supplier — without this cleanup the user sees
        # an orphan pending booking after being redirected back to search.
        from app.models.booking_item import BookingItem, BookingItemStatus
        from app.models.booking import BookingStatus
        booking_row = (
            await db.execute(
                select(Booking)
                .options(selectinload(Booking.items))
                .where(Booking.id == data.booking_id, Booking.user_id == current_user.id)
            )
        ).scalar_one_or_none()
        if booking_row and booking_row.status == BookingStatus.pending.value:
            booking_row.status = BookingStatus.cancelled.value
            for item in booking_row.items:
                if item.status == BookingItemStatus.pending.value:
                    item.status = BookingItemStatus.cancelled.value
            await db.flush()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "offer_no_longer_available",
                "message": str(exc),
                "offer_id": exc.offer_id,
            },
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


def _confirm_response_body(payment: Payment, booking: Booking | None, outcome: dict) -> dict:
    """Shape the JSON body returned to the client after confirm-stripe / vnpay-return.

    For all-success outcomes returns ``success: true`` with a confirmed status.
    Anything else returns ``success: false`` plus failure_reason / supplier_error
    / refund blocks so the frontend can route to the failure page.
    """
    status_str = outcome.get("status") or "confirmed"
    booking_id = str(payment.booking_id) if payment and payment.booking_id else (str(booking.id) if booking else None)
    if status_str == "confirmed":
        return {
            "success": True,
            "data": {"booking_id": booking_id, "status": "confirmed"},
        }
    failed_items = outcome.get("failed_items") or []
    primary = failed_items[0] if failed_items else {}
    body = {
        "success": False,
        "data": {
            "booking_id": booking_id,
            "status": status_str,
            "failure_reason": "flight_booking_failed",
            "failed_items": failed_items,
            "confirmed_items": outcome.get("confirmed_items") or [],
            "refund": outcome.get("refund"),
            "supplier_error": {
                "supplier": "duffel",
                "error_code": primary.get("error_code"),
                "error_type": primary.get("error_type"),
                "message": primary.get("user_message"),
            } if primary else None,
        },
    }
    return body


async def _load_booking_with_items(db: AsyncSession, booking_id) -> Booking | None:
    """Eager-load booking with items AND each item's flight_booking — needed
    because confirm_booking() touches `item.flight_booking` and lazy-loading
    inside async + autoflush blows up with MissingGreenlet / 500."""
    from app.models.booking_item import BookingItem
    return (
        await db.execute(
            select(Booking)
            .options(
                selectinload(Booking.items).selectinload(BookingItem.flight_booking)
            )
            .where(Booking.id == booking_id)
        )
    ).scalar_one_or_none()


def _split_name(user: User | None) -> tuple[str, str, str, str | None]:
    if not user:
        return "Guest", "Guest", "guest@example.com", None
    full = (user.full_name or "Guest").strip()
    parts = full.split(" ") if full else ["Guest"]
    fn = parts[0] or "Guest"
    ln = " ".join(parts[1:]) or "Guest"
    email = user.email or "guest@example.com"
    phone = user.phone if getattr(user, "phone", None) else None
    return fn, ln, email, phone


@router.post("/{payment_id}/confirm-stripe", status_code=status.HTTP_200_OK)
async def confirm_stripe_payment(
    payment_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Called by the frontend after Stripe confirms client-side.
    Verifies the PaymentIntent is succeeded directly with Stripe, then calls
    confirm_booking() to finalize the supplier side (Duffel order, LiteAPI
    booking, etc.).

    Returns 200 in all outcomes. When a supplier fails AFTER payment, the body
    has ``success: false`` with failure_reason/supplier_error/refund — the
    frontend reads these to route to the failure page.

    Idempotent — re-calls after a prior succeeded/refunded run return the
    same outcome without re-running supplier calls.
    """
    payment = await _load_payment_for_user(db, payment_id, current_user)

    # Idempotent re-calls after the booking already finalized (either as
    # confirmed or refunded due to supplier failure).
    if payment.status in (PaymentStatus.succeeded.value, PaymentStatus.refunded.value):
        booking = await _load_booking_with_items(db, payment.booking_id)
        from app.services.booking_service import _outcome_from_persisted_state
        outcome = _outcome_from_persisted_state(booking) if booking else {"status": "confirmed"}
        return _confirm_response_body(payment, booking, outcome)

    if not payment.stripe_payment_intent_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a Stripe payment")

    # Verify with Stripe directly (handles webhook not arriving in local dev)
    intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)
    if intent.status != "succeeded":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Payment not succeeded: {intent.status}")

    # Defense-in-depth: ensure the succeeded intent is for THIS booking at the right amount.
    expected_cents = _to_cents(payment.amount)
    if intent.amount != expected_cents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PaymentIntent amount does not match booking")
    if (intent.metadata or {}).get("booking_id") != str(payment.booking_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PaymentIntent does not belong to this booking")

    payment.status = PaymentStatus.succeeded.value

    outcome: dict = {"status": "confirmed", "confirmed_items": [], "failed_items": [], "refund": None}
    booking: Booking | None = None
    if payment.booking_id:
        from app.services.booking_service import confirm_booking
        booking = await _load_booking_with_items(db, payment.booking_id)
        if booking:
            redis = request.app.state.redis
            user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
            fn, ln, email, phone = _split_name(user)
            booking, outcome = await confirm_booking(
                db, booking,
                guest_first_name=fn, guest_last_name=ln,
                guest_email=email, guest_phone=phone, redis=redis,
            )

    await db.flush()
    return _confirm_response_body(payment, booking, outcome)


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

    await handle_webhook_event(db, event, redis=redis)
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
        booking_with_items = await _load_booking_with_items(db, booking.id)
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        fn, ln, email, phone = _split_name(user)
        redis = getattr(request.app.state, "redis", None)
        confirmed_booking, outcome = await confirm_booking(
            db, booking_with_items,
            guest_first_name=fn, guest_last_name=ln,
            guest_email=email, guest_phone=phone, redis=redis,
        )
        await db.flush()
        body = _confirm_response_body(payment, confirmed_booking, outcome)
        body["message"] = "Payment successful" if outcome.get("status") == "confirmed" else "Payment captured, booking finalization issue"
        return body
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
        booking_with_items = await _load_booking_with_items(db, booking.id)
        user = (await db.execute(select(User).where(User.id == booking.user_id))).scalar_one_or_none()
        fn = (user.full_name or "Guest").split(" ")[0] if user else "Guest"
        ln = " ".join((user.full_name or "Guest").split(" ")[1:]) or "Guest" if user else "Guest"
        email = user.email if user else "guest@example.com"
        phone = user.phone if user and user.phone else None
        redis = getattr(request.app.state, "redis", None)
        await confirm_booking(
            db, booking_with_items,
            guest_first_name=fn, guest_last_name=ln,
            guest_email=email, guest_phone=phone, redis=redis,
        )
        await db.flush()
        return {"RspCode": "00", "Message": "Success"}
    else:
        if payment:
            payment.status = PaymentStatus.failed.value
        await db.flush()
        return {"RspCode": "01", "Message": "Payment failed"}
