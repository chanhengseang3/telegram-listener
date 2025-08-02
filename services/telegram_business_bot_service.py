import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application,
    ConversationHandler,
    CallbackQueryHandler,
)

from common.enums import ServicePackage
from handlers.business_event_handler import BusinessEventHandler
from helper import force_log
from services import ChatService, UserService, GroupPackageService

# Get logger
logger = logging.getLogger(__name__)

# Business bot specific conversation states
BUSINESS_MENU_CODE = 2001
BUSINESS_SUMMARY_CODE = 2002
BUSINESS_ANALYTICS_CODE = 2003
BUSINESS_SETTINGS_CODE = 2004
BUSINESS_CALLBACK_CODE = 2005


class AutosumBusinessBot:
    """
    Specialized business bot with different event handling and features
    """

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.app: Application | None = None
        self.chat_service = ChatService()
        self.user_service = UserService()
        self.event_handler = BusinessEventHandler()
        self.group_package_service = GroupPackageService()
        force_log("AutosumBusinessBot initialized with token", "AutosumBusinessBot")

    def _convert_buttons_to_keyboard(self, buttons):
        """Convert tuple buttons to InlineKeyboardButton objects"""
        if not buttons:
            return None

        keyboard_buttons = []
        for row in buttons:
            button_row = []
            for button in row:
                if isinstance(button, tuple) and len(button) == 2:
                    text, callback_data = button
                    button_row.append(
                        InlineKeyboardButton(text, callback_data=callback_data)
                    )
            keyboard_buttons.append(button_row)

        return InlineKeyboardMarkup(keyboard_buttons)

    async def business_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Business bot start command with specialized welcome message"""
        welcome_message = """
🏢 ស្វាគមន៍មកកាន់ Autosum Business!

💼 ជំនួយការហិរញ្ញវត្ថុអាជីវកម្មរបស់អ្នក

បុតនេះផ្តល់នូវមុខងារអាជីវកម្មកម្រិតខ្ពស់:
• 📊 តាមដានចំណូលពេលវេលាពិត
• 📈 ការវិភាគនិងចំណេះដឹងអាជីវកម្ម
• 💰 ការគាំទ្ររូបិយប័ណ្ណច្រើន
• 📱 ផ្ទាំងគ្រប់គ្រងងាយស្រួលប្រើ

🚀 ការចាប់ផ្តើម:
1. ប្រើ /menu ដើម្បីចូលទៅផ្ទាំងគ្រប់គ្រងអាជីវកម្ម
2. ចុះឈ្មោះជជែករបស់អ្នកសម្រាប់សេវាអាជីវកម្ម
3. ចាប់ផ្តើមតាមដានចំណូលដោយស្វ័យប្រវត្តិ


