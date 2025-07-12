from contextlib import contextmanager
from datetime import date
from typing import Optional, Generator, Any

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    DateTime,
    Date,
    BigInteger,
    func,
)
from sqlalchemy.orm import Session, relationship

from config.database_config import SessionLocal
from helper import DateUtils
from models.base_model import BaseModel


class Shift(BaseModel):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False)
    shift_date = Column(Date, nullable=False)
    number = Column(Integer, nullable=False)  # 1, 2, 3... for each day
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)  # NULL if not closed yet
    is_closed = Column(Boolean, nullable=False, default=False)
    
    # Relationship to income_balance
    income_records = relationship("IncomeBalance", back_populates="shift")


class ShiftService:
    def __init__(self):
        self._session_factory = SessionLocal

    @contextmanager
    def _get_db(self) -> Generator[Session, Any, Any]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    async def create_shift(self, chat_id: int) -> Shift:
        """Create a new shift starting now"""
        current_time = DateUtils.now()
        
        with self._get_db() as db:
            # Get the highest shift number for this chat for today (not global)
            last_shift_number = db.query(func.max(Shift.number)).filter(
                Shift.chat_id == chat_id,
                Shift.shift_date == current_time.date(),
            ).scalar() or 0
            
            new_shift = Shift(
                chat_id=chat_id,
                shift_date=current_time.date(),
                number=last_shift_number + 1,
                start_time=current_time,
                is_closed=False
            )
            
            db.add(new_shift)
            db.commit()
            db.refresh(new_shift)
            return new_shift

    async def get_current_shift(self, chat_id: int) -> Optional[Shift]:
        """Get the current open shift (regardless of date)"""
        with self._get_db() as db:
            return db.query(Shift).filter(
                Shift.chat_id == chat_id,
                Shift.is_closed == False
            ).order_by(Shift.start_time.desc()).first()

    async def get_shift_by_id(self, shift_id: int) -> Optional[Shift]:
        """Get shift by ID"""
        with self._get_db() as db:
            return db.query(Shift).filter(Shift.id == shift_id).first()

    async def close_shift(self, shift_id: int) -> Optional[Shift]:
        """Close a shift by setting end_time and is_closed"""
        current_time = DateUtils.now()
        
        with self._get_db() as db:
            shift = db.query(Shift).filter(Shift.id == shift_id).first()
            if shift and not shift.is_closed:
                shift.end_time = current_time
                shift.is_closed = True
                db.commit()
                db.refresh(shift)
                return shift
            return None

    async def get_shifts_by_date_range(self, chat_id: int, start_date: date, end_date: date) -> list[type[Shift]]:
        """Get all shifts for a chat within a date range"""
        with self._get_db() as db:
            return db.query(Shift).filter(
                Shift.chat_id == chat_id,
                Shift.shift_date >= start_date,
                Shift.shift_date <= end_date
            ).order_by(Shift.shift_date, Shift.number).all()

    async def get_shifts_by_date(self, chat_id: int, shift_date: date) -> list[Shift]:
        """Get all shifts for a specific date"""
        with self._get_db() as db:
            return db.query(Shift).filter(
                Shift.chat_id == chat_id,
                Shift.shift_date == shift_date
            ).order_by(Shift.number).all()

    async def get_recent_closed_shifts(self, chat_id: int, limit: int = 1) -> list[Shift]:
        """Get recent closed shifts for a chat"""
        with self._get_db() as db:
            return db.query(Shift).filter(
                Shift.chat_id == chat_id,
                Shift.is_closed == True
            ).order_by(Shift.end_time.desc()).limit(limit).all()

    async def get_shift_income_summary(self, shift_id: int, chat_id: int) -> dict:
        """Get income summary for a specific shift and chat"""
        with self._get_db() as db:
            from models.income_balance_model import IncomeBalance
            
            # Get all income records for this shift and chat
            income_records = db.query(IncomeBalance).filter(
                IncomeBalance.shift_id == shift_id,
                IncomeBalance.chat_id == chat_id
            ).all()
            
            if not income_records:
                return {
                    'total_amount': 0.0,
                    'transaction_count': 0,
                    'currencies': {}
                }
            
            total_amount = sum(record.amount for record in income_records)
            transaction_count = len(income_records)
            
            # Group by currency
            currencies = {}
            for record in income_records:
                currency = record.currency or 'USD'
                if currency not in currencies:
                    currencies[currency] = {'amount': 0.0, 'count': 0}
                currencies[currency]['amount'] += record.amount
                currencies[currency]['count'] += 1
            
            return {
                'total_amount': total_amount,
                'transaction_count': transaction_count,
                'currencies': currencies
            }

    async def get_recent_dates_with_shifts(self, chat_id: int, days: int = 3) -> list[date]:
        """Get last N dates that have shifts"""
        with self._get_db() as db:
            dates = db.query(Shift.shift_date).filter(
                Shift.chat_id == chat_id
            ).distinct().order_by(Shift.shift_date.desc()).limit(days).all()
            
            return [d[0] for d in dates]

    async def check_and_auto_close_shifts(self) -> list[Shift]:
        """Check all open shifts and auto-close them based on configuration"""
        from models.shift_configuration_model import ShiftConfigurationService
        from datetime import datetime

        closed_shifts = []
        config_service = ShiftConfigurationService()
        
        with self._get_db() as db:
            # Get all open shifts
            open_shifts = db.query(Shift).filter(
                Shift.is_closed == False
            ).all()
            
            for shift in open_shifts:
                config = await config_service.get_configuration(shift.chat_id)
                if not config or not config.auto_close_enabled:
                    continue
                
                should_close = False
                current_time = DateUtils.now()
                
                # Check time-based auto close
                if config.auto_close_time:
                    # Convert time to datetime for comparison
                    close_time = datetime.combine(
                        current_time.date(), 
                        config.auto_close_time
                    )
                    # Make timezone aware
                    close_time = DateUtils.localize_datetime(close_time)
                    
                    # If current time is past the auto-close time and shift started before it
                    shift_start = DateUtils.localize_datetime(shift.start_time)
                    if current_time >= close_time and shift_start < close_time:
                        should_close = True
                
                # Check inactivity-based auto close
                if config.auto_close_after_hours and not should_close:
                    hours_since_start = (current_time - DateUtils.localize_datetime(shift.start_time)).total_seconds() / 3600
                    if hours_since_start >= config.auto_close_after_hours:
                        should_close = True
                
                # Close the shift if needed
                if should_close:
                    shift.end_time = current_time
                    shift.is_closed = True
                    closed_shifts.append(shift)
            
            if closed_shifts:
                db.commit()
                for shift in closed_shifts:
                    db.refresh(shift)
        
        return closed_shifts

    async def auto_close_shift_for_chat(self, chat_id: int) -> Optional[Shift]:
        """Auto close the current shift for a specific chat based on its configuration"""
        from models.shift_configuration_model import ShiftConfigurationService
        from datetime import datetime
        
        config_service = ShiftConfigurationService()
        config = await config_service.get_configuration(chat_id)
        
        if not config or not config.auto_close_enabled:
            return None
        
        current_shift = await self.get_current_shift(chat_id)
        if not current_shift:
            return None
        
        should_close = False
        current_time = DateUtils.now()
        
        # Check time-based auto close
        if config.auto_close_time:
            close_time = datetime.combine(
                current_time.date(), 
                config.auto_close_time
            )
            close_time = DateUtils.localize_datetime(close_time)
            
            shift_start = DateUtils.localize_datetime(current_shift.start_time)
            if current_time >= close_time and shift_start < close_time:
                should_close = True
        
        # Check inactivity-based auto close
        if config.auto_close_after_hours and not should_close:
            hours_since_start = (current_time - DateUtils.localize_datetime(current_shift.start_time)).total_seconds() / 3600
            if hours_since_start >= config.auto_close_after_hours:
                should_close = True
        
        if should_close:
            return await self.close_shift(current_shift.id)
        
        return None