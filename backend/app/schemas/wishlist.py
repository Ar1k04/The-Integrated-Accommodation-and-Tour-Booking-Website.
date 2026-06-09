import uuid
from datetime import datetime

from pydantic import BaseModel


class WishlistCreate(BaseModel):
    # Internal targets (FK to hotels.id / tours.id)
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None
    # External targets (LiteAPI hotel / Viator tour) + display snapshot
    liteapi_hotel_id: str | None = None
    viator_product_code: str | None = None
    item_name: str | None = None
    item_city: str | None = None
    item_country: str | None = None
    item_image: str | None = None


class WishlistHotelSummary(BaseModel):
    id: uuid.UUID
    name: str
    city: str | None = None
    country: str | None = None
    star_rating: int | None = None
    images: list | None = None

    model_config = {"from_attributes": True}


class WishlistTourSummary(BaseModel):
    id: uuid.UUID
    name: str
    city: str | None = None
    country: str | None = None
    images: list | None = None

    model_config = {"from_attributes": True}


class WishlistResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None
    liteapi_hotel_id: str | None = None
    viator_product_code: str | None = None
    item_name: str | None = None
    item_city: str | None = None
    item_country: str | None = None
    item_image: str | None = None
    created_at: datetime
    hotel: WishlistHotelSummary | None = None
    tour: WishlistTourSummary | None = None

    model_config = {"from_attributes": True}


class WishlistListResponse(BaseModel):
    items: list[WishlistResponse]
    meta: dict
