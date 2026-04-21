import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class RoomItemCreate(BaseModel):
    item_type: Literal["room"] = "room"
    room_id: uuid.UUID
    check_in: date
    check_out: date
    quantity: int = Field(default=1, ge=1)
    guests_count: int = Field(default=1, ge=1)


class TourItemCreate(BaseModel):
    item_type: Literal["tour"] = "tour"
    tour_id: uuid.UUID
    tour_date: date
    quantity: int = Field(default=1, ge=1)


class FlightItemCreate(BaseModel):
    item_type: Literal["flight"] = "flight"
    flight_booking_id: uuid.UUID
    quantity: int = Field(default=1, ge=1)


BookingItemCreate = Annotated[
    Union[RoomItemCreate, TourItemCreate, FlightItemCreate],
    Field(discriminator="item_type"),
]


class BookingItemResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID
    item_type: str
    room_id: uuid.UUID | None = None
    check_in: date | None = None
    check_out: date | None = None
    tour_schedule_id: uuid.UUID | None = None
    flight_booking_id: uuid.UUID | None = None
    unit_price: float
    subtotal: float
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
