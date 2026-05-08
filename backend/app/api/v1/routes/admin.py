import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.models.user import User
from app.schemas.user import UserListResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


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

    total_revenue = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.status == "succeeded",
                Payment.created_at >= start,
            )
        )
    ).scalar()

    bookings_count = (
        await db.execute(
            select(func.count(Booking.id)).where(Booking.created_at >= start)
        )
    ).scalar()

    new_users = (
        await db.execute(
            select(func.count(User.id)).where(User.created_at >= start)
        )
    ).scalar()

    total_rooms = (await db.execute(select(func.coalesce(func.sum(Room.total_quantity), 0)))).scalar()
    booked_rooms = (
        await db.execute(
            select(func.count(Booking.id)).where(
                Booking.status.in_(["confirmed", "completed"]),
                Booking.created_at >= start,
            )
        )
    ).scalar()
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
    revenue_rows = (await db.execute(revenue_chart_q)).all()
    revenue_chart_data = [{"date": str(r.day), "revenue": float(r.revenue)} for r in revenue_rows]

    bookings_by_status_q = (
        select(Booking.status, func.count(Booking.id).label("count"))
        .where(Booking.created_at >= start)
        .group_by(Booking.status)
    )
    status_rows = (await db.execute(bookings_by_status_q)).all()
    bookings_by_status = {r.status: r.count for r in status_rows}

    recent_bookings_q = (
        select(Booking)
        .options(selectinload(Booking.items))
        .order_by(Booking.created_at.desc())
        .limit(10)
    )
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
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    for field, value in data.model_dump(exclude_unset=True).items():
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
                "liteapi_booking_id": bi.liteapi_booking_id,
                "viator_product_code": bi.viator_product_code,
                "viator_booking_ref": bi.viator_booking_ref,
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

    booking.status = new_status
    await db.flush()
    await db.refresh(booking)

    return {
        "success": True,
        "data": {
            "id": str(booking.id),
            "status": booking.status,
        },
    }


