import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wishlist(Base):
    __tablename__ = "wishlists"
    __table_args__ = (
        CheckConstraint(
            "(hotel_id IS NOT NULL AND tour_id IS NULL) OR (hotel_id IS NULL AND tour_id IS NOT NULL)",
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

    user = relationship("User", back_populates="wishlists")
    hotel = relationship("Hotel", lazy="selectin")
    tour = relationship("Tour", lazy="selectin")
