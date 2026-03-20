import enum
import uuid

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class Booking(Base):
    __tablename__ = "bookings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    check_in: Mapped[str] = mapped_column(Date, index=True, nullable=False)
    check_out: Mapped[str] = mapped_column(Date, index=True, nullable=False)
    guests_count: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=BookingStatus.pending.value, server_default="pending"
    )
    special_requests: Mapped[str | None] = mapped_column(Text)
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("promo_codes.id", ondelete="SET NULL")
    )

    user = relationship("User", back_populates="bookings")
    room = relationship("Room", back_populates="bookings")
    payment = relationship("Payment", back_populates="booking", uselist=False, lazy="selectin")
