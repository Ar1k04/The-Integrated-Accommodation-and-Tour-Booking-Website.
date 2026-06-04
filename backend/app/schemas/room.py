import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChildAgeTier(BaseModel):
    min_age: int = Field(ge=0, le=17)
    max_age: int = Field(ge=0, le=17)
    discount_percent: int = Field(ge=0, le=100)


def _validate_tier_list(v: list[dict] | None) -> list[dict] | None:
    if v is None:
        return v
    parsed = [ChildAgeTier(**t).model_dump() for t in v]
    for t in parsed:
        if t["min_age"] > t["max_age"]:
            raise ValueError("min_age must be ≤ max_age")
    return parsed


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    room_type: str = Field(min_length=1, max_length=50)
    price_per_night: float = Field(gt=0)
    total_quantity: int = Field(default=1, ge=1)
    max_guests: int = Field(default=2, ge=1)
    amenities: list | None = None
    images: list | None = None
    child_age_tiers: list[dict] | None = None
    refundable: bool = True
    free_cancellation_days: int = Field(default=1, ge=0)
    cancellation_fee_percent: float = Field(default=20, ge=0, le=100)

    @field_validator("child_age_tiers")
    @classmethod
    def _check_tiers(cls, v):
        return _validate_tier_list(v)


class RoomUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    room_type: str | None = None
    price_per_night: float | None = Field(None, gt=0)
    total_quantity: int | None = Field(None, ge=1)
    max_guests: int | None = Field(None, ge=1)
    amenities: list | None = None
    images: list | None = None
    child_age_tiers: list[dict] | None = None
    refundable: bool | None = None
    free_cancellation_days: int | None = Field(None, ge=0)
    cancellation_fee_percent: float | None = Field(None, ge=0, le=100)

    @field_validator("child_age_tiers")
    @classmethod
    def _check_tiers(cls, v):
        return _validate_tier_list(v)


class RoomResponse(BaseModel):
    id: uuid.UUID
    hotel_id: uuid.UUID
    name: str
    description: str | None = None
    room_type: str
    price_per_night: float
    total_quantity: int
    max_guests: int
    amenities: list | None = None
    images: list | None = None
    child_age_tiers: list | None = None
    refundable: bool = True
    free_cancellation_days: int = 1
    cancellation_fee_percent: float = 20
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoomListResponse(BaseModel):
    items: list[RoomResponse]
    meta: dict


class RoomAvailabilityResponse(BaseModel):
    available: bool
    rooms_left: int
