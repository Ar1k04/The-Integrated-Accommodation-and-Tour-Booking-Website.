import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class ReviewCreate(BaseModel):
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None
    viator_product_code: str | None = None
    liteapi_hotel_id: str | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ReviewUpdate(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = None


class ReviewResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    hotel_id: uuid.UUID | None = None
    tour_id: uuid.UUID | None = None
    viator_product_code: str | None = None
    liteapi_hotel_id: str | None = None
    rating: int
    comment: str | None = None
    created_at: datetime
    updated_at: datetime
    user: UserResponse | None = None

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    meta: dict


# Loose review schema used to merge user-written reviews (local DB) with
# read-only supplier reviews (Viator API, LiteAPI). Suppliers don't expose
# user_id / updated_at, and LiteAPI ratings are fractional, so this stays
# deliberately permissive compared to ReviewResponse.
class ExternalReviewUser(BaseModel):
    full_name: str


class ExternalReviewItem(BaseModel):
    id: str
    rating: float
    comment: str | None = None
    created_at: datetime
    user: ExternalReviewUser | None = None


class ExternalReviewListResponse(BaseModel):
    items: list[ExternalReviewItem]
    meta: dict