វាយ /menu ដើម្បីចាប់ផ្តើមគ្រប់គ្រងហិរញ្ញវត្ថុអាជីវកម្មរបស់អ្នក!
        """

        await update.message.reply_text(welcome_message)

    async def business_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Business-specific menu handler"""
        force_log(
            f"CRITICAL DEBUG: business_menu called for chat_id: {update.effective_chat.id}", "AutosumBusinessBot"
        )

        # Create a mock event object for the business event handler
        class MockEvent:
            def __init__(self, update, parent):
                self.chat_id = update.effective_chat.id
                self.chat = update.effective_chat
                self.parent = parent

            async def respond(self, message, buttons=None):
                keyboard = (
                    self.parent._convert_buttons_to_keyboard(buttons)
                    if buttons
                    else None
                )
                await update.message.reply_text(message, reply_markup=keyboard)

            async def get_sender(self):
                return update.effective_user

        mock_event = MockEvent(update, self)

        try:
            await self.event_handler.menu(mock_event)
            return BUSINESS_MENU_CODE
        except Exception as e:
            force_log(f"Error in business menu: {e}", "AutosumBusinessBot")
            import traceback

            force_log(f"Full traceback: {traceback.format_exc()}", "AutosumBusinessBot")
            await update.message.reply_text(
                "❌ Error loading business menu. Please try again."
            )
            return ConversationHandler.END

    async def handle_business_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Handle business-specific callback queries"""
        query = update.callback_query
        force_log(f"CRITICAL: handle_business_callback received: {query.data}", "AutosumBusinessBot")
        await query.answer()

        # Create a mock event for the business handler
        class MockCallbackEvent:
            def __init__(self, query, parent):
                self.chat_id = query.message.chat_id
                self.data = query.data.encode("utf-8")
                self.query = query
                self.parent = parent
                self.chat = query.message.chat

            async def edit(self, message, buttons=None):
                keyboard = (
                    self.parent._convert_buttons_to_keyboard(buttons)
                    if buttons
                    else None
                )
                try:
                    await self.query.edit_message_text(message, reply_markup=keyboard)
                except Exception as e:
                    if "Message is not modified" in str(e):
                        force_log(f"Message content is identical, skipping edit for chat {self.chat_id}")
                        # Just answer the callback to remove loading state
                        await self.query.answer()
                    else:
                        # Re-raise other exceptions
                        raise e

            async def delete(self):
                """Delete the current message"""
                try:
                    await self.query.message.delete()
                except Exception as e:
                    force_log(f"Error deleting message in chat {self.chat_id}: {e}")

            async def respond(self, message, buttons=None, parse_mode=None):
                """Send a new message with optional HTML parsing"""
                keyboard = (
                    self.parent._convert_buttons_to_keyboard(buttons)
                    if buttons
                    else None
                )
                try:
                    await self.parent.app.bot.send_message(
                        chat_id=self.chat_id,
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=parse_mode
                    )
                    # Answer the callback to remove loading state
                    await self.query.answer()
                except Exception as e:
                    force_log(f"Error responding to chat {self.chat_id}: {e}")
                    raise e

            async def get_sender(self):
                return query.from_user

        mock_event = MockCallbackEvent(query, self)

        try:
            # Handle business callbacks through event handler
            force_log(f"Delegating callback to event handler: {query.data}", "AutosumBusinessBot")
            await self.event_handler.handle_business_callback(mock_event)
            return BUSINESS_CALLBACK_CODE
        except Exception as e:
            force_log(f"Error handling business callback: {e}", "AutosumBusinessBot")
            import traceback

            force_log(f"Full traceback: {traceback.format_exc()}", "AutosumBusinessBot")
            await query.edit_message_text(
                "❌ Error processing request. Please try again."
            )
            return ConversationHandler.END

    async def business_support(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Business support command"""
        support_message = """
📞 មជ្ឈមណ្ឌលការគាំទ្រអាជីវកម្ម

🆘 ជំនួយរហ័ស:
• បុតមិនឆ្លើយតប? សាកល្បង /start ដើម្បីផ្ទុកឡើងវិញ
• បាត់ប្រតិបត្តិការ? ពិនិត្យការចុះឈ្មោះជជែក
• ត្រូវការលក្ខណៈពិសេសផ្ទាល់ខ្លួន? ទាក់ទងក្រុមយើង

📧 ព័ត៌មានទំនាក់ទំនង:
• អ៊ីមែល: business@autosum.com
• ទូរស័ព្ទ: +1-XXX-XXX-XXXX
• ម៉ោងការគាំទ្រ: ច័ន្ទ-សុក្រ 9AM-6PM EST

🚀 សេវាអាជីវកម្ម:
• ដំណោះស្រាយរបាយការណ៍ផ្ទាល់ខ្លួន
• ការរួមបញ្ចូល API
• សម័យប្រមុងក្រុម
• លក្ខណៈពិសេសការវិភាគកម្រិតខ្ពស់

💬 ការគាំទ្រភ្លាមៗ:
ឆ្លើយតបសារនេះជាមួយនឹងសំណួររបស់អ្នក ហើយក្រុមយើងនឹងឆ្លើយតបក្នុងរយៈពេល 24 ម៉ោង។

🔗 ធនធាន:
• មគ្គុទ្ទេសក៍អ្នកប្រើប្រាស់: /help
• ផ្ទាំងគ្រប់គ្រង: /menu
• សំណើលក្ខណៈពិសេស: ទាក់ទងក្រុមការគាំទ្រ
        """

        await update.message.reply_text(support_message)

    async def register_chat(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Register chat command - registers chat and asks about shift enablement"""
        chat_id = int(update.effective_chat.id)

        try:
            # Check if chat is already registered
            chat = await self.chat_service.get_chat_by_chat_id(chat_id)
            if chat:
                message = f"""
✅ អ្នកបានចុះឈ្មោះដោយជោគជ័យហើយ

🆔 Chat ID: {chat_id}

តើអ្នកចង់ប្រើវេនទេ?
                """

                # Create buttons for shift choice
                buttons = [
                    [("✅ បើកវេន", "register_enable_shift")],
                    [("❌ មិនបើកវេនទេ", "register_skip_shift")],
                    [("🏠 ទៅមីនុយ", "back_to_menu")],
                ]

                keyboard = self._convert_buttons_to_keyboard(buttons)
                await update.message.reply_text(message, reply_markup=keyboard)
                return

            # Get user information for registration
            user = update.effective_user
            if not user or not hasattr(user, "id") or user.id is None:
                message = """
⚠️ ការចុះឈ្មោះបរាជ័យ

អ្នកត្រូវតែជាអ្នកប្រើប្រាស់ដែលមិនមែនអនាមិកដើម្បីចុះឈ្មោះជជែកនេះសម្រាប់សេវាអាជីវកម្ម។
                """
                await update.message.reply_text(message)
                return

            # Create user if needed
            user_service = UserService()
            db_user = await user_service.create_user(user)

            # Get chat title
            chat_title = "Business Chat"
            try:
                if (
                    hasattr(update.effective_chat, "title")
                    and update.effective_chat.title
                ):
                    chat_title = update.effective_chat.title
            except:
                pass

            # Register the chat
            success, reg_message = await self.chat_service.register_chat_id(
                chat_id, f"[BUSINESS] {chat_title}", db_user
            )

            if success:
                # Assign BUSINESS package for business bot registrations
                try:
                    await self.group_package_service.create_group_package(
                        chat_id, ServicePackage.BUSINESS
                    )
                    force_log(f"Assigned BUSINESS package to chat_id: {chat_id}", "AutosumBusinessBot")
                except Exception as package_error:
                    force_log(
                        f"Error assigning BUSINESS package to chat_id {chat_id}: {package_error}", "AutosumBusinessBot"
                    )
                # Registration successful, now ask about shift
                message = f"""
✅ ការចុះឈ្មោះបានជោគជ័យ!

🆔 Chat ID: {chat_id}
📊 ប្រភេទ: សេវាអាជីវកម្ម
👤 ចុះឈ្មោះដោយ: {user.first_name}

🔧 តើអ្នកចង់បើកវេនដើម្បីចាប់ផ្តើមតាមដានប្រតិបត្តិការឥឡូវនេះទេ?
                """

                # Create buttons for shift choice
                buttons = [
                    [("✅ បាទ/ចាស បើកវេន", "register_enable_shift")],
                    [("❌ ទេ មិនបើកវេនទេ", "register_skip_shift")],
                    [("🏠 ទៅមីនុយ", "back_to_menu")],
                ]

                keyboard = self._convert_buttons_to_keyboard(buttons)
                await update.message.reply_text(message, reply_markup=keyboard)
            else:
                await update.message.reply_text(f"❌ ការចុះឈ្មោះបរាជ័យ: {reg_message}")

        except Exception as e:
            force_log(f"Error registering chat: {e}", "AutosumBusinessBot")
            await update.message.reply_text("❌ មានបញ្ហាក្នុងការចុះឈ្មោះ។ សូមសាកល្បងម្តងទៀត។")

    async def enable_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Enable shift command - starts a new shift"""
        chat_id = int(update.effective_chat.id)

        try:
            # Check if chat is registered
            chat = await self.chat_service.get_chat_by_chat_id(chat_id)
            if not chat:
                message = """
⚠️ មិនទាន់ចុះឈ្មោះ

សូមប្រើ /menu ដើម្បីចុះឈ្មោះជជែករបស់អ្នកសម្រាប់សេវាអាជីវកម្មជាមុនសិន។
                """
                await update.message.reply_text(message)
                return

            # Check if there's already an active shift
            current_shift = await self.event_handler.shift_service.get_current_shift(
                chat_id
            )

            if current_shift:
                message = f"""
⚠️ មានវេនសកម្មរួចហើយ

វេន #{current_shift.number} កំពុងដំណើរការ
⏰ ចាប់ផ្តើម: {current_shift.start_time.strftime('%Y-%m-%d %H:%M')}

💡 ប្រសិនបើអ្នកចង់បិទវេនបច្ចុប្បន្ន សូមប្រើ /menu ហើយជ្រើសរើស "បិទវេន"
                """
                await update.message.reply_text(message)
                return

            # Create new shift
            new_shift = await self.event_handler.shift_service.create_shift(chat_id)

            message = f"""
✅ វេនថ្មីត្រូវបានបើកដោយជោគជ័យ!

📊 វេន #{new_shift.number}
⏰ ចាប់ផ្តើម: {new_shift.start_time.strftime('%Y-%m-%d %H:%M')}
🟢 ស្ថានភាព: កំពុងបន្ត

💡 ឥឡូវនេះប្រតិបត្តិការថ្មីទាំងអស់នឹងត្រូវបានកត់ត្រាក្នុងវេននេះ។
🔧 ប្រើ /menu ដើម្បីគ្រប់គ្រងវេននិងមើលរបាយការណ៍។
            """

            await update.message.reply_text(message)

        except Exception as e:
            force_log(f"Error enabling shift: {e}", "AutosumBusinessBot")
            await update.message.reply_text("❌ មានបញ្ហាក្នុងការបើកវេន។ សូមសាកល្បងម្តងទៀត។")

    async def handle_register_enable_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle register flow - enable shift option"""
        query = update.callback_query
        await query.answer()

        chat_id = query.message.chat_id

        try:
            # Simple database update
            await self.chat_service.update_chat_enable_shift(chat_id, True)

            # Simple response with menu button
            buttons = [[("🏠 ទៅមីនុយ", "back_to_menu")]]
            keyboard = self._convert_buttons_to_keyboard(buttons)
            await query.edit_message_text("✅ បើកវេនដោយជោគជ័យ!", reply_markup=keyboard)

        except Exception as e:
            force_log(f"Error: {e}", "AutosumBusinessBot")
            await query.edit_message_text("❌ Error", reply_markup=None)

    async def handle_register_skip_shift(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle register flow - skip shift option"""
        query = update.callback_query
        await query.answer()

        buttons = [[("🏠 ទៅមីនុយ", "back_to_menu")]]
        keyboard = self._convert_buttons_to_keyboard(buttons)
        await query.edit_message_text(
            "✅ ការចុះឈ្មោះបានបញ្ចប់ដោយជោគជ័យ!", reply_markup=keyboard
        )

    async def handle_back_to_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle back to menu button"""
        query = update.callback_query
        await query.answer()

        # Create a mock event to call the menu handler
        class MockEvent:
            def __init__(self, update, parent):
                self.chat_id = update.callback_query.message.chat_id
                self.chat = update.callback_query.message.chat
                self.parent = parent

            async def edit(self, message, buttons=None):
                keyboard = (
                    self.parent._convert_buttons_to_keyboard(buttons)
                    if buttons
                    else None
                )
                await query.edit_message_text(message, reply_markup=keyboard)

            async def respond(self, message, buttons=None):
                await self.edit(message, buttons)

            async def get_sender(self):
                return query.from_user

        mock_event = MockEvent(update, self)
        await self.event_handler.menu(mock_event)

    async def handle_close_menu(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle close menu button"""
        query = update.callback_query
        await query.answer()

        try:
            await query.delete_message()
        except Exception as e:
            # Fallback to editing the message if delete fails
            await query.edit_message_text("បានបិទ", reply_markup=None)

    async def handle_fallback_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle any callbacks not caught by other handlers"""
        query = update.callback_query
        force_log(
            f"CRITICAL: Fallback callback handler received: {query.data} from chat_id: {query.message.chat_id}", "AutosumBusinessBot"
        )
        await query.answer()

        # Try to handle as business callback if it looks like a business operation
        if (query.data in [
            "close_shift",
            "current_shift_report",
            "previous_shift_report",
            "other_days_report",
            "back_to_menu",
            "close_menu",
        ] or
            query.data.startswith("shift_") or query.data.startswith("date_")):
            force_log(f"Routing fallback callback {query.data} to business handler", "AutosumBusinessBot")
            return await self.handle_business_callback(update, context)

        # Unknown callback
        await query.edit_message_text(
            "❌ Unknown action. Please try again.", reply_markup=None
        )

    def setup(self):
        """Setup the business bot with specialized handlers"""
        if not self.bot_token:
            raise ValueError("Business bot token is required")

        self.app = ApplicationBuilder().token(self.bot_token).build()

        # Business-specific command handlers
        self.app.add_handler(CommandHandler("start", self.business_start))
        self.app.add_handler(CommandHandler("support", self.business_support))
        self.app.add_handler(CommandHandler("register", self.register_chat))
        self.app.add_handler(CommandHandler("shift", self.enable_shift))

        # Business menu conversation handler
        business_menu_handler = ConversationHandler(
            entry_points=[CommandHandler("menu", self.business_menu)],
            states={
                BUSINESS_MENU_CODE: [
                    CallbackQueryHandler(self.handle_business_callback),
                ],
                BUSINESS_CALLBACK_CODE: [
                    CallbackQueryHandler(self.handle_business_callback),
                ],
            },
            fallbacks=[CommandHandler("menu", self.business_menu)],
            per_message=False,
        )

        self.app.add_handler(business_menu_handler)

        # Add separate callback handlers for registration flow
        self.app.add_handler(
            CallbackQueryHandler(
                self.handle_register_enable_shift, pattern="^register_enable_shift$"
            )
        )
        self.app.add_handler(
            CallbackQueryHandler(
                self.handle_register_skip_shift, pattern="^register_skip_shift$"
            )
        )
        self.app.add_handler(
            CallbackQueryHandler(self.handle_back_to_menu, pattern="^back_to_menu$")
        )

        # Add fallback callback handler for any unhandled callbacks
        self.app.add_handler(CallbackQueryHandler(self.handle_fallback_callback))

        # Add error handler
        self.app.add_error_handler(self.error_handler)

        force_log("AutosumBusinessBot setup completed", "AutosumBusinessBot")

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle errors in the business bot"""
        force_log(f"Business bot error: {context.error}", "AutosumBusinessBot")

        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred in the business bot. Please try again or contact support."
            )

    async def start_polling(self):
        """Start the business bot polling"""
        try:
            self.setup()
            force_log("Starting AutosumBusinessBot polling...", "AutosumBusinessBot")

            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            force_log("AutosumBusinessBot is running and polling for updates...", "AutosumBusinessBot")

            # Keep the bot running indefinitely
            try:
                await self.app.updater.idle()
            except Exception:
                # If idle fails, just wait indefinitely
                import asyncio

                while True:
                    await asyncio.sleep(3600)  # Sleep for 1 hour at a time

        except Exception as e:
            force_log(f"Error starting AutosumBusinessBot: {e}", "AutosumBusinessBot")
            raise

    async def send_message(self, chat_id: int, message: str) -> bool:
        """Send a message to a specific chat"""
        try:
            if self.app and self.app.bot:
                await self.app.bot.send_message(chat_id=chat_id, text=message)
                return True
            else:
                force_log("Bot application not initialized")
                return False
        except Exception as e:
            force_log(f"Error sending message to chat {chat_id}: {e}")
            return False

    async def stop(self):
        """Stop the business bot"""
        if self.app:
            try:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                logger.info("AutosumBusinessBot stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping AutosumBusinessBot: {e}")
