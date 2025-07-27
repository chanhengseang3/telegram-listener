from datetime import datetime

from sqlalchemy import (
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Float,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.enums import ServicePackage
from models.base_model import BaseModel
from models.chat_model import Chat


class GroupPackage(BaseModel):
    __tablename__ = "group_package"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("chat_group.id"), unique=True, nullable=False
    )
    package: Mapped[ServicePackage] = mapped_column(
        Enum(ServicePackage), nullable=False, default=ServicePackage.TRIAL
    )
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    package_start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    package_end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_paid_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    amount_paid: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # One-to-one relationship with chat_group
    chat_group: Mapped[Chat] = relationship(
        "Chat", backref="group_package", uselist=False
    )
