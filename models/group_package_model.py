from datetime import datetime

from sqlalchemy import (
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Float,
    Text,
    JSON,
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
    feature_flags: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # One-to-one relationship with chat_group
    chat_group: Mapped[Chat] = relationship(
        "Chat", backref="group_package", uselist=False
    )

    def get_feature_flag(self, key: str, default=False) -> bool:
        """Get a feature flag value by key, returns default if not found"""
        if not self.feature_flags:
            return default
        return self.feature_flags.get(key, default)
    
    def set_feature_flag(self, key: str, value: bool) -> None:
        """Set a feature flag value by key"""
        if not self.feature_flags:
            self.feature_flags = {}
        self.feature_flags[key] = value
    
    def remove_feature_flag(self, key: str) -> None:
        """Remove a feature flag by key"""
        if self.feature_flags and key in self.feature_flags:
            del self.feature_flags[key]
    
    def has_feature(self, key: str) -> bool:
        """Check if a feature is enabled (convenience method)"""
        return self.get_feature_flag(key, False)
