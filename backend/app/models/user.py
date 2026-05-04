import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    user = "user"
    partner = "partner"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.user.value, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    loyalty_points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    preferred_locale: Mapped[str] = mapped_column(String(2), default="en", server_default="en", nullable=False)
    preferred_currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    loyalty_tier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loyalty_tier.id", ondelete="SET NULL"), index=True
    )

    @property
    def total_points(self) -> int:
        """Alias matching the target schema (docs/Project.sql). Backed by loyalty_points."""
        return self.loyalty_points

    bookings = relationship("Booking", back_populates="user", lazy="selectin")
    reviews = relationship("Review", back_populates="user", lazy="selectin")
    wishlists = relationship("Wishlist", back_populates="user", lazy="selectin")
    loyalty_tier = relationship("LoyaltyTier", back_populates="users")
    loyalty_transactions = relationship(
        "LoyaltyTransaction", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    vouchers_owned = relationship(
        "Voucher", back_populates="admin", foreign_keys="Voucher.admin_id", lazy="selectin"
    )
    voucher_usages = relationship(
        "VoucherUsage", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    hotels = relationship("Hotel", back_populates="owner", lazy="noload")
    tours = relationship("Tour", back_populates="owner", lazy="noload")
