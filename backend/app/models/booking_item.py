import enum
import uuid
from datetime import date as date_type

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BookingItemType(str, enum.Enum):
    room = "room"
    tour = "tour"
    flight = "flight"


class BookingItemStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class BookingItem(Base):
    __tablename__ = "booking_item"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('room', 'tour', 'flight')",
            name="ck_booking_item_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'completed')",
            name="ck_booking_item_status",
        ),
        CheckConstraint(
            "(item_type = 'room' AND room_id IS NOT NULL AND tour_schedule_id IS NULL AND flight_booking_id IS NULL) "
            "OR (item_type = 'tour' AND tour_schedule_id IS NOT NULL AND room_id IS NULL AND flight_booking_id IS NULL) "
            "OR (item_type = 'flight' AND flight_booking_id IS NOT NULL AND room_id IS NULL AND tour_schedule_id IS NULL)",
            name="ck_booking_item_target",
        ),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="SET NULL"), index=True
    )
    check_in: Mapped[date_type | None] = mapped_column(Date)
    check_out: Mapped[date_type | None] = mapped_column(Date)
    tour_schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tour_schedule.id", ondelete="SET NULL"), index=True
    )
    flight_booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("flight_booking.id", ondelete="SET NULL"), index=True
    )
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=BookingItemStatus.pending.value,
        server_default="pending", nullable=False,
    )

    booking = relationship("Booking", back_populates="items")
    room = relationship("Room", back_populates="booking_items")
    tour_schedule = relationship("TourSchedule", back_populates="booking_items")
    flight_booking = relationship("FlightBooking", back_populates="booking_items")
    review = relationship("Review", back_populates="booking_item", uselist=False)
