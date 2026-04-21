import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoyaltyTierResponse(BaseModel):
    id: uuid.UUID
    name: str
    min_points: int
    max_points: int
    benefits: str | None = None
    discount_percent: float

    model_config = {"from_attributes": True}


class LoyaltyTransactionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    booking_id: uuid.UUID | None = None
    points: int
    type: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyStatusResponse(BaseModel):
    user_id: uuid.UUID
    total_points: int
    current_tier: LoyaltyTierResponse | None = None
    next_tier: LoyaltyTierResponse | None = None
    points_to_next_tier: int = 0
    recent_transactions: list[LoyaltyTransactionResponse] = []


class LoyaltyRedeemRequest(BaseModel):
    points: int = Field(gt=0)
    booking_id: uuid.UUID | None = None


class LoyaltyRedeemResponse(BaseModel):
    redeemed_points: int
    discount_amount: float
    remaining_points: int
