import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.room import RoomResponse


class BookingCreate(BaseModel):
    room_id: uuid.UUID
    check_in: date
    check_out: date
    guests_count: int = Field(default=1, ge=1)
    special_requests: str | None = None
    promo_code: str | None = None


class BookingUpdate(BaseModel):
    guests_count: int | None = Field(None, ge=1)
    special_requests: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    room_id: uuid.UUID
    check_in: date
    check_out: date
    guests_count: int
    total_price: float
    status: str
    special_requests: str | None = None
    promo_code_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BookingDetailResponse(BookingResponse):
    room: RoomResponse | None = None


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    meta: dict
