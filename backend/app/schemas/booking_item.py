import uuid
from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

from app.schemas.flight import PassengerInfo


class _RoomSummary(BaseModel):
    id: uuid.UUID
    name: str
    room_type: str

    model_config = {"from_attributes": True}


class RoomItemCreate(BaseModel):
    item_type: Literal["room"] = "room"
    room_id: uuid.UUID | None = None
    liteapi_rate_id: str | None = None
    liteapi_hotel_id: str | None = None
    liteapi_room_name: str | None = None
    liteapi_price: float | None = None
    check_in: date
    check_out: date
    quantity: int = Field(default=1, ge=1)
    guests_count: int = Field(default=1, ge=1)


class TourItemCreate(BaseModel):
    item_type: Literal["tour"] = "tour"
    tour_id: uuid.UUID | None = None
    viator_product_code: str | None = None
    viator_price: float | None = None
    viator_tour_name: str | None = None
    tour_date: date
    quantity: int = Field(default=1, ge=1)


class FlightItemCreate(BaseModel):
    item_type: Literal["flight"] = "flight"
    flight_booking_id: uuid.UUID | None = None
    duffel_offer_id: str | None = None
    passenger: PassengerInfo | None = None
    quantity: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def check_flight_source(self) -> "FlightItemCreate":
        if not self.flight_booking_id and not self.duffel_offer_id:
            raise ValueError("Either flight_booking_id or duffel_offer_id must be set")
        if self.duffel_offer_id and not self.passenger:
            raise ValueError("passenger is required when duffel_offer_id is set")
        return self


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
    liteapi_prebook_id: str | None = None
    liteapi_booking_id: str | None = None
    viator_product_code: str | None = None
    viator_booking_ref: str | None = None
    unit_price: float
    subtotal: float
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime
    room: _RoomSummary | None = None

    model_config = {"from_attributes": True}
