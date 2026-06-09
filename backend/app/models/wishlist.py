import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wishlist(Base):
    __tablename__ = "wishlists"
    __table_args__ = (
        # Exactly one target: an internal hotel/tour OR an external LiteAPI
        # hotel / Viator tour (referenced by external id + display snapshot).
        CheckConstraint(
            "(CASE WHEN hotel_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN tour_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN liteapi_hotel_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN viator_product_code IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="wishlist_single_target",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    hotel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE")
    )
    tour_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tours.id", ondelete="CASCADE")
    )
    # External providers (no internal row): identifier + display snapshot.
    liteapi_hotel_id: Mapped[str | None] = mapped_column(String(255))
    viator_product_code: Mapped[str | None] = mapped_column(String(255))
    item_name: Mapped[str | None] = mapped_column(String(255))
    item_city: Mapped[str | None] = mapped_column(String(100))
    item_country: Mapped[str | None] = mapped_column(String(100))
    item_image: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="wishlists")
    hotel = relationship("Hotel", lazy="selectin")
    tour = relationship("Tour", lazy="selectin")
