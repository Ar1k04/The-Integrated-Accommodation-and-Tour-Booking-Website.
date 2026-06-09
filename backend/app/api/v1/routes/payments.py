import uuid
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

from app.core.config import settings
from app.core.dependencies import StaffUser, CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.hotel import Hotel
from app.models.payment import Payment, PaymentStatus
from app.models.room import Room
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.schemas.payment import PaymentCreate, PaymentResponse
from app.services.payment_service import (
    _to_cents,
    create_payment_intent,
    handle_webhook_event,
    refund_payment,
    OfferExpiredError,
)


WEBHOOK_IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


async def _user_can_access_payment(db: AsyncSession, payment: Payment, user) -> bool:
    """Authorize read access to a payment (AUTHZ-03).

    - admin: any payment.
    - the customer who owns the booking: their own payment.
    - partner: ONLY if the booking contains an item belonging to one of the
      partner's own local hotels/tours (owner_id). Previously every partner
      could read every payment.
    """
    if user.role == "admin":
        return True
    booking = payment.booking
    if booking and booking.user_id == user.id:
        return True
    if user.role == "partner" and booking is not None:
        partner_item = (
            select(BookingItem.id)
            .join(Room, BookingItem.room_id == Room.id, isouter=True)
            .join(Hotel, Room.hotel_id == Hotel.id, isouter=True)
            .join(TourSchedule, BookingItem.tour_schedule_id == TourSchedule.id, isouter=True)
            .join(Tour, TourSchedule.tour_id == Tour.id, isouter=True)
            .where(
                BookingItem.booking_id == booking.id,
                or_(Hotel.owner_id == user.id, Tour.owner_id == user.id),
            )
        )
        return bool((await db.execute(select(partner_item.exists()))).scalar())
    return False


async def _load_payment_for_user(
    db: AsyncSession, payment_id: uuid.UUID, user
) -> Payment:
    result = await db.execute(
        select(Payment)
        .options(selectinload(Payment.booking))
        .where(Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment or not await _user_can_access_payment(db, payment, user):
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
    """Shape the JSON body returned to the client after confirm-stripe.

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
