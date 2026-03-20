import enum

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    user = "user"
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

    bookings = relationship("Booking", back_populates="user", lazy="selectin")
    tour_bookings = relationship("TourBooking", back_populates="user", lazy="selectin")
    reviews = relationship("Review", back_populates="user", lazy="selectin")
    wishlists = relationship("Wishlist", back_populates="user", lazy="selectin")
