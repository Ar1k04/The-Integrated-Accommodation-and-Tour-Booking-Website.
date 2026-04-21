import enum
import uuid
from datetime import date as date_type

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RoomAvailabilityStatus(str, enum.Enum):
    available = "available"
    booked = "booked"
    blocked = "blocked"


class RoomAvailability(Base):
    __tablename__ = "room_availability"
    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'booked', 'blocked')",
            name="ck_room_availability_status",
        ),
        UniqueConstraint("room_id", "date", name="uq_room_date"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date_type] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=RoomAvailabilityStatus.available.value,
        server_default="available", nullable=False,
    )

    room = relationship("Room", back_populates="availability")
