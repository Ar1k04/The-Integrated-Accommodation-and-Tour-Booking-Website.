import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class TourBookingCreate(BaseModel):
    tour_id: uuid.UUID
    tour_date: date
    participants_count: int = Field(default=1, ge=1)
    special_requests: str | None = None


class TourBookingUpdate(BaseModel):
    participants_count: int | None = Field(None, ge=1)
    special_requests: str | None = None


class TourBookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tour_id: uuid.UUID
    tour_date: date
    participants_count: int
    total_price: float
    status: str
    special_requests: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TourBookingListResponse(BaseModel):
    items: list[TourBookingResponse]
    meta: dict
