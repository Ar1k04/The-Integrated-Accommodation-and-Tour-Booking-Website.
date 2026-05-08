import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Room(Base):
    __tablename__ = "rooms"

    hotel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hotels.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    price_per_night: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_guests: Mapped[int] = mapped_column(Integer, default=2, server_default="2")
    amenities: Mapped[dict | None] = mapped_column(JSONB, default=list)
    images: Mapped[dict | None] = mapped_column(JSONB, default=list)
    liteapi_room_id: Mapped[str | None] = mapped_column(String(100), index=True)

    hotel = relationship("Hotel", back_populates="rooms")
    booking_items = relationship("BookingItem", back_populates="room", lazy="selectin")
    availability = relationship(
        "RoomAvailability", back_populates="room", cascade="all, delete-orphan", lazy="selectin"
    )
