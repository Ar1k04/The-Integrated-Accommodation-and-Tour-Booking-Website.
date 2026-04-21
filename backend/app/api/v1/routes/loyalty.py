from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.loyalty import (
    LoyaltyRedeemRequest,
    LoyaltyRedeemResponse,
    LoyaltyStatusResponse,
    LoyaltyTierResponse,
    LoyaltyTransactionResponse,
)
from app.services import loyalty_service
from app.services.loyalty_service import LoyaltyError

router = APIRouter(prefix="/loyalty", tags=["Loyalty"])


@router.get("/me", response_model=LoyaltyStatusResponse)
async def get_my_loyalty(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    try:
        data = await loyalty_service.get_status(db, current_user.id)
    except LoyaltyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return LoyaltyStatusResponse(
        user_id=data["user_id"],
        total_points=data["total_points"],
        current_tier=LoyaltyTierResponse.model_validate(data["current_tier"]) if data["current_tier"] else None,
        next_tier=LoyaltyTierResponse.model_validate(data["next_tier"]) if data["next_tier"] else None,
        points_to_next_tier=data["points_to_next_tier"],
        recent_transactions=[
            LoyaltyTransactionResponse.model_validate(t) for t in data["recent_transactions"]
        ],
    )


@router.post("/redeem", response_model=LoyaltyRedeemResponse)
async def redeem_loyalty_points(
    data: LoyaltyRedeemRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    try:
        _, discount = await loyalty_service.redeem_points(
            db,
            user_id=current_user.id,
            booking_id=data.booking_id,
            points=data.points,
            description=f"Redemption by {current_user.email}",
        )
    except LoyaltyError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await db.refresh(current_user)
    return LoyaltyRedeemResponse(
        redeemed_points=data.points,
        discount_amount=float(discount),
        remaining_points=current_user.loyalty_points or 0,
    )
