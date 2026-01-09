from datetime import datetime
import uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, Text, UniqueConstraint

class Base(DeclarativeBase):
    pass

class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_reviews_order_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True, unique=True)
    order_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    partner_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())
