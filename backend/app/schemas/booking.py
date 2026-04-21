import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.booking_item import BookingItemCreate, BookingItemResponse
from app.schemas.room import RoomResponse


class BookingCreate(BaseModel):
    """New cart-style booking payload — list of items plus optional voucher and points redemption."""

    items: list[BookingItemCreate] = Field(min_length=1)
    voucher_code: str | None = None
    points_to_redeem: int = Field(default=0, ge=0)
    special_requests: str | None = None


class LegacyBookingCreate(BaseModel):
    """Old single-room booking payload. Adapter wraps it into a one-item BookingCreate."""

    room_id: uuid.UUID
    check_in: date
    check_out: date
    guests_count: int = Field(default=1, ge=1)
    special_requests: str | None = None
    promo_code: str | None = None


class BookingUpdate(BaseModel):
    guests_count: int | None = Field(None, ge=1)
    special_requests: str | None = None
    status: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    # Legacy single-room fields — present for backwards compatibility; null for multi-item bookings.
    room_id: uuid.UUID | None = None
    check_in: date | None = None
    check_out: date | None = None
    guests_count: int | None = None
    total_price: float
    status: str
    special_requests: str | None = None
    promo_code_id: uuid.UUID | None = None
    voucher_id: uuid.UUID | None = None
    discount_amount: float = 0
    points_earned: int = 0
    points_redeemed: int = 0
    created_at: datetime
    updated_at: datetime
    items: list[BookingItemResponse] = []

    model_config = {"from_attributes": True}


class BookingDetailResponse(BookingResponse):
    room: RoomResponse | None = None


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    meta: dict
