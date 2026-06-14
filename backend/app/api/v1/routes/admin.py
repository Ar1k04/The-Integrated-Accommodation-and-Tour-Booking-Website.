import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Date, String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AdminUser, StaffUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.hotel import Hotel
from app.models.payment import Payment
from app.models.room import Room
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.models.loyalty_tier import LoyaltyTier
from app.models.user import User
from app.models.voucher import Voucher
from app.schemas.loyalty import LoyaltyTierCreate, LoyaltyTierResponse, LoyaltyTierUpdate
from app.schemas.user import (
    PartnerStatusUpdate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from app.services import booking_service, loyalty_service

router = APIRouter(prefix="/admin", tags=["Admin"])


def _has_liteapi_item(booking: Booking) -> bool:
    return any(
        bi.liteapi_prebook_id or bi.liteapi_booking_id
        for bi in booking.items
    )


async def _count_user_bookings(
    db: AsyncSession, user_id: uuid.UUID, *, statuses: list[str] | None = None
) -> int:
    """Count a user's bookings, optionally restricted to given statuses."""
    stmt = select(func.count()).select_from(Booking).where(Booking.user_id == user_id)
    if statuses is not None:
        stmt = stmt.where(Booking.status.in_(statuses))
    return (await db.execute(stmt)).scalar_one()


async def _count_user_vouchers(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Count vouchers owned (issued) by a user."""
    stmt = select(func.count()).select_from(Voucher).where(Voucher.admin_id == user_id)
    return (await db.execute(stmt)).scalar_one()


def _is_liteapi_only(booking: Booking) -> bool:
    """True when every item in the booking is LiteAPI-sourced."""
    if not booking.items:
        return False
    return all(
        (bi.liteapi_prebook_id or bi.liteapi_booking_id) for bi in booking.items
    )


@router.get("/stats")
async def dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    period: str = Query("month", pattern="^(week|month|year)$"),
):
    now = datetime.now(timezone.utc)
    if period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=365)

    # AUTHZ-04: partners see ONLY metrics for bookings/listings they own.
    # `partner_exists` correlates on the outer Booking row, mirroring
    # list_all_bookings(); revenue queries (on Payment) join Booking first.
    is_partner = current_user.role == "partner"
    partner_exists = (
        select(BookingItem.id)
        .join(Room, BookingItem.room_id == Room.id, isouter=True)
        .join(Hotel, Room.hotel_id == Hotel.id, isouter=True)
        .join(TourSchedule, BookingItem.tour_schedule_id == TourSchedule.id, isouter=True)
        .join(Tour, TourSchedule.tour_id == Tour.id, isouter=True)
        .where(
            BookingItem.booking_id == Booking.id,
            BookingItem.liteapi_prebook_id.is_(None),
            BookingItem.liteapi_booking_id.is_(None),
            BookingItem.viator_product_code.is_(None),
            BookingItem.flight_booking_id.is_(None),
            or_(Hotel.owner_id == current_user.id, Tour.owner_id == current_user.id),
        )
        .exists()
    ) if is_partner else None

    revenue_q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == "succeeded",
        Payment.created_at >= start,
    )
    if is_partner:
        revenue_q = revenue_q.join(Booking, Payment.booking_id == Booking.id).where(partner_exists)
    total_revenue = (await db.execute(revenue_q)).scalar()

    bookings_count_q = select(func.count(Booking.id)).where(Booking.created_at >= start)
    if is_partner:
        bookings_count_q = bookings_count_q.where(partner_exists)
    bookings_count = (await db.execute(bookings_count_q)).scalar()

    # Platform-wide user growth is admin-only; partners get 0.
    if is_partner:
        new_users = 0
    else:
        new_users = (
            await db.execute(
                select(func.count(User.id)).where(User.created_at >= start)
            )
        ).scalar()

    total_rooms_q = select(func.coalesce(func.sum(Room.total_quantity), 0))
    if is_partner:
        total_rooms_q = total_rooms_q.join(Hotel, Room.hotel_id == Hotel.id).where(
            Hotel.owner_id == current_user.id
        )
    total_rooms = (await db.execute(total_rooms_q)).scalar()

    booked_rooms_q = select(func.count(Booking.id)).where(
        Booking.status.in_(["confirmed", "completed"]),
        Booking.created_at >= start,
    )
    if is_partner:
        booked_rooms_q = booked_rooms_q.where(partner_exists)
    booked_rooms = (await db.execute(booked_rooms_q)).scalar()
    occupancy_rate = round((booked_rooms / total_rooms * 100) if total_rooms else 0, 1)

    revenue_chart_q = (
        select(
            cast(Payment.created_at, Date).label("day"),
            func.sum(Payment.amount).label("revenue"),
        )
        .where(Payment.status == "succeeded", Payment.created_at >= start)
        .group_by("day")
        .order_by("day")
    )
    if is_partner:
        revenue_chart_q = revenue_chart_q.join(
            Booking, Payment.booking_id == Booking.id
        ).where(partner_exists)
    revenue_rows = (await db.execute(revenue_chart_q)).all()
    revenue_chart_data = [{"date": str(r.day), "revenue": float(r.revenue)} for r in revenue_rows]

    bookings_by_status_q = (
        select(Booking.status, func.count(Booking.id).label("count"))
        .where(Booking.created_at >= start)
        .group_by(Booking.status)
    )
    if is_partner:
        bookings_by_status_q = bookings_by_status_q.where(partner_exists)
    status_rows = (await db.execute(bookings_by_status_q)).all()
    bookings_by_status = {r.status: r.count for r in status_rows}

    recent_bookings_q = (
        select(Booking)
        .options(selectinload(Booking.items))
        .order_by(Booking.created_at.desc())
        .limit(10)
    )
    if is_partner:
        recent_bookings_q = recent_bookings_q.where(partner_exists)
    recent = (await db.execute(recent_bookings_q)).scalars().all()
    recent_bookings = []
    for b in recent:
        first_room = next((i for i in b.items if i.item_type == "room"), None)
        recent_bookings.append({
            "id": str(b.id),
            "user_id": str(b.user_id),
            "items_count": len(b.items),
            "summary": (
                f"Hotel {first_room.check_in} → {first_room.check_out}"
                if first_room else f"{len(b.items)} item(s)"
            ),
            "total_price": float(b.total_price),
            "status": b.status,
            "created_at": b.created_at.isoformat(),
        })

    return {
        "success": True,
        "data": {
            "total_revenue": float(total_revenue),
            "bookings_count": bookings_count,
            "occupancy_rate": occupancy_rate,
            "new_users": new_users,
            "revenue_chart_data": revenue_chart_data,
            "bookings_by_status": bookings_by_status,
            "recent_bookings": recent_bookings,
        },
    }


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(User)
    if q:
        pattern = f"%{q}%"
        from sqlalchemy import or_
        query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(User.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    users = result.scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    force: bool = Query(
        False,
        description="Deactivate even if the user has active (pending/confirmed) bookings.",
    ),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payload = data.model_dump(exclude_unset=True)
    is_self = user.id == current_user.id

    # An admin must not lock themselves out: no self-deactivation or self-demotion.
    if is_self and payload.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    if is_self and "role" in payload and payload["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot remove your own admin role.",
        )
    # Admin accounts are protected from arbitrary deactivation/demotion by peers.
    if not is_self and user.role == "admin":
        if payload.get("is_active") is False or (
            "role" in payload and payload["role"] != "admin"
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin accounts cannot be deactivated or demoted.",
            )
    # Warn (block) before deactivating a user who still has live bookings.
    if payload.get("is_active") is False and not force:
        active = await _count_user_bookings(
            db, user.id, statuses=["pending", "confirmed"]
        )
        if active > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User has active bookings; pass force=true to deactivate.",
            )

    for field, value in payload.items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin accounts cannot be deleted.",
        )
    # Deleting a user cascades to their bookings, destroying records. A user with
    # any booking history must be deactivated, not hard-deleted (no force flag).
    if await _count_user_bookings(db, user.id) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has bookings; deactivate instead of deleting.",
        )
    # Vouchers cascade off their owner (admin_id ON DELETE CASCADE), taking the
    # voucher usage history with them. A partner/admin who has issued vouchers
    # must be deactivated, not hard-deleted, so that audit trail is preserved.
    if await _count_user_vouchers(db, user.id) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has issued vouchers; deactivate instead of deleting.",
        )
    await db.delete(user)
    await db.flush()


@router.get("/bookings")
async def list_all_bookings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    booking_status: str | None = Query(None, alias="status"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = (
        select(Booking)
        .options(
            selectinload(Booking.user),
            selectinload(Booking.items)
                .selectinload(BookingItem.room)
                .selectinload(Room.hotel),
            selectinload(Booking.items)
                .selectinload(BookingItem.tour_schedule)
                .selectinload(TourSchedule.tour),
            selectinload(Booking.payments),
        )
    )

    if current_user.role == "partner":
        # Partners see only bookings containing their own local (non-API) hotel/tour items
        partner_subq = (
            select(BookingItem.id)
            .join(Room, BookingItem.room_id == Room.id, isouter=True)
            .join(Hotel, Room.hotel_id == Hotel.id, isouter=True)
            .join(TourSchedule, BookingItem.tour_schedule_id == TourSchedule.id, isouter=True)
            .join(Tour, TourSchedule.tour_id == Tour.id, isouter=True)
            .where(
                BookingItem.booking_id == Booking.id,
                BookingItem.liteapi_prebook_id.is_(None),
                BookingItem.liteapi_booking_id.is_(None),
                BookingItem.viator_product_code.is_(None),
                BookingItem.flight_booking_id.is_(None),
                or_(
                    Hotel.owner_id == current_user.id,
                    Tour.owner_id == current_user.id,
                ),
            )
        )
        query = query.where(partner_subq.exists())

    if booking_status:
        query = query.where(Booking.status == booking_status)
    if q:
        query = query.where(cast(Booking.id, String).ilike(f"%{q}%"))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Booking.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    bookings = result.scalars().all()

    items = []
    for b in bookings:
        user = b.user
        payment = b.payments[0] if b.payments else None

        booking_items = []
        for bi in b.items:
            room = bi.room
            hotel = room.hotel if room else None
            tour_schedule = bi.tour_schedule
            tour = tour_schedule.tour if tour_schedule else None
            item_dict = {
                "item_type": bi.item_type,
                "check_in": str(bi.check_in) if bi.check_in else None,
                "check_out": str(bi.check_out) if bi.check_out else None,
                "quantity": bi.quantity,
                "subtotal": float(bi.subtotal),
                "liteapi_prebook_id": bi.liteapi_prebook_id,
                "liteapi_booking_id": bi.liteapi_booking_id,
                "viator_product_code": bi.viator_product_code,
                "viator_booking_ref": bi.viator_booking_ref,
                "supplier_status": bi.supplier_status,
                "supplier_status_synced_at": bi.supplier_status_synced_at.isoformat() if bi.supplier_status_synced_at else None,
            }
            if room:
                item_dict["room"] = {
                    "id": str(room.id),
                    "name": room.name,
                    "room_type": room.room_type,
                    "price_per_night": float(room.price_per_night),
                    "hotel": {
                        "id": str(hotel.id),
                        "name": hotel.name,
                        "city": hotel.city,
                        "country": hotel.country,
                        "slug": hotel.slug,
                    } if hotel else None,
                }
            if tour:
                item_dict["tour_name"] = tour.name
                item_dict["tour_slug"] = tour.slug
            booking_items.append(item_dict)

        items.append({
            "id": str(b.id),
            "user_id": str(b.user_id),
            "user": {
                "id": str(user.id),
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "loyalty_points": user.loyalty_points,
            } if user else None,
            "items": booking_items,
            "total_price": float(b.total_price),
            "status": b.status,
            "payment": {
                "status": payment.status,
                "stripe_payment_intent_id": payment.stripe_payment_intent_id,
            } if payment else None,
            "created_at": b.created_at.isoformat(),
        })

    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


@router.patch("/bookings/{booking_id}")
async def admin_update_booking(
    booking_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    new_status: str = Query(..., alias="status"),
):
    query = select(Booking).options(
        selectinload(Booking.items)
            .selectinload(BookingItem.room)
            .selectinload(Room.hotel),
        selectinload(Booking.items)
            .selectinload(BookingItem.tour_schedule)
            .selectinload(TourSchedule.tour),
    ).where(Booking.id == booking_id)
    result = await db.execute(query)
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if _has_liteapi_item(booking):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="LiteAPI bookings are managed by LiteAPI. Use the Sync action to refresh status.",
        )

    if current_user.role == "partner":
        owns = any(
            (
                bi.room_id and bi.room and bi.room.hotel and bi.room.hotel.owner_id == current_user.id
            ) or (
                bi.tour_schedule_id and bi.tour_schedule and bi.tour_schedule.tour and bi.tour_schedule.tour.owner_id == current_user.id
            )
            for bi in booking.items
        )
        if not owns:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your booking")

    if new_status == "cancelled" and booking.status != "cancelled":
        redis = getattr(request.app.state, "redis", None)
        await booking_service.cancel_booking(db, booking, redis=redis)
    else:
        booking.status = new_status
        for bi in booking.items:
            bi.status = new_status
        await db.flush()
        await db.refresh(booking)

    return {
        "success": True,
        "data": {
            "id": str(booking.id),
            "status": booking.status,
        },
    }


@router.post("/bookings/{booking_id}/sync-liteapi")
async def admin_sync_liteapi_booking(
    booking_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    """Refresh supplier_status for every LiteAPI item in the booking."""
    query = select(Booking).options(selectinload(Booking.items)).where(Booking.id == booking_id)
    booking = (await db.execute(query)).scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

    if not _has_liteapi_item(booking):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This booking has no LiteAPI items to sync.",
        )

    synced = []
    for bi in booking.items:
        if not (bi.liteapi_prebook_id or bi.liteapi_booking_id):
            continue
        new_status = await booking_service.sync_supplier_status(db, bi)
        synced.append({
            "id": str(bi.id),
            "supplier_status": new_status or bi.supplier_status,
            "supplier_status_synced_at": bi.supplier_status_synced_at.isoformat() if bi.supplier_status_synced_at else None,
        })

    await db.flush()

    return {"success": True, "data": {"booking_id": str(booking.id), "items": synced}}


# ── Partner approval (UC_A_PARTNERS) ─────────────────────────────────────────
@router.get("/partners", response_model=UserListResponse)
async def list_partners(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    partner_status: str | None = Query(None, alias="status", pattern="^(pending|approved|rejected)$"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(User).where(User.role == "partner")
    if partner_status:
        query = query.where(User.partner_status == partner_status)
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    query = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    users = (await db.execute(query)).scalars().all()

    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.patch("/partners/{user_id}", response_model=UserResponse)
async def set_partner_status(
    user_id: uuid.UUID,
    data: PartnerStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    user = (
        await db.execute(select(User).where(User.id == user_id, User.role == "partner"))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
    user.partner_status = data.partner_status
    await db.flush()
    await db.refresh(user)
    return user


# ── Loyalty tier management (UC_A_TIERS) ─────────────────────────────────────
@router.get("/loyalty-tiers", response_model=list[LoyaltyTierResponse])
async def list_loyalty_tiers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    rows = (await db.execute(select(LoyaltyTier).order_by(LoyaltyTier.min_points.asc()))).scalars().all()
    return [LoyaltyTierResponse.model_validate(t) for t in rows]


def _validate_loyalty_tier_set(ranges: list[tuple[int, int]]) -> None:
    """Validate the whole set of (min_points, max_points) tier ranges.

    ``max_points == 0`` means "no upper bound" and is allowed only for the
    single highest tier. min_points must be unique and strictly increasing, and
    ranges must not overlap.
    """
    if not ranges:
        return
    mins = [mn for mn, _ in ranges]
    if len(set(mins)) != len(mins):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Loyalty tiers must have unique, increasing min_points.",
        )
    ordered = sorted(ranges, key=lambda r: r[0])
    for i, (mn, mx) in enumerate(ordered):
        is_top = i == len(ordered) - 1
        if mx == 0:  # open-ended
            if not is_top:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only the highest tier may be open-ended (max_points = 0).",
                )
            continue
        if mx < mn:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A tier's max_points must be >= its min_points.",
            )
        if not is_top and mx >= ordered[i + 1][0]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Loyalty tier ranges must be non-overlapping and increasing.",
            )


@router.post("/loyalty-tiers", response_model=LoyaltyTierResponse, status_code=status.HTTP_201_CREATED)
async def create_loyalty_tier(
    data: LoyaltyTierCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    dup = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.name == data.name))).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tier name already exists")
    existing = (await db.execute(select(LoyaltyTier))).scalars().all()
    _validate_loyalty_tier_set(
        [(t.min_points, t.max_points) for t in existing]
        + [(data.min_points, data.max_points)]
    )
    tier = LoyaltyTier(**data.model_dump())
    db.add(tier)
    await db.flush()
    await db.refresh(tier)
    return tier


@router.patch("/loyalty-tiers/{tier_id}", response_model=LoyaltyTierResponse)
async def update_loyalty_tier(
    tier_id: uuid.UUID,
    data: LoyaltyTierUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == tier_id))).scalar_one_or_none()
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    payload = data.model_dump(exclude_unset=True)
    if "name" in payload and payload["name"] != tier.name:
        dup = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.name == payload["name"]))).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tier name already exists")
    new_min = payload.get("min_points", tier.min_points)
    new_max = payload.get("max_points", tier.max_points)
    others = (
        await db.execute(select(LoyaltyTier).where(LoyaltyTier.id != tier_id))
    ).scalars().all()
    _validate_loyalty_tier_set(
        [(t.min_points, t.max_points) for t in others] + [(new_min, new_max)]
    )
    for field, value in payload.items():
        setattr(tier, field, value)
    await db.flush()
    await db.refresh(tier)
    return tier


@router.delete("/loyalty-tiers/{tier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_loyalty_tier(
    tier_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.id == tier_id))).scalar_one_or_none()
    if not tier:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tier not found")
    # FK users.loyalty_tier_id is ON DELETE SET NULL — affected users fall to
    # no-tier and are re-mapped on their next points mutation.
    await db.delete(tier)
    await db.flush()


@router.post("/loyalty-tiers/recompute")
async def recompute_loyalty_tiers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    """Re-map every user to the correct tier (e.g. after editing thresholds)."""
    users = (await db.execute(select(User))).scalars().all()
    for u in users:
        await loyalty_service.recompute_tier(db, u)
    await db.flush()
    return {"success": True, "data": {"recomputed": len(users)}}


