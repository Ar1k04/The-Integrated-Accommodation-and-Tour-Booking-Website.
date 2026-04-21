import uuid

from sqlalchemy import Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Hotel(Base):
    __tablename__ = "hotels"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    star_rating: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    property_type: Mapped[str | None] = mapped_column(String(50))
    amenities: Mapped[dict | None] = mapped_column(JSONB, default=list)
    images: Mapped[dict | None] = mapped_column(JSONB, default=list)
    base_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", server_default="USD")
    avg_rating: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    liteapi_hotel_id: Mapped[str | None] = mapped_column(String(100), index=True)

    rooms = relationship("Room", back_populates="hotel", lazy="selectin", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="hotel", lazy="selectin")
