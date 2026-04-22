import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TourCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = None
    city: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    category: str | None = None
    duration_days: int = Field(default=1, ge=1)
    max_participants: int = Field(default=20, ge=1)
    price_per_person: float = Field(gt=0)
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None


class TourUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    city: str | None = None
    country: str | None = None
    category: str | None = None
    duration_days: int | None = Field(None, ge=1)
    max_participants: int | None = Field(None, ge=1)
    price_per_person: float | None = Field(None, gt=0)
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None


class TourResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    city: str
    country: str
    category: str | None = None
    duration_days: int
    max_participants: int
    price_per_person: float
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None
    avg_rating: float
    total_reviews: int
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TourListResponse(BaseModel):
    items: list[TourResponse]
    meta: dict
