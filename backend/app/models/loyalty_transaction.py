import enum
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoyaltyTransactionType(str, enum.Enum):
    earn = "earn"
    redeem = "redeem"
    adjust = "adjust"


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transaction"
    __table_args__ = (
        CheckConstraint(
            "type IN ('earn', 'redeem', 'adjust')",
            name="ck_loyalty_transaction_type",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL"), index=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    user = relationship("User", back_populates="loyalty_transactions")
    booking = relationship("Booking", back_populates="loyalty_transactions")
