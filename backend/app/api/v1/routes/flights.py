"""Duffel flight search, offer retrieval, booking management, and ancillaries."""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Annotated, Literal

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import uuid as _uuid

from app.core.dependencies import CurrentUser, StaffUser
from app.data.airports import search_airports
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.models.booking_item import BookingItem, BookingItemStatus, BookingItemType
from app.models.flight_booking import FlightBooking
from app.models.payment import Payment, PaymentStatus
from app.services import duffel_service, payment_service
from app.services.duffel_service import DuffelError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flights", tags=["flights"])


def _cache(request: Request):
    return getattr(request.app.state, "redis", None)


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _slice_duration_minutes(sl: dict) -> int:
    """Compute total minutes for a slice from its first segment departure to last arrival."""
    segs = sl.get("segments") or []
    if not segs:
        return 0
    dep = _parse_iso(segs[0].get("departure_at"))
    arr = _parse_iso(segs[-1].get("arrival_at"))
    if not dep or not arr:
        return 0
    return max(0, int((arr - dep).total_seconds() // 60))


def _apply_filters(
    offers: list[dict],
    max_connections: int | None,
    max_price: float | None,
    airlines: list[str] | None,
) -> list[dict]:
    result = offers
    if max_connections is not None:
        result = [
            o for o in result
            if all(
                len(sl.get("segments") or []) - 1 <= max_connections
                for sl in o.get("slices") or []
            )
        ]
    if max_price is not None:
        result = [o for o in result if (o.get("total_amount") or 0) <= max_price]
    if airlines:
        wanted = {a.upper() for a in airlines}
        result = [o for o in result if (o.get("airline_iata") or "").upper() in wanted]
    return result


def _sort_offers(
    offers: list[dict],
    sort_by: str,
    sort_order: str,
) -> list[dict]:
    reverse = sort_order == "desc"
    if sort_by == "price":
        return sorted(offers, key=lambda o: o.get("total_amount") or 0, reverse=reverse)
    if sort_by == "duration":
        return sorted(
            offers,
            key=lambda o: sum(_slice_duration_minutes(sl) for sl in (o.get("slices") or [])),
            reverse=reverse,
        )
    if sort_by == "departure_time":
        return sorted(
            offers,
            key=lambda o: (
                _parse_iso(
                    ((o.get("slices") or [{}])[0].get("segments") or [{}])[0].get("departure_at")
                )
                or datetime.max
            ),
            reverse=reverse,
        )
    return offers


@router.get("/airports")
async def list_airports(
    q: str = Query(..., min_length=1, max_length=64, description="Search IATA, city, or airport name"),
    limit: int = Query(10, ge=1, le=25),
):
    """Autocomplete airports by IATA prefix, city, or airport name."""
    results = search_airports(q, limit=limit)
    return {"data": results, "status": "success", "count": len(results), "message": "OK"}


def _parse_child_ages_csv(raw: str | None) -> list[int]:
    """Parse `child_ages=11,8` into a clamped list of ints (0–17)."""
    if not raw:
        return []
    ages: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            age = int(chunk)
        except ValueError:
            continue
        if 0 <= age <= 17:
            ages.append(age)
    return ages


@router.get("/search")
async def search_flights(
    request: Request,
    origin: str = Query(..., min_length=3, max_length=3, description="IATA origin code e.g. HAN"),
    destination: str = Query(..., min_length=3, max_length=3, description="IATA destination code e.g. SGN"),
    depart_date: date = Query(..., alias="depart_date"),
    return_date: date | None = Query(None, alias="return_date"),
    adults: int = Query(default=1, ge=1, le=9, description="Number of adult passengers"),
    child_ages: str | None = Query(
        default=None,
        description="Comma-separated child ages (0–17), e.g. '8,11'",
    ),
    passengers: int | None = Query(
        default=None,
        ge=1,
        le=9,
        description="Deprecated. Use adults + child_ages instead.",
    ),
    cabin_class: str = Query(default="economy"),
    max_connections: int | None = Query(None, ge=0, le=3),
    max_price: float | None = Query(None, gt=0),
    airlines: list[str] | None = Query(None, description="IATA codes to whitelist"),
    sort_by: Literal["price", "duration", "departure_time"] = Query("price"),
    sort_order: Literal["asc", "desc"] = Query("asc"),
):
    parsed_children = _parse_child_ages_csv(child_ages)
    effective_adults = adults
    if passengers is not None and child_ages is None:
        # Legacy callers: pre-children search bar passed only `passengers`.
        effective_adults = passengers
    total_pax = effective_adults + len(parsed_children)
    airlines_norm = ",".join(sorted([a.upper() for a in (airlines or [])]))
    child_ages_norm = ",".join(str(a) for a in parsed_children)
    cache_key = (
        f"duffel:search:{origin.upper()}:{destination.upper()}:{depart_date}:{return_date}:"
        f"a{effective_adults}:c{child_ages_norm}:{cabin_class}"
    )
    filter_key = f"{cache_key}:flt:{max_connections}:{max_price}:{airlines_norm}:{sort_by}:{sort_order}"
    redis = _cache(request)

    if redis:
        cached = await redis.get(filter_key)
        if cached:
            return {
                "data": json.loads(cached),
                "status": "success",
                "message": "OK",
                "source": "cache",
            }

    try:
        offers = await duffel_service.search_offers(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            adults=effective_adults,
            child_ages=parsed_children,
            cabin_class=cabin_class,
        )
    except DuffelError as exc:
        logger.warning("Duffel search error: %s", exc.message)
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Flight search unavailable — try again later",
        )

    # Drop offers whose Duffel TTL won't survive the typical checkout flow.
    # Sandbox offers commonly expire in 5-15 min and the user still needs to
    # open detail → fill passengers → confirm Stripe → backend creates Duffel
    # order (~2-3 min minimum). A 5-min safety buffer prevents the "looked
    # available but errored at book" race that wastes a Stripe roundtrip.
    now = datetime.now(timezone.utc)
    safety_buffer = timedelta(minutes=5)
    fresh_offers = []
    dropped = 0
    for o in offers:
        exp = _parse_iso(o.get("expires_at"))
        if exp is None or exp - safety_buffer > now:
            fresh_offers.append(o)
        else:
            dropped += 1
    if dropped:
        logger.info(
            "Filtered %d/%d offers with expires_at < 5 min (route=%s→%s)",
            dropped, len(offers), origin, destination,
        )
    offers = fresh_offers

    offers = _apply_filters(offers, max_connections, max_price, airlines)
    offers = _sort_offers(offers, sort_by, sort_order)

    # Cache each offer individually so Select-after-search always resolves.
    # Duffel's natural expiry window is ~20 min; we cap at that.
    if redis:
        for o in offers:
            exp_dt = _parse_iso(o.get("expires_at"))
            ttl = 1200
            if exp_dt is not None:
                remaining = int((exp_dt - now).total_seconds())
                if remaining > 0:
                    ttl = min(remaining, 1200)
                else:
                    continue
            try:
                await redis.setex(
                    f"duffel:offer:{o['duffel_offer_id']}",
                    ttl,
                    json.dumps(o),
                )
            except Exception as exc:
                logger.debug("Offer cache write failed: %s", exc)

    if redis and offers:
        await redis.setex(filter_key, 300, json.dumps(offers))

    return {"data": offers, "status": "success", "message": "OK", "count": len(offers)}


@router.get("/offers/{duffel_offer_id}")
async def get_flight_offer(request: Request, duffel_offer_id: str):
    """Return a single offer. Tries Duffel for fresh price, falls back to the
    per-offer cache populated during /search so a freshly-found offer is always
    clickable even if Duffel's individual-offer endpoint flakes or the offer
    aged past the supplier's strict TTL.
    """
    redis = _cache(request)
    cache_key = f"duffel:offer:{duffel_offer_id}"

    try:
        offer = await duffel_service.get_offer(duffel_offer_id)
        # Refresh the cached snapshot so subsequent fallbacks have latest price
        if redis:
            try:
                await redis.setex(cache_key, 1200, json.dumps(offer))
            except Exception:
                pass
        return {"data": offer, "status": "success", "message": "OK"}
    except DuffelError as exc:
        if redis:
            cached = await redis.get(cache_key)
            if cached:
                logger.info(
                    "Duffel get_offer %s failed (%s) — serving cached snapshot",
                    duffel_offer_id, exc.message,
                )
                return {
                    "data": json.loads(cached),
                    "status": "success",
                    "message": "OK",
                    "source": "cache",
                }
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Offer not found or expired",
        )


