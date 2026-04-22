import uuid

from sqlalchemy import Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Tour(Base):
    __tablename__ = "tours"

    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))
    duration_days: Mapped[int] = mapped_column(Integer, default=1)
    max_participants: Mapped[int] = mapped_column(Integer, default=20)
    price_per_person: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    highlights: Mapped[dict | None] = mapped_column(JSONB, default=list)
    itinerary: Mapped[dict | None] = mapped_column(JSONB, default=list)
    includes: Mapped[dict | None] = mapped_column(JSONB, default=list)
    excludes: Mapped[dict | None] = mapped_column(JSONB, default=list)
    images: Mapped[dict | None] = mapped_column(JSONB, default=list)
    avg_rating: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    viator_product_code: Mapped[str | None] = mapped_column(String(100), index=True)

    owner = relationship("User", back_populates="tours", lazy="selectin")
    tour_bookings = relationship("TourBooking", back_populates="tour", lazy="selectin")
    reviews = relationship("Review", back_populates="tour", lazy="selectin")
    schedules = relationship(
        "TourSchedule", back_populates="tour", cascade="all, delete-orphan", lazy="selectin"
    )
