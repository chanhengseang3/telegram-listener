from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from common.enums import ServicePackage
from helper.logger_utils import force_log
from models import Chat
from services import ChatService, UserService
from services.group_package_service import GroupPackageService


class ChatSearchHandler:
    def __init__(self):
        self.chat_service = ChatService()
        self.user_service = UserService()
        self.group_package_service = GroupPackageService()

    async def validate_user_identifier(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            chat_id = int(update.message.text.strip())  # type: ignore
            chat = await self._get_chat_with_validation(update, chat_id)
            if not chat:
                return ConversationHandler.END

            identifier: str = chat.user.identifier if chat.user else ""  # type: ignore
            force_log(f"Identifier: {identifier}", "ChatSearchHandler")
            user = await self.user_service.get_user_by_identifier(identifier)
            if not user:
                await update.message.reply_text("User not found.")  # type: ignore
                return ConversationHandler.END

            context.user_data["user_identifier"] = identifier  # type: ignore
            context.user_data["chat_id_input"] = chat_id  # type: ignore
            context.user_data["found_user"] = user  # type: ignore
            
            # Import PackageHandler to show user confirmation
            from .package_handler import PackageHandler
            package_handler = PackageHandler()
            return await package_handler.show_user_confirmation(update, context, user)
        except Exception as e:
            await update.message.reply_text(f"Error: {str(e)}")  # type: ignore
            return ConversationHandler.END

    async def search_and_show_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        try:
            search_term = update.message.text.strip()  # type: ignore
            force_log(f"Searching for chats with term: {search_term}", "ChatSearchHandler")
            
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
                    # Import PackageHandler to show user confirmation
                    from .package_handler import PackageHandler
                    package_handler = PackageHandler()
                    return await package_handler.show_user_confirmation(update, context, chat.user)
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
            
            return 1010  # CHAT_SELECTION_CODE
            
        except Exception as e:
            force_log(f"Error in search_and_show_chats: {e}", "ChatSearchHandler")
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
                    force_log(f"Selected chat_id: {chat_id} for command: {command_type}", "ChatSearchHandler")
                    
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
                        return 1003  # PACKAGE_COMMAND_CODE
                    
                    # For query package command, display package details directly
                    elif command_type == "query_package":
                        from .package_handler import PackageHandler
                        package_handler = PackageHandler()
                        return await package_handler.display_package_details(update, context)
                    
                    # For other commands, execute directly
                    elif command_type == "enable_shift":
                        await query.edit_message_text(f"Executing enable shift for chat: {chat.group_name}")
                        return await self.execute_enable_shift_command_from_query(query, int(chat_id))
                        
        except Exception as e:
            force_log(f"Error in handle_chat_selection: {e}", "ChatSearchHandler")
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
                        return 1006  # ENABLE_SHIFT_COMMAND_CODE
                    elif command_type == "query_package":
                        return 1020  # QUERY_PACKAGE_COMMAND_CODE
                    else:
                        return 1003  # PACKAGE_COMMAND_CODE

                elif selection == "use_group_name":
                    context.user_data["selection_type"] = "group_name"  # type: ignore
                    await query.edit_message_text(
                        "Please provide the group name to search. You can enter partial group name (up to 5 results will be shown)."
                    )
                    # Return appropriate command code based on command type
                    if command_type == "enable_shift":
                        return 1006  # ENABLE_SHIFT_COMMAND_CODE
                    elif command_type == "query_package":
                        return 1020  # QUERY_PACKAGE_COMMAND_CODE
                    else:
                        return 1003  # PACKAGE_COMMAND_CODE

        except Exception as e:
            force_log(f"Error in shared_selection_handler: {e}", "ChatSearchHandler")
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
            force_log(f"Searching for chats with term: {search_term} for command: {command_type}", "ChatSearchHandler")
            
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
                elif command_type == "query_package":
                    # Execute query package directly
                    context.user_data["group_name"] = chat.group_name
                    from .package_handler import PackageHandler
                    package_handler = PackageHandler()
                    return await package_handler.display_package_details(update, context)
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
                    return 1003  # PACKAGE_COMMAND_CODE
            
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
            return 1010  # CHAT_SELECTION_CODE
            
        except Exception as e:
            force_log(f"Error in search_and_show_chats_for_command: {e}", "ChatSearchHandler")
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
            force_log(f"Error in execute_enable_shift_command: {e}", "ChatSearchHandler")
            await update.message.reply_text("Error enabling shift for chat.")  # type: ignore
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
            force_log(f"Error in execute_enable_shift_command_from_query: {e}", "ChatSearchHandler")
            await query.edit_message_text("Error enabling shift for chat.")
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