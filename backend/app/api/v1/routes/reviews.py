import math
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.booking_item import BookingItem
from app.models.hotel import Hotel
from app.models.review import Review
from app.models.room import Room
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.schemas.review import (
    ExternalReviewItem, ExternalReviewListResponse, ExternalReviewUser,
    ReviewCreate, ReviewListResponse, ReviewResponse, ReviewUpdate,
)
from app.services import completion_service, liteapi_service, viator_service
from app.services.viator_service import ViatorError

router = APIRouter(tags=["Reviews"])


def _parse_viator_date(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return datetime.now(tz=timezone.utc)


async def _paginated_reviews(
    db: AsyncSession,
    base_query,
    sort_by: str,
    page: int,
    per_page: int,
) -> ReviewListResponse:
    count_q = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    if sort_by == "rating":
        base_query = base_query.order_by(Review.rating.desc())
    else:
        base_query = base_query.order_by(Review.created_at.desc())

    base_query = base_query.options(selectinload(Review.user))
    base_query = base_query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(base_query)
    reviews = result.scalars().all()

    return ReviewListResponse(
        items=[ReviewResponse.model_validate(r) for r in reviews],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/hotels/{hotel_id}/reviews", response_model=ExternalReviewListResponse)
async def list_hotel_reviews(
    hotel_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    sort_by: str = Query("recent", pattern="^(recent|rating)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    hotel = (await db.execute(select(Hotel).where(Hotel.id == hotel_id))).scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found")

    # User-written reviews from our DB (verified completed stays).
    local_q = select(Review).where(Review.hotel_id == hotel_id).options(selectinload(Review.user))
    if sort_by == "rating":
        local_q = local_q.order_by(Review.rating.desc())
    else:
        local_q = local_q.order_by(Review.created_at.desc())
    local_reviews = (await db.execute(local_q)).scalars().all()

    local_items = [
        ExternalReviewItem(
            id=str(r.id),
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
            user=ExternalReviewUser(full_name=r.user.full_name if r.user else "Guest"),
        )
        for r in local_reviews
    ]

    # Read-only guest reviews proxied from LiteAPI for linked hotels. LiteAPI
    # has no write endpoint, so these are aggregated supplier reviews only.
    liteapi_items: list[ExternalReviewItem] = []
    if hotel.liteapi_hotel_id:
        raw = await liteapi_service.get_hotel_reviews(hotel.liteapi_hotel_id, limit=50)
        for r in raw:
            created = _parse_viator_date(r.get("created_at") or "")
            liteapi_items.append(
                ExternalReviewItem(
                    id=str(r.get("id")),
                    rating=r.get("rating") or 0,
                    comment=r.get("comment"),
                    created_at=created,
                    user=ExternalReviewUser(full_name=(r.get("user") or {}).get("full_name") or "Guest"),
                )
            )

    # Local reviews first, then supplier reviews; paginate the merged list.
    all_items = local_items + liteapi_items
    total = len(all_items)
    total_pages = math.ceil(total / per_page) if total else 0
    start = (page - 1) * per_page
    page_items = all_items[start: start + per_page]

    return ExternalReviewListResponse(
        items=page_items,
        meta={"total": total, "page": page, "per_page": per_page, "total_pages": total_pages},
    )


@router.get("/tours/viator/{viator_product_code}/reviews", response_model=ExternalReviewListResponse)
async def list_viator_tour_reviews(
    viator_product_code: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    per_page: int = Query(5, ge=1, le=50),
):
    # Fetch user-written reviews from local DB first
    local_q = select(Review).where(Review.viator_product_code == viator_product_code)
    local_q = local_q.options(selectinload(Review.user)).order_by(Review.created_at.desc())
    local_reviews = (await db.execute(local_q)).scalars().all()

    local_items = [
        ExternalReviewItem(
            id=str(r.id),
            rating=r.rating,
            comment=r.comment,
            created_at=r.created_at,
            user=ExternalReviewUser(full_name=r.user.full_name if r.user else "Traveler"),
        )
        for r in local_reviews
    ]

    # Fetch Viator API / fallback reviews
    try:
        result = await viator_service.get_product_reviews(viator_product_code, page, per_page)
    except ViatorError:
        result = {"reviews": [], "total": 0}

    reviews_raw = result.get("reviews") or []
    viator_total = result.get("total") or len(reviews_raw)

    viator_items = [
        ExternalReviewItem(
            id=r.get("id") or f"v-{viator_product_code}-{i}",
            rating=max(1, min(5, r["rating"])),
            comment=r.get("comment"),
            created_at=_parse_viator_date(r.get("published_date", "")),
            user=ExternalReviewUser(full_name=r.get("user_name") or "Traveler"),
        )
        for i, r in enumerate(reviews_raw)
    ]

    # Merge: local reviews appear first, then Viator reviews
    all_items = local_items + viator_items
    total = len(local_items) + viator_total
    total_pages = math.ceil(total / per_page) if total else 0

    # Paginate the merged list
    start = (page - 1) * per_page
    page_items = all_items[start: start + per_page]

    return ExternalReviewListResponse(
        items=page_items,
        meta={"total": total, "page": page, "per_page": per_page, "total_pages": total_pages},
    )


@router.get("/tours/{tour_id}/reviews", response_model=ReviewListResponse)
async def list_tour_reviews(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    sort_by: str = Query("recent", pattern="^(recent|rating)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    tour = (await db.execute(select(Tour).where(Tour.id == tour_id))).scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")

    query = select(Review).where(Review.tour_id == tour_id)
    return await _paginated_reviews(db, query, sort_by, page, per_page)


@router.post("/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    targets = [
        bool(data.hotel_id),
        bool(data.tour_id),
        bool(data.viator_product_code),
        bool(data.liteapi_hotel_id),
    ]
    if targets.count(True) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of hotel_id, tour_id, viator_product_code, or liteapi_hotel_id",
        )

    # Complete this user's overdue items first, so a guest who just checked out
    # can review immediately without waiting for the background scheduler.
    await completion_service.complete_due_items(db, user_id=current_user.id)

    if data.hotel_id:
        has_booking = (
            await db.execute(
                select(BookingItem.id)
                .join(Booking, BookingItem.booking_id == Booking.id)
                .join(Room, BookingItem.room_id == Room.id)
                .where(
                    Booking.user_id == current_user.id,
                    Room.hotel_id == data.hotel_id,
                    BookingItem.status == "completed",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not has_booking:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review hotels when you completed a stay",
            )

        already = (
            await db.execute(
                select(Review.id).where(
                    Review.user_id == current_user.id,
                    Review.hotel_id == data.hotel_id,
                )
            )
        ).scalar_one_or_none()
        if already:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this hotel")

    if data.tour_id:
        has_booking = (
            await db.execute(
                select(BookingItem.id)
                .join(Booking, BookingItem.booking_id == Booking.id)
                .join(TourSchedule, BookingItem.tour_schedule_id == TourSchedule.id)
                .where(
                    Booking.user_id == current_user.id,
                    TourSchedule.tour_id == data.tour_id,
                    BookingItem.status == "completed",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not has_booking:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review tours you completed",
            )

        already = (
            await db.execute(
                select(Review.id).where(
                    Review.user_id == current_user.id,
                    Review.tour_id == data.tour_id,
                )
            )
        ).scalar_one_or_none()
        if already:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this tour")

    if data.viator_product_code:
        has_booking = (
            await db.execute(
                select(Booking.id)
                .join(BookingItem, BookingItem.booking_id == Booking.id)
                .where(
                    Booking.user_id == current_user.id,
                    BookingItem.viator_product_code == data.viator_product_code,
                    BookingItem.status == "completed",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not has_booking:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review Viator tours you have completed",
            )

        already = (
            await db.execute(
                select(Review.id).where(
                    Review.user_id == current_user.id,
                    Review.viator_product_code == data.viator_product_code,
                )
            )
        ).scalar_one_or_none()
        if already:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this tour")

    if data.liteapi_hotel_id:
        has_booking = (
            await db.execute(
                select(Booking.id)
                .join(BookingItem, BookingItem.booking_id == Booking.id)
                .where(
                    Booking.user_id == current_user.id,
                    BookingItem.liteapi_hotel_id == data.liteapi_hotel_id,
                    BookingItem.status == "completed",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not has_booking:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review hotels when you completed a stay",
            )

        already = (
            await db.execute(
                select(Review.id).where(
                    Review.user_id == current_user.id,
                    Review.liteapi_hotel_id == data.liteapi_hotel_id,
                )
            )
        ).scalar_one_or_none()
        if already:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already reviewed this hotel")

    review = Review(user_id=current_user.id, **data.model_dump())
    db.add(review)
    await db.flush()

    await _update_aggregate_rating(db, data.hotel_id, data.tour_id)

    await db.refresh(review)
    return review


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: uuid.UUID,
    data: ReviewUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if review.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your review")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    await db.flush()

    await _update_aggregate_rating(db, review.hotel_id, review.tour_id)

    await db.refresh(review)
    return review


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    if review.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    hotel_id, tour_id = review.hotel_id, review.tour_id
    await db.delete(review)
    await db.flush()
    await _update_aggregate_rating(db, hotel_id, tour_id)


async def _update_aggregate_rating(
    db: AsyncSession,
    hotel_id: uuid.UUID | None,
    tour_id: uuid.UUID | None,
) -> None:
    """Recompute avg_rating and total_reviews on the parent entity."""
    if hotel_id:
        stats = (
            await db.execute(
                select(func.avg(Review.rating), func.count(Review.id)).where(Review.hotel_id == hotel_id)
            )
        ).one()
        hotel = (await db.execute(select(Hotel).where(Hotel.id == hotel_id))).scalar_one_or_none()
        if hotel:
            hotel.avg_rating = float(stats[0] or 0)
            hotel.total_reviews = stats[1]

    if tour_id:
        stats = (
            await db.execute(
                select(func.avg(Review.rating), func.count(Review.id)).where(Review.tour_id == tour_id)
            )
        ).one()
        tour = (await db.execute(select(Tour).where(Tour.id == tour_id))).scalar_one_or_none()
        if tour:
            tour.avg_rating = float(stats[0] or 0)
            tour.total_reviews = stats[1]
