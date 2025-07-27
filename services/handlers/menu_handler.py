from datetime import timedelta, datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from helper import DateUtils, daily_transaction_report, weekly_transaction_report, monthly_transaction_report
from helper.logger_utils import force_log
from services import ChatService, IncomeService


class MenuHandler:
    def __init__(self):
        self.chat_service = ChatService()

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
            force_log(f"Error in _handle_daily_summary_menu: {e}", "MenuHandler")
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
            force_log(f"Error in _handle_report: {e}", "MenuHandler")
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
            force_log(f"Error in _handle_date_summary: {e}", "MenuHandler")
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
            force_log(f"Error in _handle_shift_report: {e}", "MenuHandler")
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
            force_log(f"Error in _handle_other_dates: {e}", "MenuHandler")
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
        from helper import total_summary_report
        period_text = title
        formatted_title = f"សរុបប្រតិបត្តិការ {period_text}"
        return total_summary_report(incomes, formatted_title)

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
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE
            elif callback_data == "weekly_summary":
                result = await self._handle_report(chat_id, "weekly", query)
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE
            elif callback_data == "monthly_summary":
                result = await self._handle_report(chat_id, "monthly", query)
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE
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
                return 1008  # CALLBACK_QUERY_CODE
            elif callback_data.startswith("summary_of_"):
                result = await self._handle_date_summary(chat_id, callback_data, query)
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE
            elif callback_data == "report_per_shift":
                result = await self._handle_shift_report(query)
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE
            elif callback_data == "other_dates":
                result = await self._handle_other_dates(query)
                return 1008 if result else ConversationHandler.END  # CALLBACK_QUERY_CODE

            # If we get here, it's an unknown callback
            await query.edit_message_text(f"Unhandled callback: {callback_data}")
            return 1008  # CALLBACK_QUERY_CODE

        except Exception as e:
            force_log(f"Error in menu_callback_query_handler: {e}", "MenuHandler")
            try:
                await query.edit_message_text(
                    f"Error processing button action: {str(e)}"
                )
            except Exception:
                pass
            return ConversationHandler.END