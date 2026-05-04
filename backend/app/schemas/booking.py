import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.booking_item import BookingItemCreate, BookingItemResponse


class BookingCreate(BaseModel):
    """Cart-style booking payload — list of items plus optional voucher and points redemption."""

    items: list[BookingItemCreate] = Field(min_length=1)
    voucher_code: str | None = None
    points_to_redeem: int = Field(default=0, ge=0)
    special_requests: str | None = None


class BookingUpdate(BaseModel):
    special_requests: str | None = None
    status: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    total_price: float
    status: str
    special_requests: str | None = None
    voucher_id: uuid.UUID | None = None
    discount_amount: float = 0
    points_earned: int = 0
    points_redeemed: int = 0
    created_at: datetime
    updated_at: datetime
    items: list[BookingItemResponse] = []

    model_config = {"from_attributes": True}


class BookingDetailResponse(BookingResponse):
    pass


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    meta: dict
