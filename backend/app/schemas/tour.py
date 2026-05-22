import uuid
from datetime import datetime
from typing import Literal

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


class TourAgeBand(BaseModel):
    """Supplier-defined age band for a Viator product.

    Each Viator supplier publishes its own age ranges in
    ``pricingInfo.ageBands[]``; the frontend uses this list to validate
    child age input and to render "Children 4-12 yrs only" hints.
    """
    age_band: str
    start_age: int = 0
    end_age: int = 99
    min_travelers: int = 0
    max_travelers: int = 99


class TourResponse(BaseModel):
    id: uuid.UUID | None = None
    name: str
    slug: str | None = None
    description: str | None = None
    city: str
    country: str | None = None
    category: str | None = None
    duration_days: int = 1
    max_participants: int = 20
    price_per_person: float = 0
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None
    avg_rating: float = 0
    total_reviews: int = 0
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source: Literal["local", "viator"] = "local"
    viator_product_code: str | None = None
    age_bands: list[TourAgeBand] | None = None

    model_config = {"from_attributes": True}


class TourAvailabilityResponse(BaseModel):
    available: bool
    price: float
    currency: str
    tour_date: str
    paxmix_used: list[dict] | None = None


class TourListResponse(BaseModel):
    items: list[TourResponse]
    meta: dict


class ViatorTag(BaseModel):
    tag_id: int
    parent_tag_id: int | None = None
    name: str
    names_by_locale: dict[str, str] = Field(default_factory=dict)


class ViatorTagsResponse(BaseModel):
    tags: list[ViatorTag]
