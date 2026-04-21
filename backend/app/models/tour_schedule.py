import uuid
from datetime import date as date_type

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TourSchedule(Base):
    __tablename__ = "tour_schedule"
    __table_args__ = (
        CheckConstraint("booked_slots <= total_slots", name="ck_tour_schedule_capacity"),
        UniqueConstraint("tour_id", "available_date", name="uq_tour_date"),
    )

    tour_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tours.id", ondelete="CASCADE"), index=True, nullable=False
    )
    available_date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    total_slots: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    booked_slots: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    tour = relationship("Tour", back_populates="schedules")
    booking_items = relationship("BookingItem", back_populates="tour_schedule", lazy="selectin")