async def _verify_order_ownership(
    db: AsyncSession, duffel_order_id: str, user_id
) -> FlightBooking:
    """Return the FlightBooking iff the current user owns it via the Booking graph."""
    result = await db.execute(
        select(FlightBooking)
        .join(BookingItem, BookingItem.flight_booking_id == FlightBooking.id)
        .join(Booking, Booking.id == BookingItem.booking_id)
        .where(FlightBooking.duffel_order_id == duffel_order_id, Booking.user_id == user_id)
    )
    flight = result.scalar_one_or_none()
    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return flight


@router.get("/orders/{duffel_order_id}")
async def get_flight_order(
    duffel_order_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Fetch live order details from Duffel. Verifies ownership against local booking."""
    await _verify_order_ownership(db, duffel_order_id, current_user.id)
    try:
        order = await duffel_service.get_order(duffel_order_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Order not found at airline",
        )
    return {"data": order, "status": "success", "message": "OK"}


@router.get("/seat-maps/{duffel_offer_id}")
async def get_flight_seat_maps(
    request: Request,
    duffel_offer_id: str,
):
    """Seat maps for an offer. Empty list if the airline doesn't support it."""
    cache_key = f"duffel:seat-maps:{duffel_offer_id}"
    redis = _cache(request)
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return {"data": json.loads(cached), "status": "success", "source": "cache"}

    try:
        seat_maps = await duffel_service.get_seat_maps(duffel_offer_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Seat maps unavailable",
        )

    if redis:
        await redis.setex(cache_key, 60, json.dumps(seat_maps))
    return {"data": seat_maps, "status": "success", "message": "OK", "count": len(seat_maps)}


@router.get("/offers/{duffel_offer_id}/available_services")
async def get_flight_services(
    request: Request,
    duffel_offer_id: str,
):
    """Add-on services (baggage, etc.) for an offer."""
    cache_key = f"duffel:services:{duffel_offer_id}"
    redis = _cache(request)
    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return {"data": json.loads(cached), "status": "success", "source": "cache"}

    try:
        services = await duffel_service.get_available_services(duffel_offer_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Services unavailable",
        )

    if redis:
        await redis.setex(cache_key, 60, json.dumps(services))
    return {"data": services, "status": "success", "message": "OK", "count": len(services)}


@router.post("/orders/{duffel_order_id}/sync")
async def sync_flight_order(
    duffel_order_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Pull authoritative order state from Duffel and update local FlightBooking."""
    flight = await _verify_order_ownership(db, duffel_order_id, current_user.id)
    try:
        order = await duffel_service.get_order(duffel_order_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Sync failed",
        )

    duffel_status = order.get("status") or ""
    if "cancelled" in duffel_status.lower():
        flight.status = "cancelled"
    elif duffel_status:
        flight.status = "confirmed"

    details = dict(flight.passenger_details or {})
    details["documents"] = order.get("documents") or []
    details["last_synced_at"] = datetime.utcnow().isoformat() + "Z"
    flight.passenger_details = details

    await db.flush()
    await db.refresh(flight)

    return {
        "data": {
            "duffel_order_id": order.get("duffel_order_id"),
            "duffel_booking_ref": order.get("duffel_booking_ref"),
            "status": flight.status,
            "documents": order.get("documents") or [],
            "synced_at": details["last_synced_at"],
        },
        "status": "success",
        "message": "Synced",
    }


@router.post("/bookings/{booking_item_id}/retry-duffel-order")
async def admin_retry_duffel_order(
    booking_item_id: _uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    """Admin/partner action: retry a stuck Duffel order.

    Use when a booking succeeded on the payment side but the supplier call
    failed (transient Duffel error, etc.). Pre-checks that the offer is still
    alive at Duffel — if it isn't, the only remedy is a refund + re-book.

    Rejects the retry once the booking has been auto-refunded into the
    cancelled state (status=cancelled AND payment refunded): admin must
    refund/re-book manually instead.
    """
    item = (
        await db.execute(
            select(BookingItem)
            .options(
                selectinload(BookingItem.flight_booking),
                selectinload(BookingItem.booking).selectinload(Booking.items),
            )
            .where(BookingItem.id == booking_item_id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking item not found")
    if item.item_type != BookingItemType.flight.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not a flight item")
    flight = item.flight_booking
    if not flight:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No flight booking attached")
    if flight.duffel_order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order already exists at Duffel")

    booking = item.booking
    payment = (
        await db.execute(
            select(Payment)
            .where(Payment.booking_id == booking.id)
            .order_by(Payment.created_at.desc())
        )
    ).scalars().first()
    if booking.status == BookingStatus.cancelled.value and payment and payment.status == PaymentStatus.refunded.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking was already refunded — the customer must search and book a new offer.",
        )

    offer_id = (flight.passenger_details or {}).get("offer_id")
    if not offer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flight has no stored offer_id — cannot retry. Customer must re-search.",
        )

    # Verify the offer is still alive — saves us a guaranteed retry-and-fail.
    try:
        await duffel_service.get_offer(offer_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Offer is no longer valid at Duffel ({exc.error_code or exc.status_code}): {exc.message}. Customer must re-search.",
        )

    from app.services.booking_service import _finalize_duffel_flight, _build_failed_item_entry
    success, last_error = await _finalize_duffel_flight(db, booking, item, flight, max_attempts=3)
    if success:
        item.status = BookingItemStatus.confirmed.value
        # If the booking was previously stuck pending, promote it back to confirmed.
        if booking.status == BookingStatus.pending.value:
            booking.status = BookingStatus.confirmed.value
        await db.flush()
        return {
            "data": {
                "booking_id": str(booking.id),
                "item_id": str(item.id),
                "duffel_order_id": flight.duffel_order_id,
                "duffel_booking_ref": flight.duffel_booking_ref,
                "status": "confirmed",
            },
            "status": "success",
            "message": "Duffel order created on retry",
        }

    # Retry exhausted again. Persist the new last_error (already done inside
    # the helper) and surface a 200 with the structured failure.
    await db.flush()
    failed_entry = _build_failed_item_entry(item, flight, last_error)
    return {
        "data": {
            "booking_id": str(booking.id),
            "item_id": str(item.id),
            "status": "failed",
            "failed_items": [failed_entry],
            "supplier_error": {
                "supplier": "duffel",
                "error_code": failed_entry.get("error_code"),
                "error_type": failed_entry.get("error_type"),
                "message": failed_entry.get("user_message"),
            },
        },
        "status": "error",
        "message": "Duffel still rejecting the order",
    }


def _err_from_duffel(exc: DuffelError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code if exc.status_code and exc.status_code < 500 else 502,
        detail=exc.message or "Duffel error",
    )


async def _verify_order_owner_by_id(
    db: AsyncSession, duffel_order_id: str, user_id
) -> tuple[FlightBooking, BookingItem]:
    """Return (FlightBooking, BookingItem) iff the user owns the order."""
    flight = await _verify_order_ownership(db, duffel_order_id, user_id)
    item = (
        await db.execute(
            select(BookingItem).where(BookingItem.flight_booking_id == flight.id)
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Booking item missing for order")
    return flight, item
