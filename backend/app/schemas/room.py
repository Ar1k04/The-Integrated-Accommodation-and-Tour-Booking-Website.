import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    room_type: str = Field(min_length=1, max_length=50)
    price_per_night: float = Field(gt=0)
    total_quantity: int = Field(default=1, ge=1)
    max_guests: int = Field(default=2, ge=1)
    amenities: list | None = None
    images: list | None = None


class RoomUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    room_type: str | None = None
    price_per_night: float | None = Field(None, gt=0)
    total_quantity: int | None = Field(None, ge=1)
    max_guests: int | None = Field(None, ge=1)
    amenities: list | None = None
    images: list | None = None


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
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoomListResponse(BaseModel):
    items: list[RoomResponse]
    meta: dict


class RoomAvailabilityResponse(BaseModel):
    available: bool
    rooms_left: int
