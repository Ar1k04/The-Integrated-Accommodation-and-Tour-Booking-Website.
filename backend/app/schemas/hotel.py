import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class HotelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=255)
    description: str | None = None
    address: str | None = None
    city: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    latitude: float | None = None
    longitude: float | None = None
    star_rating: int = Field(default=3, ge=1, le=5)
    property_type: str | None = None
    amenities: list | None = None
    images: list | None = None
    # Hotel price is derived from the hotel's rooms (min room price),
    # but the DB model still has `base_price` as a required field.
    # So we make it optional in the API and default it server-side on create.
    base_price: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", max_length=10)


class HotelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    star_rating: int | None = Field(None, ge=1, le=5)
    property_type: str | None = None
    amenities: list | None = None
    images: list | None = None
    base_price: float | None = Field(None, gt=0)
    currency: str | None = Field(None, max_length=10)


class OwnerInfo(BaseModel):
    id: uuid.UUID
    full_name: str

    model_config = {"from_attributes": True}


class HotelResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    address: str | None = None
    city: str
    country: str
    latitude: float | None = None
    longitude: float | None = None
    star_rating: int
    property_type: str | None = None
    amenities: list | None = None
    images: list | None = None
    base_price: float
    # Minimum room price for this hotel (optionally date-filtered by list queries).
    min_room_price: float | None = None
    currency: str = "USD"
    avg_rating: float
    total_reviews: int
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HotelListResponse(BaseModel):
    items: list[HotelResponse]
    meta: dict
