from telethon import Button

from common.enums import ServicePackage
from helper import DateUtils, force_log
from models import User
from services import (
    ChatService,
    ConversationService,
    IncomeService,
    UserService,
    GroupPackageService,
)
from .bot_event_handler import CommandHandler

contact_message = "សូមទាក់ទងទៅអ្នកគ្រប់គ្រង: https://t.me/HK_688"


class EventHandler:
    def __init__(self):
        self.command_handler = CommandHandler()
        self.chat_service = ChatService()
        self.income_service = IncomeService()
        self.group_package_service = GroupPackageService()
        self.conversation_service = ConversationService()

    async def _check_and_notify_autosum_missing(self, event):
        """Check if @autosum_kh exists in the group and notify if missing"""
        try:
            # Only check for groups, not private chats
            if event.is_private:
                return None, False

            # Get participants to check if @autosum_kh is already in the group
            try:
                participants = await event.client.get_participants(event.chat_id)
                autosum_usernames = ["autosum_kh"]

                # Check if any of the autosum bots are already in the group
                existing_usernames = {
                    getattr(p, "username", "").lower()
                    for p in participants
                    if hasattr(p, "username") and p.username
                }

                for username in autosum_usernames:
                    if username.lower() in existing_usernames:
                        return None, False  # Bot already exists, no need to notify

                # Notify that @autosum_kh should be added with a convenient button
                notification_message = (
                    "⚠️ សម្រាប់ការប្រើប្រាស់ពេញលេញ សូមបន្ថែម @autosum_kh ចូលក្រុមនេះ។"
                )

                force_log(
                    f"Notified group {event.chat_id} to add @autosum_kh with button"
                )
                return notification_message, False

            except Exception as e:
                force_log(f"Error checking participants in group {event.chat_id}: {e}")
                return None, False

        except Exception as e:
            force_log(f"Error in _check_and_notify_autosum_missing: {e}")
            return None, False

    async def menu(self, event):
        if event.is_private:
            await event.respond(contact_message)

        # Check if chat is activated and trial status
        chat = await self.chat_service.get_chat_by_chat_id(event.chat_id)
        if not chat:
            # Chat doesn't exist - automatically register using our own register method
            try:
                # Get sender information
                sender = await event.get_sender()

                user = None
                # Check if sender is anonymous
                if sender and hasattr(sender, "id") and sender.id is not None:
                    # Create user if not exists
                    user_service = UserService()
                    user = await user_service.create_user(sender)

                # Use our own register method to register the chat
                await self.register(event, user)

                # Refresh chat information after registration
                chat = await self.chat_service.get_chat_by_chat_id(event.chat_id)

                # If still not available, registration failed
                if not chat:
                    return  # Register method would have shown appropriate message

                # No need to show success message here since register method already does that

            except Exception as e:
                import logging

                logging.error(f"Error during auto-registration: {e}")
                message = (
                    "⚠️ Auto-registration failed. Please use /register command manually."
                )
                await event.respond(message)
                return

        # Check if chat is not active (needs trial period check)
        if not chat.is_active:
            # Check if it's still within 7-day trial period
            from datetime import timedelta

            trial_end = chat.created_at + timedelta(days=7)

            # Make trial_end timezone-aware for comparison
            trial_end = DateUtils.localize_datetime(trial_end)

            if DateUtils.now() > trial_end:
                # Trial expired - ask user to contact admin

                # Check if this is a callback (return button) or new command
                if hasattr(event, "callback_query") and event.callback_query:
                    await event.edit(contact_message)
                else:
                    await event.respond(contact_message)
                return
            # If within trial period, continue to show menu (don't update is_active)

        # Chat is either active (is_active=True) or within trial period - show menu
        # Check and notify if @autosum_kh is missing
        telethon_message, not_added = await self._check_and_notify_autosum_missing(
            event
        )
        if telethon_message and not_added:
            # Create button to easily add @autosum_kh
            buttons = [[Button.url("➕ Add @autosum_kh", f"https://t.me/autosum_kh")],
                       [Button.url("Contact Admin", f"https://t.me/HK_688")]]
            await event.respond(telethon_message, buttons=buttons)
            return

        # Check package to determine available options
        group_package = await self.group_package_service.get_or_create_group_package(
            event.chat_id
        )

        if group_package.package == ServicePackage.BASIC or group_package.package == ServicePackage.FREE:
            # Basic package: only current date option
            buttons = [
                [Button.inline("ថ្ងៃនេះ", "current_date_summary")],
                [Button.inline("បិទ", "close_menu")],
            ]
        else:
            # Trial, Unlimited, Business packages: full menu
            buttons = [
                [
                    Button.inline(
                        "ប្រចាំថ្ងៃ",
                        "daily_summary",
                    )
                ],
                [Button.inline("ប្រចាំសប្តាហ៍", "weekly_summary")],
                [Button.inline("ប្រចាំខែ", "monthly_summary")],
                [Button.inline("បិទ", "close_menu")],
            ]

        # Check if this is a callback (return button) or new command
        if hasattr(event, 'data'):
            # This is from a return button - edit existing message
            await event.edit("ជ្រើសរើសរបាយការណ៍ប្រចាំ:", buttons=buttons)
        else:
            # This is from a new command - send new message
            await event.respond("ជ្រើសរើសរបាយការណ៍ប្រចាំ:", buttons=buttons)

    async def close_menu(self, event):
        await event.delete()

    async def register(self, event, user: User | None):
        chat_id = event.chat_id
        # Handle both group chats (with title) and private chats (without title)
        group_name = getattr(event.chat, "title", f"Private Chat {chat_id}")
        chat_service = ChatService()
        success, message = await chat_service.register_chat_id(
            chat_id, group_name, user
        )

        # Add a menu button to the response message for successful registration
        if success:
            # Assign TRIAL package for normal bot registrations
            try:

                await self.group_package_service.create_group_package(
                    chat_id, ServicePackage.TRIAL
                )
                force_log(f"Assigned TRIAL package to chat_id: {chat_id}")
            except Exception as package_error:
                force_log(
                    f"Error assigning TRIAL package to chat_id {chat_id}: {package_error}"
                )
            # Check and notify if @autosum_kh is missing after successful registration
            telethon_message, not_added = await self._check_and_notify_autosum_missing(
                event
            )
            if telethon_message and not_added:
                # Create button to easily add @autosum_kh
                message = telethon_message
                buttons = [
                    [Button.url("➕ Add @autosum_kh", f"https://t.me/autosum_kh")]
                ]
            else:
                # Create menu button
                buttons = [[Button.inline("របាយការណ៍", "menu")]]
            await event.respond(message, buttons=buttons)
        else:
            # For failures, just show the message without buttons
            await event.respond(message)

    async def message(self, event):
        if event.message.text.startswith("/"):
            return

        replied_message = await event.message.get_reply_message()
        if not replied_message:
            return

        chat_id = event.chat_id
        question = await self.conversation_service.get_question_by_message_id(
            chat_id=chat_id, message_id=replied_message.id
        )

        if question and question.question_type == "date_input":  # type: ignore
            await self.command_handler.handle_date_input_response(event, question)
            return

    async def callback(self, event):
        data = event.data.decode()
        if any(
            data.startswith(prefix) for prefix in ["summary_week_", "summary_month_"]
        ):
            await self.command_handler.handle_period_summary(event, data)
            return

        command_handlers = {
            "menu": self.menu,
            "daily_summary": self.command_handler.handle_daily_summary,
            "current_date_summary": self.command_handler.handle_current_date_summary,
            "weekly_summary": self.command_handler.handle_weekly_summary,
            "monthly_summary": self.command_handler.handle_monthly_summary,
            "close": self.command_handler.close,
            "close_menu": self.close_menu,
            "other_dates": self.command_handler.handle_other_dates,
        }

        handler = command_handlers.get(data)
        if handler:
            await handler(event)
            return

        if data.startswith("summary_of_"):
            await self.command_handler.handle_date_summary(event, data)
            return

        await self.command_handler.handle_daily_summary(event)
