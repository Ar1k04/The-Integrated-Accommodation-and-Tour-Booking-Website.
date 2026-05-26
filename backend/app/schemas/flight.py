from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class PassengerInfo(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    gender: Literal["M", "F", "m", "f"]
    born_on: date
    title: Literal["mr", "mrs", "ms", "dr"]
    # Duffel / airlines reject orders with blank phone numbers (e.g. Vietnam
    # Airlines returns `validation_required: Field 'phone_number' can't be
    # blank`). We require it at our boundary so the error surfaces in the
    # form instead of after Stripe charges and we have to refund.
    phone_number: str = Field(min_length=5, max_length=30)
    # Optional age + type for child / infant pricing. When `age` is set,
    # Duffel + the airline decide whether the passenger maps to child or
    # infant_without_seat (we do not pre-classify on our side).
    age: int | None = Field(default=None, ge=0, le=120)
    passenger_type: Literal["adult", "child", "infant_without_seat"] | None = None


class PassengerBreakdown(BaseModel):
    """One row in the offer's passenger list — used by the frontend to label
    each passenger form ("Adult passenger 1", "Child age 8 — passenger 2")."""
    passenger_id: str | None = None
    type: str | None = None
    age: int | None = None


class FlightSegmentResponse(BaseModel):
    flight_number: str
    airline_name: str
    airline_iata: str
    origin_iata: str
    origin_name: str
    destination_iata: str
    destination_name: str
    departure_at: str
    arrival_at: str
    duration: str | None = None
    aircraft: str | None = None


class FlightSliceResponse(BaseModel):
    origin: str
    destination: str
    duration: str | None = None
    segments: list[FlightSegmentResponse]


class FlightOfferResponse(BaseModel):
    duffel_offer_id: str
    total_amount: float
    currency: str
    airline_name: str
    airline_iata: str
    slices: list[FlightSliceResponse]
    passengers: int = 1
    passenger_breakdown: list[PassengerBreakdown] | None = None
    cabin_class: str | None = None
    expires_at: str | None = None
    source: str = "duffel"
