import enum
import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


class PaymentProvider(str, enum.Enum):
    stripe = "stripe"


class Payment(Base):
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(
        String(20), default=PaymentProvider.stripe.value, server_default="stripe"
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    refunded_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="usd", server_default="usd")
    status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.pending.value, server_default="pending"
    )
    # Populated when payment_intent.payment_failed fires (decline diagnostics).
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decline_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    booking = relationship("Booking", back_populates="payments")
