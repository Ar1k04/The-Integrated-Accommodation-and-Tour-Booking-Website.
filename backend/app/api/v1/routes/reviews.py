import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.hotel import Hotel
from app.models.review import Review
from app.models.tour import Tour
from app.models.tour_booking import TourBooking
from app.schemas.review import ReviewCreate, ReviewListResponse, ReviewResponse, ReviewUpdate

router = APIRouter(tags=["Reviews"])


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


@router.get("/hotels/{hotel_id}/reviews", response_model=ReviewListResponse)
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

    query = select(Review).where(Review.hotel_id == hotel_id)
    return await _paginated_reviews(db, query, sort_by, page, per_page)


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
    if bool(data.hotel_id) == bool(data.tour_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of hotel_id or tour_id",
        )

    if data.hotel_id:
        has_booking = (
            await db.execute(
                select(Booking.id)
                .join(Booking.room)
                .where(
                    Booking.user_id == current_user.id,
                    Booking.room.has(hotel_id=data.hotel_id),
                    Booking.status == "completed",
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not has_booking:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review hotels where you completed a stay",
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
                select(TourBooking.id).where(
                    TourBooking.user_id == current_user.id,
                    TourBooking.tour_id == data.tour_id,
                    TourBooking.status == "completed",
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
