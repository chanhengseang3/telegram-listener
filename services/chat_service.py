from .income_balance_service import IncomeService
from .group_package_service import GroupPackageService
from common.enums import ServicePackage
from models import User, IncomeBalance
from helper.logger_utils import force_log
from config import get_db_session
from sqlalchemy.orm import joinedload
from models import Chat
from .shift_service import ShiftService


class ChatService:
    def __init__(self):
        self.income_service = IncomeService()
        self.shift_service = ShiftService()
        self.group_package_service = GroupPackageService()

    async def is_unlimited_package(self, chat_id: int) -> int | None:
        try:
            chat = await self.get_chat_by_chat_id(chat_id)
            if chat and chat.enable_shift:
                group_package = await self.group_package_service.get_package_by_chat_id(
                    chat_id
                )

                if group_package and group_package.package in [ServicePackage.BUSINESS]:
                    last_shift = await self.income_service.get_last_shift_id(chat_id)
                    return last_shift.number if last_shift else None

        except Exception as e:
            force_log(f"Error checking unlimited package: {e}")

    async def register_chat_id(self, chat_id, group_name, user: User | None):
        with get_db_session() as session:
            try:
                new_chat = Chat(
                    chat_id=chat_id,
                    group_name=group_name,
                    user_id=user.id if user else None,
                )
                session.add(new_chat)
                session.commit()
                return True, f"Chat ID {chat_id} registered successfully."
            except Exception as e:
                session.rollback()
                force_log(f"Error registering chat ID: {e}")
                return False, f"Error registering chat ID: {e}"
            finally:
                session.close()

    async def update_chat_enable_shift(self, chat_id: int, enable_shift: bool):
        with get_db_session() as session:
            try:
                # Create a shift first if enabling shift
                if enable_shift:
                    try:
                        # Only create shift if none exists
                        current_shift = await self.shift_service.get_current_shift(
                            chat_id
                        )
                        if not current_shift:
                            await self.shift_service.create_shift(chat_id)

                    except Exception as shift_error:
                        force_log(f"Error creating shift: {shift_error}")
                        raise shift_error

                # Update the chat setting after shift creation succeeds
                session.query(Chat).filter_by(chat_id=chat_id).update(
                    {"enable_shift": enable_shift}
                )
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                force_log(f"Error updating chat enable_shift: {e}")
                return False
            finally:
                session.close()

    async def update_chat_status(self, chat_id: int, status: bool):
        with get_db_session() as session:
            try:
                session.query(Chat).filter_by(chat_id=chat_id).update(
                    {"is_active": status}
                )
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                force_log(f"Error updating chat status: {e}")
                return False
            finally:
                session.close()

    async def update_chat_user_id(self, chat_id: int, user_id: int):
        with get_db_session() as session:
            try:
                session.query(Chat).filter_by(chat_id=chat_id).update(
                    {"user_id": user_id}
                )
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                force_log(f"Error updating chat user_id: {e}")
                return False
            finally:
                session.close()

    async def get_chat_by_chat_id(self, chat_id: int) -> Chat | None:
        with get_db_session() as session:
            try:
                chat = (
                    session.query(Chat)
                    .options(joinedload(Chat.user))
                    .filter_by(chat_id=chat_id)
                    .first()
                )
                return chat
            except Exception as e:
                force_log(f"Error fetching chat by chat ID: {e}")
                return None
            finally:
                session.close()

    async def get_all_active_chat_ids(self):
        with get_db_session() as session:
            try:
                chats = session.query(Chat.chat_id).filter_by(is_active=True).all()
                return [int(c[0]) for c in chats]
            except Exception as e:
                force_log(f"Error fetching chat IDs: {e}")
                return []
            finally:
                session.close()

    async def chat_exists(self, chat_id: int) -> bool:
        """
        Check if a chat with the given chat_id exists.
        Much more efficient than fetching all chat IDs and checking if it's in the list.
        """
        with get_db_session() as session:
            try:
                exists = (
                    session.query(Chat).filter_by(chat_id=chat_id).first() is not None
                )
                return bool(exists)
            except Exception as e:
                force_log(f"Error checking if chat exists: {e}")
                return False
            finally:
                session.close()

    async def is_shift_enabled(self, chat_id: int) -> bool:
        try:
            chat = await self.get_chat_by_chat_id(chat_id)
            return chat.enable_shift if chat else False
        except Exception as e:
            force_log(f"Error checking shift enabled: {e}")
            return False

    async def migrate_chat_id(self, old_chat_id: int, new_chat_id: int) -> bool:
        """Migrate chat_id from old to new (for group migrations)"""
        with get_db_session() as session:
            try:
                chat_result = (
                    session.query(Chat)
                    .filter_by(chat_id=old_chat_id)
                    .update({"chat_id": new_chat_id})
                )

                income_result = (
                    session.query(IncomeBalance)
                    .filter_by(chat_id=old_chat_id)
                    .update({"chat_id": new_chat_id})
                )

                session.commit()
                if chat_result > 0 or income_result > 0:
                    force_log(
                        f"Successfully migrated chat_id from {old_chat_id} to {new_chat_id}"
                    )
                    force_log(
                        f"Updated {chat_result} chat records and {income_result} income_balance records"
                    )
                    return True
                else:
                    force_log(f"No records found with chat_id {old_chat_id}")
                    return False
            except Exception as e:
                session.rollback()
                force_log(f"Error migrating chat_id: {e}")
                return False
            finally:
                session.close()
