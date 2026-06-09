import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.models.wishlist import Wishlist
from app.schemas.wishlist import WishlistCreate, WishlistListResponse, WishlistResponse

router = APIRouter(prefix="/wishlists", tags=["Wishlists"])


@router.get("", response_model=WishlistListResponse)
async def list_wishlists(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Wishlist).where(Wishlist.user_id == current_user.id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Wishlist.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    items = result.scalars().all()

    return WishlistListResponse(
        items=[WishlistResponse.model_validate(w) for w in items],
        meta={
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    )


@router.post("", response_model=WishlistResponse, status_code=status.HTTP_201_CREATED)
async def add_to_wishlist(
    data: WishlistCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    targets = {
        "hotel_id": data.hotel_id,
        "tour_id": data.tour_id,
        "liteapi_hotel_id": data.liteapi_hotel_id,
        "viator_product_code": data.viator_product_code,
    }
    provided = {k: v for k, v in targets.items() if v}
    if len(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of hotel_id, tour_id, liteapi_hotel_id or viator_product_code",
        )

    target_col, target_val = next(iter(provided.items()))
    existing_q = select(Wishlist).where(
        Wishlist.user_id == current_user.id,
        getattr(Wishlist, target_col) == target_val,
    )
    if (await db.execute(existing_q)).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in wishlist")

    item = Wishlist(user_id=current_user.id, **data.model_dump(exclude_none=True))
    db.add(item)
    await db.flush()
    # Eager-load the hotel/tour relationships so response serialization does not
    # trigger a lazy load outside the async greenlet.
    await db.refresh(item, attribute_names=["hotel", "tour"])
    return item


@router.delete("/{wishlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_wishlist(
    wishlist_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(Wishlist).where(Wishlist.id == wishlist_id, Wishlist.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wishlist item not found")
    await db.delete(item)
    await db.flush()
