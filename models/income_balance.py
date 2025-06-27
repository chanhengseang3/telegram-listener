from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Optional, Generator, Any

from sqlalchemy import (
    Float,
    String,
    Column,
    Integer,
    DateTime,
    BigInteger,
    Text,
    func,
)
import pytz as pytz
from sqlalchemy import Float, String, Column, Integer, DateTime, BigInteger, Text
from sqlalchemy.orm import Session

from config.database_config import Base, SessionLocal


class CurrencyEnum(Enum):
    KHR = "៛"
    USD = "$"

    @classmethod
    def from_symbol(cls, symbol: str) -> Optional[str]:
        for member in cls:
            if member.value == symbol:
                return member.name
        return None


class IncomeBalance(Base):
    __tablename__ = "income_balance"
    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    chat_id = Column(BigInteger, nullable=False)
    currency = Column(String(16), nullable=False)
    original_amount = Column(Float, nullable=False)
    income_date = Column(DateTime, default=datetime.now, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    message = Column(Text, nullable=False)
    trx_id = Column(String(50), nullable=False)


class IncomeService:
    def __init__(self):
        self._session_factory = SessionLocal

    @contextmanager
    def _get_db(self) -> Generator[Session, Any, Any]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    async def insert_income(
        self,
        chat_id: int,
        amount: float,
        currency: str,
        original_amount: float,
        message_id: int,
        message: str,
        trx_id: str,
    ) -> IncomeBalance:
        from_symbol = CurrencyEnum.from_symbol(currency)
        currency_code = from_symbol if from_symbol else currency
        tz = pytz.timezone("Asia/Phnom_Penh")
        current_date = datetime.now(tz)

        with self._get_db() as db:
            try:
                new_income = IncomeBalance(
                    chat_id=chat_id,
                    amount=amount,
                    currency=currency_code,
                    income_date=current_date,
                    original_amount=original_amount,
                    message_id=message_id,
                    message=message,
                    trx_id=trx_id,
                )

                db.add(new_income)
                db.commit()
                db.refresh(new_income)
                return new_income

            except Exception as e:
                db.rollback()
                raise e

    async def get_income(self, income_id: int) -> Optional[IncomeBalance]:
        with self._get_db() as db:
            return db.query(IncomeBalance).filter(IncomeBalance.id == income_id).first()

    async def get_income_by_chat_id(self, chat_id: int) -> list[type[IncomeBalance]]:
        with self._get_db() as db:
            return (
                db.query(IncomeBalance).filter(IncomeBalance.chat_id == chat_id).all()
            )  # type: ignore

    async def get_income_by_message_id(self, message_id: int) -> bool:
        with self._get_db() as db:
            return (
                db.query(IncomeBalance)
                .filter(IncomeBalance.message_id == message_id)
                .first()
                is not None
            )

    async def get_income_by_trx_id(self, trx_id) -> bool:
        with self._get_db() as db:
            return (
                db.query(IncomeBalance).filter(IncomeBalance.trx_id == trx_id).first()
                is not None
            )

    async def get_last_yesterday_message(self, date: datetime):
        with self._get_db() as db:
            return (
                db.query(IncomeBalance)
                .filter(func.date(IncomeBalance.income_date) == date.date())
                .order_by(IncomeBalance.id.desc())
                .first()
            )

    async def get_income_by_date_and_chat_id(
        self, chat_id: int, start_date: datetime, end_date: datetime
    ) -> list[type[IncomeBalance]]:
        with self._get_db() as db:
            return (
                db.query(IncomeBalance)
                .filter(
                    IncomeBalance.chat_id == chat_id,
                    IncomeBalance.income_date >= start_date,
                    IncomeBalance.income_date < end_date,
                )
                .all()
            )  # type: ignore
