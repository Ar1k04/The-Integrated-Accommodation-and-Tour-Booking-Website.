import enum
import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
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

    special_requests: Mapped[str | None] = mapped_column(Text)

    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=BookingStatus.pending.value, server_default="pending"
    )

    voucher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vouchers.id", ondelete="SET NULL"), index=True
    )
    discount_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    points_earned: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    points_redeemed: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    user = relationship("User", back_populates="bookings")
    payments = relationship("Payment", back_populates="booking", lazy="selectin", order_by="Payment.created_at.desc()")
    items = relationship(
        "BookingItem", back_populates="booking", cascade="all, delete-orphan", lazy="selectin"
    )
    voucher = relationship("Voucher", back_populates="bookings")
    voucher_usages = relationship(
        "VoucherUsage", back_populates="booking", cascade="all, delete-orphan", lazy="selectin"
    )
    loyalty_transactions = relationship(
        "LoyaltyTransaction", back_populates="booking", lazy="selectin"
    )
