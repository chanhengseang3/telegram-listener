from datetime import timedelta, datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from common.enums import ServicePackage
from handlers.bot_command_handler import EventHandler
from helper import DateUtils, total_summary_report, daily_transaction_report, weekly_transaction_report, \
    monthly_transaction_report
from helper.logger_utils import force_log
from models import Chat
from services import ChatService, UserService, IncomeService
from .group_package_service import GroupPackageService

PACKAGE_COMMAND_CODE = 1003
PACKAGE_SELECTION_CODE = 1004
USER_CONFIRMATION_CODE = 1005
ENABLE_SHIFT_COMMAND_CODE = 1006
MENU_COMMAND_CODE = 1007
CALLBACK_QUERY_CODE = 1008
GET_USERNAME_COMMAND_CODE = 1009
CHAT_SELECTION_CODE = 1010
ACTIVATE_SELECTION_CODE = 1011
DEACTIVATE_SELECTION_CODE = 1012
ENABLE_SHIFT_SELECTION_CODE = 1013
PACKAGE_START_DATE_CODE = 1014
PACKAGE_END_DATE_CODE = 1015
AMOUNT_PAID_CODE = 1016
NOTE_CONFIRMATION_CODE = 1017
NOTE_INPUT_CODE = 1018


class TelegramAdminBot:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.app: Application | None = None
        self.chat_service = ChatService()
        self.user_service = UserService()
        self.group_package_service = GroupPackageService()
        self.event_handler = EventHandler()
        self.default_question = (
            "Please provide the chat ID by replying to this message."
        )
        self.telethon_client = None
        force_log("TelegramAdminBot initialized with token", "TelegramAdminBot")

    async def validate_user_identifier(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            chat_id = int(update.message.text.strip())  # type: ignore
            chat = await self._get_chat_with_validation(update, chat_id)
            if not chat:
                return ConversationHandler.END

            identifier: str = chat.user.identifier if chat.user else ""  # type: ignore
            force_log(f"Identifier: {identifier}", "TelegramAdminBot")
            user = await self.user_service.get_user_by_identifier(identifier)
            if not user:
                await update.message.reply_text("User not found.")  # type: ignore
                return ConversationHandler.END

            context.user_data["user_identifier"] = identifier  # type: ignore
            context.user_data["chat_id_input"] = chat_id  # type: ignore
            context.user_data["found_user"] = user  # type: ignore
            return await self.show_user_confirmation(update, context, user)
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")  # type: ignore
            return ConversationHandler.END

    @staticmethod
    async def package(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["command_type"] = "package"  # type: ignore
        keyboard = [
            [InlineKeyboardButton("Use Chat ID", callback_data="use_chat_id")],
            [InlineKeyboardButton("Use Group Name", callback_data="use_group_name")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(  # type: ignore
            "How would you like to identify the user?", reply_markup=reply_markup
        )
        return PACKAGE_SELECTION_CODE

    @staticmethod
    async def package_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        try:
            if query:
                await query.answer()
                selection = query.data

                if selection == "use_chat_id":
                    context.user_data["selection_type"] = "chat_id"
                    await query.edit_message_text(
                        "Please provide the chat ID by replying to this message."
                    )
                    return PACKAGE_COMMAND_CODE
                elif selection == "use_group_name":
                    context.user_data["selection_type"] = "group_name"
                    await query.edit_message_text(
                        "Please provide the group name to search. You can enter partial group name (up to 5 results will be shown)."
                    )
                    return PACKAGE_COMMAND_CODE

            return PACKAGE_SELECTION_CODE
        except Exception as e:
            force_log(f"Error in package_selection_handler: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text(f"Error: {str(e)}")
            return ConversationHandler.END

    async def search_and_show_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            search_term = update.message.text.strip()  # type: ignore
            force_log(f"Searching for chats with term: {search_term}", "TelegramAdminBot")
            
            # Search for chats using the new search method
            matching_chats = await self.chat_service.search_chats_by_chat_id_or_name(search_term, 5)
            
            if not matching_chats:
                await update.message.reply_text("No chats found matching your search.")  # type: ignore
                return ConversationHandler.END
            
            if len(matching_chats) == 1:
                # If only one result, proceed directly with that chat
                chat = matching_chats[0]
                context.user_data["chat_id_input"] = str(chat.chat_id)  # type: ignore
                context.user_data["group_name"] = chat.group_name
                context.user_data["found_user"] = chat.user  # type: ignore
                if chat.user:
                    return await self.show_user_confirmation(update, context, chat.user)
                else:
                    await update.message.reply_text("No user associated with this chat.")  # type: ignore
                    return ConversationHandler.END
            
            # Multiple results - show selection buttons
            keyboard = []
            for chat in matching_chats:
                button_text = f"{chat.group_name} (ID: {chat.chat_id})"
                callback_data = f"select_chat_{chat.chat_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add cancel button
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_chat_selection")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(  # type: ignore
                f"Found {len(matching_chats)} matching chats. Please select one:",
                reply_markup=reply_markup
            )
            
            return CHAT_SELECTION_CODE
            
        except Exception as e:
            force_log(f"Error in search_and_show_chats: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error searching for chats.")  # type: ignore
            return ConversationHandler.END

    async def handle_chat_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        try:
            if query:
                await query.answer()
                callback_data = query.data
                
                if callback_data == "cancel_chat_selection":
                    await query.edit_message_text("Chat selection cancelled.")
                    return ConversationHandler.END
                
                if callback_data.startswith("select_chat_"):
                    chat_id = callback_data.replace("select_chat_", "")
                    command_type = context.user_data.get("command_type")  # type: ignore
                    force_log(f"Selected chat_id: {chat_id} for command: {command_type}", "TelegramAdminBot")
                    
                    # Get the selected chat
                    chat = await self.chat_service.get_chat_by_chat_id(int(chat_id))
                    if not chat:
                        await query.edit_message_text("Selected chat not found.")
                        return ConversationHandler.END
                    
                    context.user_data["chat_id_input"] = chat_id  # type: ignore
                    context.user_data["group_name"] = chat.group_name
                    
                    # For package command, proceed directly to package selection
                    if command_type == "package" or not command_type:
                        # Show package selection
                        keyboard = [
                            [
                                InlineKeyboardButton(
                                    ServicePackage.BASIC.value, callback_data="BASIC"
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    ServicePackage.UNLIMITED.value, callback_data="UNLIMITED",
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    ServicePackage.BUSINESS.value, callback_data="BUSINESS"
                                )
                            ],
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(
                            f"Selected chat: {chat.group_name} (ID: {chat_id})\n\nPlease choose a subscription package:",
                            reply_markup=reply_markup,
                        )
                        return PACKAGE_COMMAND_CODE
                    
                    # For other commands, execute directly
                    elif command_type == "enable_shift":
                        await query.edit_message_text(f"Executing enable shift for chat: {chat.group_name}")
                        return await self.execute_enable_shift_command_from_query(query, int(chat_id))
                        
        except Exception as e:
            force_log(f"Error in handle_chat_selection: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text("Error processing selection.")
            return ConversationHandler.END
        return ConversationHandler.END


    @staticmethod
    async def shared_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Shared handler for chat selection across all commands"""
        query = update.callback_query
        try:
            if query:
                await query.answer()
                selection = query.data
                command_type = context.user_data.get("command_type")  # type: ignore

                if selection == "use_chat_id":
                    context.user_data["selection_type"] = "chat_id"  # type: ignore
                    await query.edit_message_text(
                        "Please provide the chat ID or group name to search. You can search by exact chat ID or partial group name (up to 5 results will be shown)."
                    )
                    # Return appropriate command code based on command type
                    if command_type == "enable_shift":
                        return ENABLE_SHIFT_COMMAND_CODE
                    else:
                        return PACKAGE_COMMAND_CODE

                elif selection == "use_group_name":
                    context.user_data["selection_type"] = "group_name"  # type: ignore
                    await query.edit_message_text(
                        "Please provide the group name to search. You can enter partial group name (up to 5 results will be shown)."
                    )
                    # Return appropriate command code based on command type
                    if command_type == "enable_shift":
                        return ENABLE_SHIFT_COMMAND_CODE
                    else:
                        return PACKAGE_COMMAND_CODE

        except Exception as e:
            force_log(f"Error in shared_selection_handler: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text(f"Error: {str(e)}")
            return ConversationHandler.END
        
        return ConversationHandler.END

    async def shared_process_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Shared handler for processing chat search input across all commands"""
        selection_type = context.user_data.get("selection_type")  # type: ignore

        if selection_type == "chat_id":
            # All commands now use the search method for consistency
            return await self.search_and_show_chats_for_command(update, context)
        elif selection_type == "group_name":
            return await self.search_and_show_chats_for_command(update, context)
        else:
            await update.message.reply_text("Invalid selection type.")  # type: ignore
            return ConversationHandler.END

    async def search_and_show_chats_for_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Search and show chats for activate/deactivate/enable_shift commands"""
        try:
            search_term = update.message.text.strip()  # type: ignore
            command_type = context.user_data.get("command_type")  # type: ignore
            force_log(f"Searching for chats with term: {search_term} for command: {command_type}", "TelegramAdminBot")
            
            # Search for chats using the new search method
            matching_chats = await self.chat_service.search_chats_by_chat_id_or_name(search_term, 5)
            
            if not matching_chats:
                await update.message.reply_text("No chats found matching your search.")  # type: ignore
                return ConversationHandler.END
            
            if len(matching_chats) == 1:
                # If only one result, proceed directly with the command
                chat = matching_chats[0]
                context.user_data["chat_id_input"] = str(chat.chat_id)  # type: ignore
                
                # Execute the command directly
                if command_type == "enable_shift":
                    return await self.execute_enable_shift_command(update, context)
                elif command_type == "package":
                    # Show package selection directly
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                ServicePackage.BASIC.value, callback_data="BASIC"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.UNLIMITED.value, callback_data="UNLIMITED",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.BUSINESS.value, callback_data="BUSINESS"
                            )
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text(  # type: ignore
                        f"Selected chat: {chat.group_name} (ID: {chat.chat_id})\n\nPlease choose a subscription package:",
                        reply_markup=reply_markup,
                    )
                    return PACKAGE_COMMAND_CODE
            
            # Multiple results - show selection buttons
            keyboard = []
            for chat in matching_chats:
                button_text = f"{chat.group_name} (ID: {chat.chat_id})"
                callback_data = f"select_chat_{chat.chat_id}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add cancel button
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel_chat_selection")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(  # type: ignore
                f"Found {len(matching_chats)} matching chats. Please select one:",
                reply_markup=reply_markup
            )
            
            # Store command type for the selection handler
            context.user_data["command_type"] = command_type  # type: ignore
            return CHAT_SELECTION_CODE
            
        except Exception as e:
            force_log(f"Error in search_and_show_chats_for_command: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error searching for chats.")  # type: ignore
            return ConversationHandler.END

    async def execute_enable_shift_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Execute the enable shift command for a specific chat"""
        try:
            # Use the existing process_enable_shift_chat_id logic
            return await self.process_enable_shift_chat_id(update, context)
        except Exception as e:
            force_log(f"Error in execute_enable_shift_command: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error enabling shift for chat.")  # type: ignore
            return ConversationHandler.END

    async def execute_activate_command_from_query(
        self, query, chat_id: int
    ) -> int:
        """Execute activate command from callback query"""
        try:
            success = await self.chat_service.update_chat_status(chat_id, True)
            if success:
                await query.edit_message_text(f"✅ Chat {chat_id} has been activated successfully!")
            else:
                await query.edit_message_text(f"❌ Failed to activate chat {chat_id}")
            return ConversationHandler.END
        except Exception as e:
            force_log(f"Error in execute_activate_command_from_query: {e}", "TelegramAdminBot")
            await query.edit_message_text("Error activating chat.")
            return ConversationHandler.END

    async def execute_deactivate_command_from_query(
        self, query, chat_id: int
    ) -> int:
        """Execute deactivate command from callback query"""
        try:
            success = await self.chat_service.update_chat_status(chat_id, False)
            if success:
                await query.edit_message_text(f"✅ Chat {chat_id} has been deactivated successfully!")
            else:
                await query.edit_message_text(f"❌ Failed to deactivate chat {chat_id}")
            return ConversationHandler.END
        except Exception as e:
            force_log(f"Error in execute_deactivate_command_from_query: {e}", "TelegramAdminBot")
            await query.edit_message_text("Error deactivating chat.")
            return ConversationHandler.END

    async def execute_enable_shift_command_from_query(
        self, query, chat_id: int
    ) -> int:
        """Execute enable shift command from callback query"""
        try:
            success = await self.chat_service.update_chat_enable_shift(chat_id, True)
            if success:
                await query.edit_message_text(f"✅ Shift has been enabled for chat {chat_id} successfully!")
            else:
                await query.edit_message_text(f"❌ Failed to enable shift for chat {chat_id}")
            return ConversationHandler.END
        except Exception as e:
            force_log(f"Error in execute_enable_shift_command_from_query: {e}", "TelegramAdminBot")
            await query.edit_message_text("Error enabling shift for chat.")
            return ConversationHandler.END

    async def show_user_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, user
    ) -> int:
        try:
            # Display user information with username
            username = user.username if user.username else "N/A"  # type: ignore
            first_name = user.first_name if user.first_name else "N/A"  # type: ignore
            last_name = user.last_name if user.last_name else "N/A"  # type: ignore

            user_info = f"User Found:\n"
            user_info += f"Username: @{username}\n"
            user_info += f"Name: {first_name} {last_name}\n"

            # Get package info from chat if available
            chat_id = context.user_data.get("chat_id_input")
            if chat_id:
                group_package = await self.group_package_service.get_package_by_chat_id(
                    chat_id
                )
                if group_package:
                    user_info += f"Current Package: {group_package.package.value}"
                else:
                    user_info += f"Current Package: No package assigned"
            else:
                user_info += f"Current Package: N/A (no chat specified)"

            keyboard = [
                [
                    InlineKeyboardButton(
                        f"✅ Confirm (@{username})", callback_data="confirm_user"
                    )
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_user")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(user_info, reply_markup=reply_markup)  # type: ignore
            return USER_CONFIRMATION_CODE
        except Exception as e:
            force_log(f"Error in show_user_confirmation: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error displaying user information.")  # type: ignore
            return ConversationHandler.END

    async def process_package_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        selection_type = context.user_data.get("selection_type")

        if selection_type == "chat_id":
            return await self.validate_user_identifier(update, context)
        elif selection_type == "group_name":
            return await self.search_and_show_chats(update, context)
        else:
            await update.message.reply_text("Invalid selection type.")  # type: ignore
            return ConversationHandler.END

    @staticmethod
    async def user_confirmation_handler(
            update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        try:
            if query:
                await query.answer()
                action = query.data

                if action == "confirm_user":
                    # Show package selection
                    keyboard = [
                        [
                            InlineKeyboardButton(
                                ServicePackage.TRIAL.value, callback_data="TRIAL"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.FREE.value, callback_data="FREE"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.BASIC.value, callback_data="BASIC"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.UNLIMITED.value,
                                callback_data="UNLIMITED",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                ServicePackage.BUSINESS.value, callback_data="BUSINESS"
                            )
                        ],
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await query.edit_message_text(
                        "Please choose a subscription package:",
                        reply_markup=reply_markup,
                    )
                    return PACKAGE_COMMAND_CODE

                elif action == "cancel_user":
                    await query.edit_message_text("Operation cancelled.")
                    return ConversationHandler.END

            return USER_CONFIRMATION_CODE
        except Exception as e:
            force_log(f"Error in user_confirmation_handler: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text(f"Error: {str(e)}")
            return ConversationHandler.END

    async def package_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        try:
            if query:
                await query.answer()
                selected_package = query.data

                # Handle selection buttons
                if selected_package in ["use_chat_id", "use_username"]:
                    return await self.package_selection_handler(update, context)

                # Handle package selection buttons
                if selected_package in ["BASIC", "UNLIMITED", "BUSINESS"]:
                    chat_id = context.user_data.get("chat_id_input")

                    if not chat_id:
                        await query.edit_message_text("Chat ID not found.")
                        return ConversationHandler.END

                    # Store selected package for later processing
                    context.user_data["selected_package"] = selected_package

                    # Ask for start date
                    await query.edit_message_text(
                        f"Selected package: {selected_package}\n\n"
                        "Please enter the start date for this package (dd-mm-yyyy format):\n"
                        "Example: 15-01-2024"
                    )
                    return PACKAGE_START_DATE_CODE

            return PACKAGE_COMMAND_CODE
        except Exception as e:
            force_log(f"Error in package_button: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text(f"Error updating user package: {str(e)}")
            return ConversationHandler.END

    @staticmethod
    async def process_package_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle start date input for package"""
        try:
            start_date_str = update.message.text.strip()  # type: ignore
            
            try:
                context.user_data["package_start_date"] = start_date_str
                
                # Ask for end date
                await update.message.reply_text(  # type: ignore
                    f"Start date set: {start_date_str}\n\n"
                    "Please enter the end date for this package (dd-mm-yyyy format):\n"
                    "Example: 31-12-2024"
                )
                return PACKAGE_END_DATE_CODE
                
            except ValueError:
                await update.message.reply_text(  # type: ignore
                    "Invalid date format. Please use dd-mm-yyyy format (e.g., 15-01-2024):"
                )
                return PACKAGE_START_DATE_CODE
                
        except Exception as e:
            force_log(f"Error in process_package_start_date: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error processing start date.")  # type: ignore
            return ConversationHandler.END

    async def process_package_end_date(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle end date input and finalize package update"""
        try:
            end_date_str = update.message.text.strip()  # type: ignore
            
            # Validate date format
            try:
                end_date = datetime.strptime(end_date_str, "%d-%m-%Y")
                start_date = datetime.strptime(context.user_data["package_start_date"], "%d-%m-%Y")
                
                # Validate end date is after start date
                if end_date <= start_date:
                    await update.message.reply_text(  # type: ignore
                        "End date must be after start date. Please enter a valid end date:"
                    )
                    return PACKAGE_END_DATE_CODE
                
                # Store end date
                context.user_data["package_end_date"] = end_date_str
                
                # Ask for amount paid
                await update.message.reply_text(  # type: ignore
                    f"End date set: {end_date_str}\n\n"
                    "Please enter the amount paid for this package:\n"
                    "Example: 25.50"
                )
                return AMOUNT_PAID_CODE
                
            except ValueError:
                await update.message.reply_text(  # type: ignore
                    "Invalid date format. Please use dd-mm-yyyy format (e.g., 31-12-2024):"
                )
                return PACKAGE_END_DATE_CODE
                
        except Exception as e:
            force_log(f"Error in process_package_end_date: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error processing end date.")  # type: ignore
            return ConversationHandler.END

    async def process_amount_paid(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle amount paid input"""
        try:
            amount_str = update.message.text.strip()  # type: ignore
            
            # Validate amount format
            try:
                amount_paid = float(amount_str)
                if amount_paid < 0:
                    await update.message.reply_text(  # type: ignore
                        "Amount must be a positive number. Please enter a valid amount:"
                    )
                    return AMOUNT_PAID_CODE
                
                # Store amount paid
                context.user_data["amount_paid"] = amount_paid
                
                # Ask if user wants to add a note
                keyboard = [
                    [InlineKeyboardButton("✅ Yes, add note", callback_data="add_note")],
                    [InlineKeyboardButton("❌ No, finish setup", callback_data="skip_note")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(  # type: ignore
                    f"Amount paid set: ${amount_paid:.2f}\n\n"
                    "Would you like to add a note for this package?",
                    reply_markup=reply_markup
                )
                return NOTE_CONFIRMATION_CODE
                
            except ValueError:
                await update.message.reply_text(  # type: ignore
                    "Invalid amount format. Please enter a valid number (e.g., 25.50):"
                )
                return AMOUNT_PAID_CODE
                
        except Exception as e:
            force_log(f"Error in process_amount_paid: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error processing amount paid.")  # type: ignore
            return ConversationHandler.END

    async def handle_note_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle note confirmation buttons"""
        query = update.callback_query
        try:
            if query:
                await query.answer()
                action = query.data

                if action == "add_note":
                    await query.edit_message_text(
                        "Please enter your note for this package:"
                    )
                    return NOTE_INPUT_CODE

                elif action == "skip_note":
                    # Proceed to finalize without note
                    context.user_data["note"] = None
                    return await self.finalize_package_update_with_payment(update, context)

            return NOTE_CONFIRMATION_CODE
        except Exception as e:
            force_log(f"Error in handle_note_confirmation: {e}", "TelegramAdminBot")
            if query:
                await query.edit_message_text(f"Error: {str(e)}")
            return ConversationHandler.END

    async def process_note_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle note input"""
        try:
            note = update.message.text.strip()  # type: ignore
            
            # Store note
            context.user_data["note"] = note
            
            # Proceed to finalize with note
            return await self.finalize_package_update_with_payment(update, context)
            
        except Exception as e:
            force_log(f"Error in process_note_input: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error processing note.")  # type: ignore
            return ConversationHandler.END

    async def finalize_package_update_with_payment(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Finalize the package update with payment info and optional note"""
        try:
            # Get stored data
            chat_id = context.user_data.get("chat_id_input")
            chat_name = context.user_data.get("group_name")
            selected_package = context.user_data.get("selected_package")
            start_date_str = context.user_data.get("package_start_date")
            end_date_str = context.user_data.get("package_end_date")
            amount_paid = context.user_data.get("amount_paid")
            note = context.user_data.get("note")
            
            if not all([chat_id, selected_package, start_date_str, end_date_str, amount_paid is not None]):
                await update.message.reply_text("Missing required information.")  # type: ignore
                return ConversationHandler.END
            
            # Convert dates
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, "%d-%m-%Y")
            end_date = datetime.strptime(end_date_str, "%d-%m-%Y")

            # Update group package with dates, amount, and note
            await self.group_package_service.get_or_create_group_package(chat_id)

            updated_package = await self.group_package_service.update_package(
                chat_id, 
                ServicePackage(selected_package),
                package_start_date=start_date,
                package_end_date=end_date,
                amount_paid=amount_paid,
                note=note
            )

            if not updated_package:
                await update.message.reply_text("Failed to update group package.")  # type: ignore
                return ConversationHandler.END

            # Update shift settings based on package change
            if ServicePackage(selected_package) == ServicePackage.BUSINESS:
                # When upgrading to business, automatically enable shift
                await self.chat_service.update_chat_enable_shift(chat_id, True)
            elif ServicePackage(selected_package) in [ServicePackage.TRIAL, ServicePackage.FREE]:
                # When downgrading to trial or free, disable shift
                await self.chat_service.update_chat_enable_shift(chat_id, False)

            # Prepare confirmation message
            message = (
                f"✅ Successfully updated package:\n"
                f"• Package: {selected_package}\n"
                f"• Group ID: {chat_id}\n"
                f"• Group Name: {chat_name}\n"
                f"• Start Date: {start_date_str}\n"
                f"• End Date: {end_date_str}\n"
                f"• Amount Paid: ${amount_paid:.2f}"
            )
            
            if note:
                message += f"\n• Note: {note}"

            await update.message.reply_text(message)  # type: ignore
            return ConversationHandler.END
            
        except Exception as e:
            force_log(f"Error in finalize_package_update_with_payment: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error finalizing package update.")  # type: ignore
            return ConversationHandler.END

    async def finalize_package_update(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Finalize the package update with selected dates"""
        try:
            # Get stored data
            chat_id = context.user_data.get("chat_id_input")
            chat_name = context.user_data.get("group_name")
            selected_package = context.user_data.get("selected_package")
            start_date_str = context.user_data.get("package_start_date")
            end_date_str = context.user_data.get("package_end_date")
            
            if not all([chat_id, selected_package, start_date_str, end_date_str]):
                await update.message.reply_text("Missing required information.")  # type: ignore
                return ConversationHandler.END
            
            # Convert dates
            from datetime import datetime
            start_date = datetime.strptime(start_date_str, "%d-%m-%Y")
            end_date = datetime.strptime(end_date_str, "%d-%m-%Y")

            # Update group package with dates
            await self.group_package_service.get_or_create_group_package(chat_id)

            updated_package = await self.group_package_service.update_package(
                chat_id, 
                ServicePackage(selected_package),
                package_start_date=start_date,
                package_end_date=end_date
            )

            if not updated_package:
                await update.message.reply_text("Failed to update group package.")  # type: ignore
                return ConversationHandler.END

            # Update shift settings based on package change
            if ServicePackage(selected_package) == ServicePackage.BUSINESS:
                # When upgrading to business, automatically enable shift
                await self.chat_service.update_chat_enable_shift(chat_id, True)
            elif ServicePackage(selected_package) in [ServicePackage.TRIAL, ServicePackage.FREE]:
                # When downgrading to trial or free, disable shift
                await self.chat_service.update_chat_enable_shift(chat_id, False)

            # Confirm to user
            await update.message.reply_text(  # type: ignore
                f"✅ Successfully updated package:\n"
                f"• Package: {selected_package}\n"
                f"• Group ID: {chat_id}\n"
                f"• Group Name: {chat_name}\n"
                f"• Start Date: {start_date_str}\n"
                f"• End Date: {end_date_str}"
            )
            return ConversationHandler.END
            
        except Exception as e:
            force_log(f"Error in finalize_package_update: {e}", "TelegramAdminBot")
            await update.message.reply_text("Error finalizing package update.")  # type: ignore
            return ConversationHandler.END

    async def callback_query_handler(self, update: Update) -> int:
        """Handle callback queries from inline buttons"""
        query = update.callback_query

        try:
            # We need to answer the callback query first to stop the loading indicator
            await query.answer()

            # Extract the callback data (similar to what Telethon would get)
            callback_data = query.data

            # Create a pseudo-event for the callback similar to Telethon's events.CallbackQuery
            class PseudoCallbackEvent:
                def __init__(self, callback_query, callback_data):
                    self.chat_id = callback_query.message.chat_id
                    self.data = (
                        callback_data.encode("utf-8")
                        if isinstance(callback_data, str)
                        else callback_data
                    )
                    self.callback_query = True
                    self.message = callback_query.message

                @staticmethod
                async def edit(text, buttons=None):
                    if buttons:
                        # Convert Telethon buttons to python-telegram-bot InlineKeyboardButton format
                        keyboard = []
                        for row in buttons:
                            keyboard_row = []
                            for button in row:
                                # Extract text and data from button
                                if hasattr(button, "text") and hasattr(button, "data"):
                                    # Convert bytes to string if needed
                                    button_data = button.data
                                    if isinstance(button_data, bytes):
                                        button_data = button_data.decode("utf-8")
                                    elif not isinstance(button_data, str):
                                        button_data = str(button_data)

                                    keyboard_row.append(
                                        InlineKeyboardButton(
                                            button.text, callback_data=button_data
                                        )
                                    )
                            if keyboard_row:
                                keyboard.append(keyboard_row)

                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(text, reply_markup=reply_markup)
                    else:
                        await query.edit_message_text(text)

                @staticmethod
                async def respond(text, buttons=None):
                    """For cases where a new message needs to be sent instead of editing"""
                    if buttons:
                        # Convert Telethon buttons to python-telegram-bot format
                        keyboard = []
                        for row in buttons:
                            keyboard_row = []
                            for button in row:
                                if hasattr(button, "text") and hasattr(button, "data"):
                                    # Convert bytes to string if needed
                                    button_data = button.data
                                    if isinstance(button_data, bytes):
                                        button_data = button_data.decode("utf-8")
                                    elif not isinstance(button_data, str):
                                        button_data = str(button_data)

                                    keyboard_row.append(
                                        InlineKeyboardButton(
                                            button.text, callback_data=button_data
                                        )
                                    )
                            if keyboard_row:
                                keyboard.append(keyboard_row)

                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(text, reply_markup=reply_markup)
                    else:
                        await query.edit_message_text(text)

            # Create pseudo-event
            pseudo_event = PseudoCallbackEvent(query, callback_data)

            # Call the event_handler's callback method
            await self.event_handler.callback(pseudo_event)

            return CALLBACK_QUERY_CODE

        except Exception as e:
            force_log(f"Error in callback_query_handler: {e}", "TelegramAdminBot")
            try:
                await query.edit_message_text(f"Error processing button action: {str(e)}")
            except Exception:
                pass
            return ConversationHandler.END

    async def _get_chat_with_validation(
        self,
        update: Update,
        chat_id: int,
    ) -> Chat | None:
        chat = await self.chat_service.get_chat_by_chat_id(chat_id)
        if not chat:
            await update.message.reply_text("Chat is not found.")  # type: ignore
            return None
        return chat


    @staticmethod
    async def enable_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data["command_type"] = "enable_shift"  # type: ignore
        keyboard = [
            [InlineKeyboardButton("Use Chat ID", callback_data="use_chat_id")],
            [InlineKeyboardButton("Use Group Name", callback_data="use_group_name")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(  # type: ignore
            "How would you like to find the chat to enable shift?", reply_markup=reply_markup
        )
        return ENABLE_SHIFT_SELECTION_CODE

    @staticmethod
    async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Please provide the phone number (with country code, e.g., +85512345678) by replying to this message.")  # type: ignore
        return GET_USERNAME_COMMAND_CODE

    async def process_chat_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if not update.message:
            return ConversationHandler.END

        try:
            # Validate not found
            chat_id: int = update.message.text.strip()  # type: ignore
            chat = await self._get_chat_with_validation(update, chat_id)
            if not chat:
                return ConversationHandler.END

            # Validate already activated
            if chat.is_active:  # type: ignore
                await update.message.reply_text("Chat has already been activated.")
                return ConversationHandler.END

            await self.chat_service.update_chat_status(chat_id, True)
            await update.message.reply_text("Chat has been activated successfully.")

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

        return ConversationHandler.END

    async def process_enable_shift_chat_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if not update.message:
            return ConversationHandler.END

        try:
            chat_id: int = update.message.text.strip()  # type: ignore
            chat = await self._get_chat_with_validation(update, chat_id)
            if not chat:
                return ConversationHandler.END

            # Check if chat has a user
            if not chat.user:  # type: ignore
                await update.message.reply_text(
                    "Chat does not have an associated user."
                )
                return ConversationHandler.END

            # Check if chat has business package
            group_package = await self.group_package_service.get_package_by_chat_id(
                chat_id
            )
            if not group_package or group_package.package != ServicePackage.BUSINESS:
                current_package = (
                    str(group_package.package) if group_package else "No package"
                )
                await update.message.reply_text(
                    f"Chat must have BUSINESS package to enable shift. Current package: {current_package}"
                )
                return ConversationHandler.END

            # Check if shift is already enabled
            if chat.enable_shift:  # type: ignore
                await update.message.reply_text(
                    "Shift is already enabled for this chat."
                )
                return ConversationHandler.END

            # Enable shift for the chat
            await self.chat_service.update_chat_enable_shift(chat_id, True)
            await update.message.reply_text(
                "Shift has been enabled successfully for this chat."
            )

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")

        return ConversationHandler.END

    @staticmethod
    async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return ConversationHandler.END

    def set_telethon_client(self, telethon_client):
        """Set the telethon client reference for username lookup"""
        self.telethon_client = telethon_client
        force_log("Telethon client reference set for admin bot", "TelegramAdminBot")

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.default_question)  # type: ignore
        return MENU_COMMAND_CODE

    async def process_menu_chat_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        if not update.message:
            return ConversationHandler.END

        try:
            chat_id: int = int(update.message.text.strip())  # type: ignore
            chat = await self._get_chat_with_validation(update, chat_id)
            if not chat:
                return ConversationHandler.END

            # Store the chat_id in context for use in callback queries
            context.user_data["admin_chat_id"] = chat_id

            # Create buttons for the menu
            keyboard = [
                [InlineKeyboardButton("ប្រចាំថ្ងៃ", callback_data="daily_summary")],
                [InlineKeyboardButton("ប្រចាំសប្តាហ៍", callback_data="weekly_summary")],
                [InlineKeyboardButton("ប្រចាំខែ", callback_data="monthly_summary")],
                [InlineKeyboardButton("បិទ", callback_data="close_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "ជ្រើសរើសរបាយការណ៍ប្រចាំ:", reply_markup=reply_markup
            )

        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")  # type: ignore
            force_log(f"Error in process_menu_chat_id: {e}", "TelegramAdminBot")

        return CALLBACK_QUERY_CODE

    async def menu_callback_query_handler(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle callback queries from menu inline buttons"""
        query = update.callback_query

        try:
            # We need to answer the callback query first to stop the loading indicator
            await query.answer()

            # Get the callback data
            callback_data = query.data

            # First, check if we're handling direct admin bot actions
            if callback_data in ["close_menu"]:
                await query.edit_message_text("Menu closed.")
                return ConversationHandler.END

            # Get chat_id from context or use message chat_id as fallback
            if context and context.user_data and "admin_chat_id" in context.user_data:
                chat_id = context.user_data["admin_chat_id"]
            else:
                # No stored chat ID from admin bot menu flow
                # This might be a global callback handler case
                await query.edit_message_text(
                    "Session expired. Please run /menu again."
                )
                return ConversationHandler.END

            # Prepare callback handlers for different report types
            if callback_data == "daily_summary":
                result = await self._handle_daily_summary_menu(chat_id, query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END
            elif callback_data == "weekly_summary":
                result = await self._handle_report(chat_id, "weekly", query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END
            elif callback_data == "monthly_summary":
                result = await self._handle_report(chat_id, "monthly", query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END
            elif callback_data == "menu":
                # Return to main menu - recreate the menu buttons
                keyboard = [
                    [InlineKeyboardButton("ប្រចាំថ្ងៃ", callback_data="daily_summary")],
                    [InlineKeyboardButton("ប្រចាំសប្តាហ៍", callback_data="weekly_summary")],
                    [InlineKeyboardButton("ប្រចាំខែ", callback_data="monthly_summary")],
                    [InlineKeyboardButton("បិទ", callback_data="close_menu")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    "ជ្រើសរើសរបាយការណ៍ប្រចាំ:", reply_markup=reply_markup
                )
                return CALLBACK_QUERY_CODE
            elif callback_data.startswith("summary_of_"):
                result = await self._handle_date_summary(chat_id, callback_data, query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END
            elif callback_data == "report_per_shift":
                result = await self._handle_shift_report(query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END
            elif callback_data == "other_dates":
                result = await self._handle_other_dates(query)
                return CALLBACK_QUERY_CODE if result else ConversationHandler.END

            # If we get here, it's an unknown callback
            await query.edit_message_text(f"Unhandled callback: {callback_data}")
            return CALLBACK_QUERY_CODE

        except Exception as e:
            force_log(f"Error in menu_callback_query_handler: {e}", "TelegramAdminBot")
            try:
                await query.edit_message_text(
                    f"Error processing button action: {str(e)}"
                )
            except Exception:
                pass
            return ConversationHandler.END

    async def _handle_daily_summary_menu(self, chat_id: int, query):
        """Handle daily summary by showing date selection menu like normal bot"""
        try:

            chat = await self.chat_service.get_chat_by_chat_id(chat_id)
            if not chat:
                await query.edit_message_text(f"Chat {chat_id} not found.")
                return False

            today = DateUtils.now()
            keyboard = []

            # Check if shift is enabled for this chat
            shift_enabled = await self.chat_service.is_shift_enabled(int(chat_id))
            if shift_enabled:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "ប្រចាំវេនថ្ងៃនេះ", callback_data="report_per_shift"
                        )
                    ]
                )
                # Only show current date for shift-enabled chats
                label = today.strftime("ថ្ងៃនេះ")
                callback_value = today.strftime("%Y-%m-%d")
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            label, callback_data=f"summary_of_{callback_value}"
                        )
                    ]
                )
            else:
                # Show 3 days for non-shift chats
                for i in range(2, -1, -1):
                    day = today - timedelta(days=i)
                    label = day.strftime("%b %d")
                    callback_value = day.strftime("%Y-%m-%d")
                    keyboard.append(
                        [
                            InlineKeyboardButton(
                                label, callback_data=f"summary_of_{callback_value}"
                            )
                        ]
                    )

            keyboard.append(
                [InlineKeyboardButton("ថ្ងៃផ្សេងទៀត", callback_data="other_dates")]
            )
            keyboard.append([InlineKeyboardButton("ត្រឡប់ក្រោយ", callback_data="menu")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("ឆែករបាយការណ៍ថ្ងៃ:", reply_markup=reply_markup)
            return True

        except Exception as e:
            force_log(f"Error in _handle_daily_summary_menu: {e}", "TelegramAdminBot")
            await query.edit_message_text(f"Error showing daily menu: {str(e)}")
            return False

    async def _handle_report(self, chat_id: int, report_type: str, query):
        """Handle generating a specific report type"""
        try:
            chat = await self.chat_service.get_chat_by_chat_id(chat_id)
            if not chat:
                await query.edit_message_text(f"Chat {chat_id} not found.")
                return False

            # Create return to menu button
            keyboard = [[InlineKeyboardButton("ត្រឡប់", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Get the user who clicked the button
            requesting_user = query.from_user if query else None

            if report_type == "daily":
                # Call report generation logic or reuse from event_handler
                report = await self._generate_report(chat_id, "daily", requesting_user)
                await query.edit_message_text(report, reply_markup=reply_markup, parse_mode='HTML')
            elif report_type == "weekly":
                report = await self._generate_report(chat_id, "weekly", requesting_user)
                await query.edit_message_text(report, reply_markup=reply_markup, parse_mode='HTML')
            elif report_type == "monthly":
                report = await self._generate_report(chat_id, "monthly", requesting_user)
                await query.edit_message_text(report, reply_markup=reply_markup, parse_mode='HTML')

            return True
        except Exception as e:
            force_log(f"Error in _handle_report: {e}", "TelegramAdminBot")
            await query.edit_message_text(
                f"Error generating {report_type} report: {str(e)}"
            )
            return False

    @staticmethod
    async def _handle_date_summary(chat_id: str, callback_data: str, query):
        """Handle date summary like normal bot"""
        try:

            date_str = callback_data.replace("summary_of_", "")
            selected_date = datetime.strptime(date_str, "%Y-%m-%d")

            income_service = IncomeService()
            incomes = await income_service.get_income_by_date_and_chat_id(
                chat_id=int(chat_id),
                start_date=selected_date,
                end_date=selected_date + timedelta(days=1),
            )

            # Create return to daily menu button
            keyboard = [
                [InlineKeyboardButton("ត្រឡប់ក្រោយ", callback_data="daily_summary")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if not incomes:
                message = (
                    f"គ្មានប្រតិបត្តិការសម្រាប់ថ្ងៃទី {selected_date.strftime('%d %b %Y')} ទេ។"
                )
            else:
                # Get username from the requesting user (who clicked the button)
                telegram_username = "Admin"
                if hasattr(query, 'from_user') and query.from_user:
                    requesting_user = query.from_user
                    if hasattr(requesting_user, 'username') and requesting_user.username:
                        telegram_username = requesting_user.username
                    elif hasattr(requesting_user, 'first_name') and requesting_user.first_name:
                        telegram_username = requesting_user.first_name
                    # If user is anonymous, username will remain "Admin"
                
                # Use new daily report format
                start_date = selected_date
                end_date = selected_date + timedelta(days=1)
                message = daily_transaction_report(incomes, selected_date, telegram_username, start_date, end_date)

            await query.edit_message_text(message, reply_markup=reply_markup)
            return True

        except Exception as e:
            force_log(f"Error in _handle_date_summary: {e}", "TelegramAdminBot")
            await query.edit_message_text(f"Error generating date summary: {str(e)}")
            return False

    @staticmethod
    async def _handle_shift_report(query):
        """Handle shift report - placeholder for now"""
        try:
            # For now, just show a placeholder message
            keyboard = [
                [InlineKeyboardButton("ត្រឡប់ក្រោយ", callback_data="daily_summary")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Shift report functionality not implemented yet.",
                reply_markup=reply_markup,
            )
            return True

        except Exception as e:
            force_log(f"Error in _handle_shift_report: {e}", "TelegramAdminBot")
            await query.edit_message_text(f"Error: {str(e)}")
            return False

    @staticmethod
    async def _handle_other_dates(query):
        """Handle other dates - placeholder for now"""
        try:
            # For now, just show a placeholder message
            keyboard = [
                [InlineKeyboardButton("ត្រឡប់ក្រោយ", callback_data="daily_summary")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Other dates functionality not implemented yet.",
                reply_markup=reply_markup,
            )
            return True

        except Exception as e:
            force_log(f"Error in _handle_other_dates: {e}", "TelegramAdminBot")
            await query.edit_message_text(f"Error: {str(e)}")
            return False

    @staticmethod
    async def _generate_report(chat_id: int, report_type: str, requesting_user=None) -> str:
        """Generate report text by calling appropriate service methods"""

        income_service = IncomeService()

        # Get current time using DateUtils for consistency
        now = DateUtils.now()

        if report_type == "daily":
            start_date = now
            end_date = now + timedelta(days=1)
            title = f"ថ្ងៃទី {now.strftime('%d %b %Y')}"
        elif report_type == "weekly":
            # Get start of week (Monday)
            start_of_week = now - timedelta(days=now.weekday())
            start_date = start_of_week
            end_date = now + timedelta(days=1)
            title = f"{start_of_week.strftime('%d')} - {now.strftime('%d %b %Y')}"
        elif report_type == "monthly":
            # First day of current month
            start_of_month = now.replace(day=1)
            start_date = start_of_month
            end_date = now + timedelta(days=1)
            title = f"{start_of_month.strftime('%d')} - {now.strftime('%d %b %Y')}"
        else:
            return "Invalid report type"

        # Get income data using the same method as normal bot
        incomes = await income_service.get_income_by_date_and_chat_id(
            chat_id=chat_id,
            start_date=start_date,
            end_date=end_date,
        )

        # If no data found, return no data message
        if not incomes:
            return f"គ្មានប្រតិបត្តិការសម្រាប់ {title} ទេ។"

        # For daily reports, use the new format
        if report_type == "daily":
            # Get username from the requesting user (who clicked the button)
            telegram_username = "Admin"
            if requesting_user:
                if hasattr(requesting_user, 'username') and requesting_user.username:
                    telegram_username = requesting_user.username
                elif hasattr(requesting_user, 'first_name') and requesting_user.first_name:
                    telegram_username = requesting_user.first_name
                # If user is anonymous, username will remain "Admin"
            
            return daily_transaction_report(incomes, now, telegram_username, start_date, end_date)
        elif report_type == "weekly":
            # Use the new weekly format
            return weekly_transaction_report(incomes, start_date, end_date)
        elif report_type == "monthly":
            # Use the new monthly format
            return monthly_transaction_report(incomes, start_date, end_date)
        
        # For other reports, use the old format
        period_text = title
        formatted_title = f"សរុបប្រតិបត្តិការ {period_text}"
        return total_summary_report(incomes, formatted_title)

    def setup(self) -> None:
        self.app = ApplicationBuilder().token(self.bot_token).build()

        # Package command handler with multiple states
        # Note: per_message=False warning is expected when mixing CallbackQueryHandler with other handler types
        package_handler = ConversationHandler(
            entry_points=[CommandHandler("package", self.package)],
            states={
                PACKAGE_SELECTION_CODE: [CallbackQueryHandler(self.shared_selection_handler)],
                PACKAGE_COMMAND_CODE: [
                    MessageHandler(
                        filters.TEXT & filters.REPLY, self.shared_process_input
                    ),
                    CallbackQueryHandler(self.package_button),
                ],
                USER_CONFIRMATION_CODE: [CallbackQueryHandler(self.package_button)],
                CHAT_SELECTION_CODE: [CallbackQueryHandler(self.handle_chat_selection)],
                PACKAGE_START_DATE_CODE: [MessageHandler(filters.TEXT & filters.REPLY, self.process_package_start_date)],
                PACKAGE_END_DATE_CODE: [MessageHandler(filters.TEXT & filters.REPLY, self.process_package_end_date)],
                AMOUNT_PAID_CODE: [MessageHandler(filters.TEXT & filters.REPLY, self.process_amount_paid)],
                NOTE_CONFIRMATION_CODE: [CallbackQueryHandler(self.handle_note_confirmation)],
                NOTE_INPUT_CODE: [MessageHandler(filters.TEXT & filters.REPLY, self.process_note_input)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_chat=True,
            per_user=True,
            per_message=False,
        )

        enable_shift_handler = ConversationHandler(
            entry_points=[CommandHandler("enable_shift", self.enable_shift)],
            states={
                ENABLE_SHIFT_SELECTION_CODE: [CallbackQueryHandler(self.shared_selection_handler)],
                ENABLE_SHIFT_COMMAND_CODE: [
                    MessageHandler(filters.TEXT & filters.REPLY, self.shared_process_input),
                    CallbackQueryHandler(self.shared_selection_handler),
                ],
                CHAT_SELECTION_CODE: [CallbackQueryHandler(self.handle_chat_selection)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_chat=True,
            per_user=True,
            per_message=False,
        )

        menu_handler = ConversationHandler(
            entry_points=[CommandHandler("menu", self.menu)],
            states={
                MENU_COMMAND_CODE: [
                    MessageHandler(
                        filters.TEXT & filters.REPLY, self.process_menu_chat_id
                    )
                ],
                CALLBACK_QUERY_CODE: [
                    CallbackQueryHandler(self.menu_callback_query_handler)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_chat=True,
            per_user=True,
            per_message=False,
        )

        self.app.add_handler(package_handler)
        self.app.add_handler(enable_shift_handler)
        self.app.add_handler(menu_handler)

        # Remove the global callback query handler to avoid duplicate handling
        # self.app.add_handler(CallbackQueryHandler(self.callback_query_handler))
        force_log("TelegramAdminBot handlers set up", "TelegramAdminBot")

    async def start_polling(self) -> None:
        if not self.app:
            self.setup()

        assert self.app is not None
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()  # type: ignore
        force_log("TelegramAdminBot started polling", "TelegramAdminBot")
