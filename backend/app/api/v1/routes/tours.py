import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.tour import Tour
from app.schemas.tour import TourCreate, TourListResponse, TourResponse, TourUpdate

router = APIRouter(prefix="/tours", tags=["Tours"])


def _tour_response(tour: Tour) -> TourResponse:
    data = TourResponse.model_validate(tour)
    if tour.owner:
        data.owner_name = tour.owner.full_name
    return data


@router.get("", response_model=TourListResponse)
async def list_tours(
    db: Annotated[AsyncSession, Depends(get_db)],
    city: str | None = None,
    country: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, description="Text search on name/description"),
    min_price: float | None = None,
    max_price: float | None = None,
    duration: int | None = None,
    owner_id: uuid.UUID | None = Query(None, description="Filter by owner admin"),
    sort_by: str = Query("created_at", pattern="^(created_at|price_per_person|avg_rating|duration_days|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Tour)

    if owner_id:
        query = query.where(Tour.owner_id == owner_id)
    if city:
        query = query.where(Tour.city.ilike(f"%{city}%"))
    if country:
        query = query.where(Tour.country.ilike(f"%{country}%"))
    if category:
        query = query.where(Tour.category == category)
    if min_price is not None:
        query = query.where(Tour.price_per_person >= min_price)
    if max_price is not None:
        query = query.where(Tour.price_per_person <= max_price)
    if duration:
        query = query.where(Tour.duration_days == duration)
    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Tour.name.ilike(pattern), Tour.description.ilike(pattern)))

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sort_col = getattr(Tour, sort_by)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    tours = result.scalars().all()

    return TourListResponse(
        items=[_tour_response(t) for t in tours],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.get("/{tour_id}", response_model=TourResponse)
async def get_tour(tour_id: uuid.UUID, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    return _tour_response(tour)


def _assert_tour_owner_or_superadmin(tour: Tour, user) -> None:
    if user.role == "superadmin":
        return
    if tour.owner_id and tour.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this tour",
        )


@router.post("", response_model=TourResponse, status_code=status.HTTP_201_CREATED)
async def create_tour(
    data: TourCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    existing = await db.execute(select(Tour).where(Tour.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    tour = Tour(**data.model_dump(), owner_id=current_user.id)
    db.add(tour)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.put("/{tour_id}", response_model=TourResponse)
async def replace_tour(
    tour_id: uuid.UUID,
    data: TourCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

    for field, value in data.model_dump().items():
        setattr(tour, field, value)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.patch("/{tour_id}", response_model=TourResponse)
async def update_tour(
    tour_id: uuid.UUID,
    data: TourUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tour, field, value)
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)


@router.delete("/{tour_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tour(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)
    await db.delete(tour)
    await db.flush()


@router.post("/{tour_id}/images", response_model=TourResponse)
async def upload_tour_images(
    tour_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    files: list[UploadFile] = File(...),
):
    from app.services.cloudinary_service import upload_images

    result = await db.execute(select(Tour).where(Tour.id == tour_id))
    tour = result.scalar_one_or_none()
    if not tour:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tour not found")
    _assert_tour_owner_or_superadmin(tour, current_user)

    urls = await upload_images(files, folder="tours")
    existing = tour.images or []
    tour.images = existing + urls
    await db.flush()
    await db.refresh(tour)
    return _tour_response(tour)
