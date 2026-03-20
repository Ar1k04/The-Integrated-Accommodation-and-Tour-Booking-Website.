import enum
import uuid

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TourBookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class TourBooking(Base):
    __tablename__ = "tour_bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tour_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tours.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tour_date: Mapped[str] = mapped_column(Date, nullable=False)
    participants_count: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=TourBookingStatus.pending.value, server_default="pending"
    )
    special_requests: Mapped[str | None] = mapped_column(Text)

    user = relationship("User", back_populates="tour_bookings")
    tour = relationship("Tour", back_populates="tour_bookings")
