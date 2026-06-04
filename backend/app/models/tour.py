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
    # Total run-time in minutes (e.g. a 3-hour walking tour = 180). Lets Partner
    # tours match the same minute-based "Duration" filter Viator products use.
    # Nullable: legacy/seeded tours fall back to ``duration_days`` at filter time.
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    max_participants: Mapped[int] = mapped_column(Integer, default=20)
    price_per_person: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    highlights: Mapped[dict | None] = mapped_column(JSONB, default=list)
    itinerary: Mapped[dict | None] = mapped_column(JSONB, default=list)
    includes: Mapped[dict | None] = mapped_column(JSONB, default=list)
    excludes: Mapped[dict | None] = mapped_column(JSONB, default=list)
    images: Mapped[dict | None] = mapped_column(JSONB, default=list)
    # Supplier-style age bands (mirrors Viator `pricingInfo.ageBands[]`). Each
    # entry: {age_band, start_age, end_age, min_travelers, max_travelers, price}.
    # Partner tours define their own bands + per-person price so they share the
    # same detail page, availability check, and child-pricing as Viator tours.
    age_bands: Mapped[dict | None] = mapped_column(JSONB, default=list)
    # Supplier feature flags (subset of Viator's product flags) the Partner can
    # set, e.g. ["FREE_CANCELLATION", "PRIVATE_TOUR"]. Lets Partner tours match
    # the same "Features" filter as Viator products. See PARTNER_SETTABLE_FLAGS.
    flags: Mapped[dict | None] = mapped_column(JSONB, default=list)
    avg_rating: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    viator_product_code: Mapped[str | None] = mapped_column(String(100), index=True)

    owner = relationship("User", back_populates="tours", lazy="selectin")
    reviews = relationship("Review", back_populates="tour", lazy="selectin")
    schedules = relationship(
        "TourSchedule", back_populates="tour", cascade="all, delete-orphan", lazy="selectin"
    )
