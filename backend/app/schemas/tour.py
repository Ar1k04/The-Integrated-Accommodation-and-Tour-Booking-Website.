import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.tour_taxonomy import PARTNER_SETTABLE_FLAGS


class TourAgeBand(BaseModel):
    """Supplier-defined age band for a tour product.

    Mirrors Viator's ``pricingInfo.ageBands[]`` — each supplier (Viator OR a
    platform Partner) publishes its own age ranges; the frontend uses this
    list to validate child age input and render "Children 4-12 yrs only"
    hints. ``price`` is the per-person price for the band: Partner tours set
    it so the shared availability/booking flow can price each traveler by
    band; Viator leaves it ``None`` (price comes from the live quote).
    """
    age_band: str
    start_age: int = 0
    end_age: int = 99
    min_travelers: int = 0
    max_travelers: int = 99
    price: float | None = None


class TourCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Auto-generated from `name` server-side when omitted (mirrors HotelCreate).
    slug: str | None = Field(None, max_length=255)
    description: str | None = None
    city: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    category: str | None = None
    duration_days: int = Field(default=1, ge=1)
    # Total run-time in minutes; powers the minute-based "Duration" filter.
    duration_minutes: int | None = Field(default=None, ge=0)
    max_participants: int = Field(default=20, ge=1)
    price_per_person: float = Field(gt=0)
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None
    # Supplier feature flags the Partner guarantees (subset of Viator flags).
    flags: list[str] | None = None
    # Partner must define age bands (incl. an ADULT band) so the tour shares
    # the same age-band-aware detail page / availability / pricing as Viator.
    age_bands: list[TourAgeBand] | None = None

    @field_validator("flags")
    @classmethod
    def _validate_flags(cls, v: list[str] | None) -> list[str] | None:
        if not v:
            return v
        invalid = [f for f in v if f not in PARTNER_SETTABLE_FLAGS]
        if invalid:
            raise ValueError(
                f"Unsupported tour flags: {invalid}. "
                f"Allowed: {PARTNER_SETTABLE_FLAGS}"
            )
        # De-dupe while preserving order.
        return list(dict.fromkeys(v))

    @model_validator(mode="after")
    def _require_adult_band(self) -> "TourCreate":
        bands = self.age_bands or []
        if not bands:
            raise ValueError("age_bands is required: define at least an ADULT band")
        adult = next(
            (b for b in bands if (b.age_band or "").strip().upper() == "ADULT"), None
        )
        if adult is None:
            raise ValueError("age_bands must include an ADULT band")
        if not adult.price or adult.price <= 0:
            raise ValueError("the ADULT age band must have a price > 0")
        for b in bands:
            if b.start_age > b.end_age:
                raise ValueError(
                    f"age band '{b.age_band}' has start_age > end_age"
                )
            if b.price is not None and b.price < 0:
                raise ValueError(f"age band '{b.age_band}' price cannot be negative")
        return self


class TourUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    city: str | None = None
    country: str | None = None
    category: str | None = None
    duration_days: int | None = Field(None, ge=1)
    duration_minutes: int | None = Field(None, ge=0)
    max_participants: int | None = Field(None, ge=1)
    price_per_person: float | None = Field(None, gt=0)
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None
    flags: list[str] | None = None
    age_bands: list[TourAgeBand] | None = None

    @field_validator("flags")
    @classmethod
    def _validate_flags(cls, v: list[str] | None) -> list[str] | None:
        if not v:
            return v
        invalid = [f for f in v if f not in PARTNER_SETTABLE_FLAGS]
        if invalid:
            raise ValueError(
                f"Unsupported tour flags: {invalid}. "
                f"Allowed: {PARTNER_SETTABLE_FLAGS}"
            )
        return list(dict.fromkeys(v))


class TourResponse(BaseModel):
    id: uuid.UUID | None = None
    name: str
    slug: str | None = None
    description: str | None = None
    city: str
    country: str | None = None
    category: str | None = None
    # Viator tag ID behind `category` (None for Partner tours). Lets the
    # frontend localize the category name to the active UI language.
    category_tag_id: int | None = None
    duration_days: int = 1
    duration_minutes: int | None = None
    max_participants: int = 20
    price_per_person: float = 0
    highlights: list | None = None
    itinerary: list | None = None
    includes: list | None = None
    excludes: list | None = None
    images: list | None = None
    flags: list[str] | None = None
    avg_rating: float = 0
    total_reviews: int = 0
    owner_id: uuid.UUID | None = None
    owner_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source: Literal["local", "viator"] = "local"
    viator_product_code: str | None = None
    age_bands: list[TourAgeBand] | None = None
    # Multi-destination context — set for Viator tours that visit more than
    # one place (e.g. a Halong Bay cruise sold from Hanoi). `destinations` is
    # the full list from the product; `departs_from` is the searched-against
    # destination when it differs from the primary `city` so the card can
    # render "Departs from Hanoi".
    destinations: list[str] | None = None
    departs_from: str | None = None

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


class ViatorDestination(BaseModel):
    destination_id: str
    name: str
    type: str
    parent_destination_id: str | None = None


class ViatorDestinationsResponse(BaseModel):
    destinations: list[ViatorDestination]
