import typing
from datetime import datetime

if typing.TYPE_CHECKING:
    from models.shift_model import Shift

from sqlalchemy import (
    Float,
    String,
    Integer,
    DateTime,
    BigInteger,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helper import DateUtils
from models.base_model import BaseModel


class IncomeBalance(BaseModel):
    __tablename__ = "income_balance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    income_date: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: DateUtils.now, nullable=False
    )
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.id"), nullable=True
    )
    shift: Mapped["Shift"] = relationship("Shift", back_populates="income_records")
    trx_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sent_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
