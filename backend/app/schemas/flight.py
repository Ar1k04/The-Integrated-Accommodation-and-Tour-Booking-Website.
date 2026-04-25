from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PassengerInfo(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    gender: Literal["M", "F", "m", "f"]
    born_on: date
    title: Literal["mr", "mrs", "ms", "dr"]
    phone_number: str | None = None


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
    cabin_class: str | None = None
    expires_at: str | None = None
    source: str = "duffel"
