from sqlalchemy import CHAR, Computed, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Country(Base):
    __tablename__ = "countries"
    __table_args__ = (UniqueConstraint("code", name="uq_countries_code"),)

    code: Mapped[str] = mapped_column(CHAR(2), nullable=False, index=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_norm: Mapped[str] = mapped_column(
        Text, Computed("f_unaccent(name)", persisted=True), nullable=False
    )
