import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FlightBookingStatus(str, enum.Enum):
    confirmed = "confirmed"
    cancelled = "cancelled"
    refunded = "refunded"


class FlightBooking(Base):
    __tablename__ = "flight_booking"
    __table_args__ = (
        CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'refunded')",
            name="ck_flight_booking_status",
        ),
    )

    duffel_order_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    duffel_booking_ref: Mapped[str | None] = mapped_column(String(50))
    airline_name: Mapped[str] = mapped_column(String(100), nullable=False)
    flight_number: Mapped[str] = mapped_column(String(20), nullable=False)
    departure_airport: Mapped[str] = mapped_column(String(10), nullable=False)
    arrival_airport: Mapped[str] = mapped_column(String(10), nullable=False)
    departure_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cabin_class: Mapped[str | None] = mapped_column(String(20))
    passenger_name: Mapped[str] = mapped_column(String(255), nullable=False)
    passenger_email: Mapped[str] = mapped_column(String(255), nullable=False)
    base_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="VND", server_default="VND", nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=FlightBookingStatus.confirmed.value,
        server_default="confirmed", nullable=False,
    )

    booking_items = relationship("BookingItem", back_populates="flight_booking", lazy="selectin")
