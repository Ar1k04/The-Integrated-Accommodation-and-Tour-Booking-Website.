import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.room import Room
from app.models.tour_booking import TourBooking
from app.models.user import User
from app.schemas.user import UserListResponse, UserResponse, UserUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats")
async def dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
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
        .order_by(Booking.created_at.desc())
        .limit(10)
    )
    recent = (await db.execute(recent_bookings_q)).scalars().all()
    recent_bookings = []
    for b in recent:
        recent_bookings.append({
            "id": str(b.id),
            "user_id": str(b.user_id),
            "room_id": str(b.room_id),
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
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
    current_user: AdminUser,
    booking_status: str | None = Query(None, alias="status"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Booking)
    if booking_status:
        query = query.where(Booking.status == booking_status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Booking.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    bookings = result.scalars().all()

    items = []
    for b in bookings:
        items.append({
            "id": str(b.id),
            "user_id": str(b.user_id),
            "room_id": str(b.room_id),
            "check_in": str(b.check_in),
            "check_out": str(b.check_out),
            "guests_count": b.guests_count,
            "total_price": float(b.total_price),
            "status": b.status,
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
    current_user: AdminUser,
    new_status: str = Query(..., alias="status"),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")

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
