import uuid
from datetime import datetime

from pydantic import BaseModel


class WishlistCreate(BaseModel):
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None


class WishlistResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WishlistListResponse(BaseModel):
    items: list[WishlistResponse]
    meta: dict
