from datetime import datetime

from common.enums import ServicePackage
from config import get_db_session
from helper import DateUtils
from models import GroupPackage


class GroupPackageService:
    async def _get_chat_group_id_by_chat_id(self, chat_id: int) -> int | None:
        with get_db_session() as db:
            from models.chat_model import Chat

            chat = db.query(Chat).filter(Chat.chat_id == chat_id).first()
            return chat.id if chat else None  # type: ignore

    async def get_package_by_chat_id(self, chat_id: int) -> GroupPackage | None:
        chat_group_id = await self._get_chat_group_id_by_chat_id(chat_id)
        if not chat_group_id:
            return None

        with get_db_session() as db:
            package = (
                db.query(GroupPackage)
                .filter(GroupPackage.chat_group_id == chat_group_id)
                .first()
            )
            return package

    async def create_group_package(
        self, chat_id: int, package: ServicePackage = ServicePackage.TRIAL
    ) -> GroupPackage:
        chat_group_id = await self._get_chat_group_id_by_chat_id(chat_id)
        if not chat_group_id:
            raise ValueError(f"Chat with chat_id {chat_id} not found")

        with get_db_session() as db:
            group_package = GroupPackage(
                chat_group_id=chat_group_id,
                package=package,
                is_paid=False if package in [ServicePackage.TRIAL, ServicePackage.FREE] else True,
                package_start_date=DateUtils.now(),
                created_at=DateUtils.now(),
                updated_at=DateUtils.now(),
            )

            try:
                db.add(group_package)
                db.commit()
                db.refresh(group_package)
                return group_package
            except Exception as e:
                db.rollback()
                raise e

    async def update_package(
        self,
        chat_id: int,
        package: ServicePackage,
        package_start_date: datetime | None = None,
        package_end_date: datetime | None = None,
        amount_paid: float | None = None,
        note: str | None = None,
        last_paid_date: datetime | None = None,
    ) -> GroupPackage | None:
        chat_group_id = await self._get_chat_group_id_by_chat_id(chat_id)
        if not chat_group_id:
            return None

        with get_db_session() as db:
            group_package = (
                db.query(GroupPackage)
                .filter(GroupPackage.chat_group_id == chat_group_id)
                .first()
            )

            if group_package:
                group_package.package = package
                group_package.is_paid = (
                    False if package in [ServicePackage.TRIAL, ServicePackage.FREE] else True
                )

                if package_start_date:
                    group_package.package_start_date = package_start_date
                if package_end_date:
                    group_package.package_end_date = package_end_date
                if amount_paid is not None:
                    group_package.amount_paid = amount_paid
                if note is not None:
                    group_package.note = note
                if last_paid_date:
                    group_package.last_paid_date = last_paid_date

                db.commit()
                db.refresh(group_package)
                return group_package
            return None

    async def get_or_create_group_package(self, chat_id: int) -> GroupPackage:
        existing = await self.get_package_by_chat_id(chat_id)
        if existing:
            return existing
        return await self.create_group_package(chat_id, ServicePackage.TRIAL)

    async def update_feature_flags(
        self, chat_id: int, feature_flags: dict[str, bool]
    ) -> GroupPackage | None:
        """Update feature flags for a group package"""
        chat_group_id = await self._get_chat_group_id_by_chat_id(chat_id)
        if not chat_group_id:
            return None

        with get_db_session() as db:
            group_package = (
                db.query(GroupPackage)
                .filter(GroupPackage.chat_group_id == chat_group_id)
                .first()
            )

            if group_package:
                # Merge new feature flags with existing ones
                current_flags = group_package.feature_flags or {}
                current_flags.update(feature_flags)
                group_package.feature_flags = current_flags
                group_package.updated_at = DateUtils.now()

                db.commit()
                db.refresh(group_package)
                return group_package
            return None

    async def set_feature_flag(
        self, chat_id: int, key: str, value: bool
    ) -> GroupPackage | None:
        """Set a single feature flag for a group package"""
        return await self.update_feature_flags(chat_id, {key: value})

    async def get_feature_flag(
        self, chat_id: int, key: str, default: bool = False
    ) -> bool:
        """Get a feature flag value for a chat"""
        package = await self.get_package_by_chat_id(chat_id)
        if not package:
            return default
        return package.get_feature_flag(key, default)

    async def has_feature(self, chat_id: int, key: str) -> bool:
        """Check if a feature is enabled for a chat (convenience method)"""
        return await self.get_feature_flag(chat_id, key, False)

    async def remove_feature_flag(
        self, chat_id: int, key: str
    ) -> GroupPackage | None:
        """Remove a feature flag for a group package"""
        chat_group_id = await self._get_chat_group_id_by_chat_id(chat_id)
        if not chat_group_id:
            return None

        with get_db_session() as db:
            group_package = (
                db.query(GroupPackage)
                .filter(GroupPackage.chat_group_id == chat_group_id)
                .first()
            )

            if group_package and group_package.feature_flags:
                if key in group_package.feature_flags:
                    del group_package.feature_flags[key]
                    group_package.updated_at = DateUtils.now()
                    db.commit()
                    db.refresh(group_package)
                return group_package
            return None

    async def get_all_feature_flags(self, chat_id: int) -> dict[str, bool]:
        """Get all feature flags for a chat"""
        package = await self.get_package_by_chat_id(chat_id)
        if not package or not package.feature_flags:
            return {}
        return package.feature_flags
