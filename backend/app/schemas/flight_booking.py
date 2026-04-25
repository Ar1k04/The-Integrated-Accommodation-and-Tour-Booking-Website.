import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FlightBookingCreate(BaseModel):
    duffel_order_id: str = Field(min_length=1, max_length=100)
    duffel_booking_ref: str | None = Field(None, max_length=50)
    airline_name: str = Field(min_length=1, max_length=100)
    flight_number: str = Field(min_length=1, max_length=20)
    departure_airport: str = Field(min_length=3, max_length=10)
    arrival_airport: str = Field(min_length=3, max_length=10)
    departure_at: datetime
    arrival_at: datetime
    cabin_class: str | None = Field(None, max_length=20)
    passenger_name: str = Field(min_length=1, max_length=255)
    passenger_email: str = Field(min_length=3, max_length=255)
    base_amount: float = Field(ge=0)
    total_amount: float = Field(ge=0)
    currency: str = Field(default="VND", max_length=10)


class FlightBookingResponse(BaseModel):
    id: uuid.UUID
    duffel_order_id: str | None = None
    duffel_booking_ref: str | None = None
    airline_name: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_at: datetime
    arrival_at: datetime
    cabin_class: str | None = None
    passenger_name: str
    passenger_email: str
    base_amount: float
    total_amount: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FlightBookingUpdate(BaseModel):
    status: Literal["confirmed", "cancelled", "refunded"] | None = None
