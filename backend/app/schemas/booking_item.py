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


class _FlightSummary(BaseModel):
    id: uuid.UUID
    airline_name: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_at: datetime
    arrival_at: datetime
    cabin_class: str | None = None
    passenger_name: str
    passenger_email: str
    total_amount: float
    currency: str
    status: str
    duffel_order_id: str | None = None
    duffel_booking_ref: str | None = None
    passenger_details: dict | None = None

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
    adults: int | None = Field(default=None, ge=1)
    children_ages: list[int] | None = Field(default=None)

    @model_validator(mode="after")
    def _normalise_occupancy(self) -> "RoomItemCreate":
        ages = self.children_ages or []
        for age in ages:
            if age < 0 or age > 17:
                raise ValueError("child age must be 0–17")
        if self.adults is None and ages:
            # Caller sent only children; assume guests_count counts adults too.
            self.adults = max(1, self.guests_count - len(ages))
        if self.adults is None:
            self.adults = self.guests_count
        total = self.adults + len(ages)
        if total != self.guests_count:
            # Keep guests_count consistent with adults + children for downstream
            # legacy consumers that still read guests_count.
            self.guests_count = total
        if self.children_ages is None:
            self.children_ages = []
        return self


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
    passengers: list[PassengerInfo] | None = None
    selected_services: list[dict] | None = None
    selected_seats: dict[str, str] | None = None
    quantity: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def check_flight_source(self) -> "FlightItemCreate":
        if not self.flight_booking_id and not self.duffel_offer_id:
            raise ValueError("Either flight_booking_id or duffel_offer_id must be set")
        if self.duffel_offer_id:
            if not self.passengers and not self.passenger:
                raise ValueError("passengers (list) is required when duffel_offer_id is set")
            if not self.passengers and self.passenger:
                self.passengers = [self.passenger]
            if self.passengers and len(self.passengers) != self.quantity:
                raise ValueError(
                    f"passengers count ({len(self.passengers)}) must equal quantity ({self.quantity})"
                )
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
    supplier_status: str | None = None
    supplier_status_synced_at: datetime | None = None
    adults_count: int | None = None
    children_count: int | None = None
    children_ages: list[int] | None = None
    unit_price: float
    subtotal: float
    quantity: int
    status: str
    created_at: datetime
    updated_at: datetime
    room: _RoomSummary | None = None
    flight_booking: _FlightSummary | None = None

    model_config = {"from_attributes": True}
