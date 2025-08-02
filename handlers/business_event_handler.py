from typing import List

from common.enums import ServicePackage, FeatureFlags
from helper import DateUtils, shift_report_format, current_shift_report_format
from helper.logger_utils import force_log
from models import User
from services.chat_service import ChatService
from services.group_package_service import GroupPackageService
from services.income_balance_service import IncomeService
from services.shift_configuration_service import ShiftConfigurationService
from services.shift_service import ShiftService
from services.user_service import UserService
from .bot_event_handler import CommandHandler


class BusinessEventHandler:
    """
    Specialized event handler for autosum_business bot with different business logic
    """

    def __init__(self):
        self.command_handler = CommandHandler()
        self.chat_service = ChatService()
        self.income_service = IncomeService()
        self.shift_service = ShiftService()
        self.shift_config_service = ShiftConfigurationService()
        self.group_package_service = GroupPackageService()

    async def menu(self, event):
        """Business-specific menu handler"""
        force_log(f"BusinessEventHandler.menu called for chat_id: {event.chat_id}")
        # Check if chat is activated and trial status
        chat = await self.chat_service.get_chat_by_chat_id(event.chat_id)
        if not chat:
            # Auto-register for business bot
            try:
                sender = await event.get_sender()

                if not sender or not hasattr(sender, "id") or sender.id is None:
                    message = "⚠️ Business Registration failed: You must be a non-anonymous user to register this chat for business services."
                    await event.respond(message)
                    return

                # Create user for business service
                user_service = UserService()
                user = await user_service.create_user(sender)

                # Register with business-specific settings
                await self.register_business(event, user)

                # Refresh chat information after registration
                chat = await self.chat_service.get_chat_by_chat_id(event.chat_id)

                if not chat:
                    return

            except Exception as e:
                force_log(f"Error during business auto-registration: {e}", "ERROR")
                message = "⚠️ Business auto-registration failed. Please contact support."
                await event.respond(message)
                return

        # Create menu buttons based on shift status
        chat_id = event.chat_id

        # Check for auto close before showing menu
        # await self.check_auto_close_shift(chat_id)

        current_shift = await self.shift_service.get_current_shift(chat_id)
        
        # Check if weekly/monthly reports feature is enabled
        has_weekly_monthly_reports = await self.group_package_service.has_feature(
            chat_id, FeatureFlags.WEEKLY_MONTHLY_REPORTS.value
        )

        if current_shift:
            buttons = [
                [("📊 របាយការណ៍វេននេះ", "current_shift_report")],
                # [("📈 របាយការណ៍វេនមុន", "previous_shift_report")],
                [("📅 របាយការណ៍ថ្ងៃផ្សេង", "other_days_report")],
            ]
            
            # Add weekly/monthly reports if feature is enabled
            if has_weekly_monthly_reports:
                buttons.append([("📆 របាយការណ៍ប្រចាំសប្តាហ៍", "weekly_reports")])
                buttons.append([("📊 របាយការណ៍ប្រចាំខែ", "monthly_reports")])
            
            buttons.append([("❌ ត្រលប់ក្រោយ", "close_menu")])
        else:
            buttons = [
                [("📈 របាយការណ៍វេនមុន", "previous_shift_report")],
                [("📅 របាយការណ៍ថ្ងៃផ្សេង", "other_days_report")],
            ]
            
            # Add weekly/monthly reports if feature is enabled
            if has_weekly_monthly_reports:
                buttons.append([("📆 របាយការណ៍ប្រចាំសប្តាហ៍", "weekly_reports")])
                buttons.append([("📊 របាយការណ៍ប្រចាំខែ", "monthly_reports")])
            
            buttons.append([("❌ បិទ", "close_menu")])

        message = f"""
ជ្រើសរើសជម្រើសខាងក្រោម
"""

        # Check if this is a callback query (edit existing message) or new message (respond)
        if hasattr(event, "data") and hasattr(event, "edit"):
            # This is a callback query, edit the existing message
            await event.edit(message, buttons=buttons)
        else:
            # This is a regular message, respond with new message
            await event.respond(message, buttons=buttons)

    async def register_business(self, event, user: User):
        """Register chat for business services with special configuration"""
        chat_id = event.chat_id
        chat_title = "Business Chat"

        # Try to get chat title
        try:
            if hasattr(event, "chat") and event.chat:
                chat_title = getattr(event.chat, "title", "Business Chat")
        except:
            force_log("Failed to register business chat")

        success, message = await self.chat_service.register_chat_id(
            chat_id, f"[BUSINESS] {chat_title}", user
        )

        if success:
            # Assign BUSINESS package for business bot registrations
            try:
                await self.group_package_service.create_group_package(
                    chat_id, ServicePackage.BUSINESS
                )
                force_log(f"Assigned BUSINESS package to chat_id: {chat_id}")
            except Exception as package_error:
                force_log(
                    f"Error assigning BUSINESS package to chat_id {chat_id}: {package_error}"
                )
            response = f"""
✅ ការចុះឈ្មោះអាជីវកម្មបានជោគជ័យ!

🏢 ជជែករបស់អ្នកត្រូវបានចុះឈ្មោះសម្រាប់សេវាអាជីវកម្ម។
📊 ការវិភាគកម្រិតខ្ពស់ឥឡូវនេះត្រូវបានបើក។
💼 អ្នកអាចចូលប្រើលក្ខណៈពិសេសអាជីវកម្មតាមរយៈម៉ឺនុយ។

វាយ /menu ដើម្បីចាប់ផ្តើមជាមួយនឹងផ្ទាំងគ្រប់គ្រងអាជីវកម្មរបស់អ្នក។
"""
        else:
            response = f"❌ Business registration failed: {message}"

        await event.respond(response)

    async def handle_business_callback(self, event):
        """Handle business-specific callback queries"""
        data = event.data.decode("utf-8")
        force_log(f"handle_business_callback received data: {data}")

        if data == "current_shift_report":
            await self.show_current_shift_report(event)
        elif data == "previous_shift_report":
            await self.show_previous_shift_report(event)
        elif data == "other_days_report":
            await self.show_other_days_report(event)
        elif data == "close_shift":
            await self.close_current_shift(event)
        elif data == "close_menu":
            await self.close_menu(event)
        elif data == "back_to_menu":
            await self.menu(event)
        elif data.startswith("shift_"):
            await self.show_specific_shift_report(event, data)
        elif data.startswith("date_"):
            await self.show_date_shifts(event, data)
        elif data == "weekly_reports":
            await self.show_weekly_reports(event)
        elif data == "monthly_reports":
            await self.show_monthly_reports(event)
        elif data.startswith("week_"):
            await self.show_weekly_report(event, data)
        elif data.startswith("month_"):
            await self.show_monthly_report(event, data)
        else:
            # Fallback to regular command handler
            await self.command_handler.handle_callback_query(event)

    async def show_current_shift_report(self, event):
        """Show current shift report"""
        chat_id = event.chat_id
        force_log(f"show_current_shift_report called for chat_id: {chat_id}")

        try:
            current_shift = await self.shift_service.get_current_shift(chat_id)
            force_log(f"Current shift for chat_id {chat_id}: {current_shift}")

            if not current_shift:
                message = """
📊 របាយការណ៍វេនបច្ចុប្បន្ន

🔴 គ្មានវេនសកម្មកំពុងដំណើរការ។

💡 វេនថ្មីនឹងត្រូវបានបង្កើតដោយស្វ័យប្រវត្តិនៅពេលមានប្រតិបត្តិការថ្មី។
"""
                buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            else:
                shift_summary = await self.shift_service.get_shift_income_summary(
                    current_shift.id, chat_id
                )

                # Handle case where shift exists but has no transactions yet
                if shift_summary["transaction_count"] == 0:
                    # Calculate duration for empty shift
                    try:
                        now = DateUtils.now()
                        aware_start_time = DateUtils.localize_datetime(
                            current_shift.start_time
                        )
                        duration = now - aware_start_time
                        total_seconds = abs(duration.total_seconds())
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                    except Exception:

                        now = DateUtils.now()
                        duration = now - current_shift.start_time
                        total_seconds = abs(duration.total_seconds())
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)

                    message = f"""
📊 របាយការណ៍វេនបច្ចុប្បន្ន #{current_shift.number}

⏱️ រយៈពេល: {hours}ម៉ោង {minutes}នាទី
⏰ ចាប់ផ្តើម: {current_shift.start_time.strftime('%Y-%m-%d %I:%M %p')}
🟢 កំពុងបន្ត

💰 សង្ខេបចំណូលសរុប:
• មិនទាន់មានប្រតិបត្តិការទេ
"""
                else:
                    # Calculate duration - simplified approach first
                    try:
                        now = DateUtils.now()
                        aware_start_time = DateUtils.localize_datetime(
                            current_shift.start_time
                        )
                        duration = now - aware_start_time
                        total_seconds = abs(duration.total_seconds())
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)
                    except Exception as e:
                        force_log(f"Error in duration calculation: {e}", "ERROR")
                        # Fallback to simple calculation

                        now = DateUtils.now()

                        duration = now - current_shift.start_time
                        total_seconds = abs(duration.total_seconds())
                        hours = int(total_seconds // 3600)
                        minutes = int((total_seconds % 3600) // 60)

                # Use new shift report format
                message = current_shift_report_format(
                    current_shift.number,
                    current_shift.start_time,
                    current_shift.start_time,
                    shift_summary,
                    hours,
                    minutes
                )

                buttons = [
                    [("🛑 បិទបញ្ជី", "close_shift")],
                    [("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")],
                ]

        except Exception as e:
            force_log(f"Error showing current shift report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        await event.edit(message, buttons=buttons)

    async def show_previous_shift_report(self, event):
        """Show previous shift report (last closed shift)"""
        chat_id = int(event.chat_id)

        try:
            previous_shifts = await self.shift_service.get_recent_closed_shifts(
                chat_id, 1
            )

            if not previous_shifts:
                message = """
📈 របាយការណ៍វេនមុន

🔴 គ្មានវេនដែលបានបិទ។

💡 វេនមុននឹងបង្ហាញនៅទីនេះបន្ទាប់ពីអ្នកបិទវេន។
"""
                buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            else:
                shift = previous_shifts[0]
                shift_summary = await self.shift_service.get_shift_income_summary(
                    shift.id, chat_id
                )

                # Calculate duration
                duration = shift.end_time - shift.start_time
                total_seconds = abs(duration.total_seconds())
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)

                # Use new shift report format for closed shift
                message = shift_report_format(
                    shift.number,
                    shift.start_time,
                    shift.start_time,
                    shift.end_time,
                    shift_summary,
                    auto_closed=False  # We don't know if it was auto-closed from this context
                )

                buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        except Exception as e:
            force_log(f"Error showing previous shift report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        await event.edit(message, buttons=buttons)

    async def show_other_days_report(self, event):
        """Show other days with shifts (last 3 days with data)"""
        chat_id = int(event.chat_id)

        try:
            recent_dates = await self.shift_service.get_recent_end_dates_with_shifts(
                chat_id, 3
            )
            force_log(f"Found recent dates: {recent_dates}")

            if not recent_dates:
                message = """
📅 របាយការណ៍ថ្ងៃផ្សេង

🔴 គ្មានទិន្នន័យសម្រាប់ថ្ងៃមុនៗ។

💡 ទិន្នន័យនឹងបង្ហាញនៅទីនេះបន្ទាប់ពីមានវេនបានបិទ។
"""
                buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            else:
                message = "📅 របាយការណ៍ថ្ងៃផ្សេង\n\nជ្រើសរើសថ្ងៃដែលអ្នកចង់មើល:"

                buttons = []
                for date in recent_dates:
                    date_str = date.strftime("%Y-%m-%d")
                    display_date = date.strftime("%d %b %Y")
                    buttons.append([(display_date, f"date_{date_str}")])

                buttons.append([("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")])

        except Exception as e:
            force_log(f"Error showing other days report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        await event.edit(message, buttons=buttons)

    async def show_date_shifts(self, event, data):
        """Show all shift reports for a specific date in one response"""
        chat_id = int(event.chat_id)
        date_str = data.replace("date_", "")
        force_log(
            f"show_date_shifts called with data: {data}, date_str: {date_str}, chat_id: {chat_id}"
        )

        try:
            from datetime import datetime
            from helper import shift_report

            selected_date = datetime.strptime(date_str, "%Y-%m-%d")
            parsed_date = selected_date.date()
            force_log(f"Parsed date: {parsed_date}")
            shifts = await self.shift_service.get_shifts_by_end_date(chat_id, parsed_date)
            force_log(f"Found {len(shifts)} shifts for date {parsed_date}")

            if not shifts:
                message = f"""
📅 វេនសម្រាប់ថ្ងៃ {parsed_date.strftime('%d %b %Y')}

🔴 គ្មានវេនសម្រាប់ថ្ងៃនេះ។
"""
            else:
                # Generate reports for all shifts on that date
                reports = []
                for shift in shifts:
                    try:
                        report = await shift_report(shift.id, shift.number, selected_date)
                        reports.append(report)
                    except Exception as e:
                        force_log(f"Error generating report for shift {shift.id}: {e}", "ERROR")
                        reports.append(f"កំហុសក្នុងការបង្កើតរបាយការណ៍វេន {shift.number}")
                
                # Combine all reports
                if len(reports) == 1:
                    message = reports[0]
                else:
                    message = "".join(reports)

            buttons = None

        except Exception as e:
            force_log(f"Error showing date shifts: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        await event.edit(message, buttons=buttons)

    async def show_specific_shift_report(self, event, data):
        """Show report for a specific shift"""
        shift_id = int(data.replace("shift_", ""))
        chat_id = event.chat_id
        try:
            shift = await self.shift_service.get_shift_by_id(shift_id)

            if not shift:
                message = "❌ រកមិនឃើញវេននេះទេ។"
                buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            else:
                shift_summary = await self.shift_service.get_shift_income_summary(
                    shift.id, chat_id
                )

                # Calculate duration
                if shift.end_time:
                    duration = shift.end_time - shift.start_time
                    end_text = shift.end_time.strftime("%Y-%m-%d %I:%M %p")
                    status = "🔴 បានបិទបញ្ជី"
                else:
                    from helper import DateUtils

                    try:
                        now = DateUtils.now()
                        aware_start_time = DateUtils.localize_datetime(shift.start_time)
                        duration = now - aware_start_time
                    except Exception as e:
                        force_log(
                            f"Error calculating duration for active shift: {e}", "ERROR"
                        )
                        # Fallback to naive datetime calculation

                        now = DateUtils.now()
                        duration = now - shift.start_time
                    end_text = "បច្ចុប្បន្ន (វេនកំពុងសកម្ម)"
                    status = "🟢 🟢 កំពុងបន្ត"

                total_seconds = abs(duration.total_seconds())
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)

                # Currency breakdown
                currency_text = ""
                for currency, data in shift_summary["currencies"].items():
                    if currency == "USD":
                        currency_text += f"• {currency}: ${data['amount']:,.2f} ({data['count']} ប្រតិបត្តិការ)\n"
                    elif currency == "KHR":
                        khr_amount = int(data["amount"])
                        currency_text += f"• {currency}: ៛{khr_amount:,} ({data['count']} ប្រតិបត្តិការ)\n"
                    else:
                        currency_text += f"• {currency}: {data['amount']:,.2f} ({data['count']} ប្រតិបត្តិការ)\n"

                message = f"""
📊 របាយការណ៍វេន #{shift.number}

{status}
⏰ ចាប់ផ្តើម: {shift.start_time.strftime('%Y-%m-%d %I:%M %p')}
⏱️ បញ្ចប់: {end_text}
⏲️ រយៈពេល: {hours}ម៉ោង {minutes}នាទី

💰 សង្ខេបចំណូលសរុប:
{currency_text if currency_text else '• មិនទាន់មានប្រតិបត្តិការទេ'}
"""

                buttons = [
                    [("🔙 ត្រឡប់ទៅថ្ងៃផ្សេង", "other_days_report")],
                    [("🏠 ត្រឡប់ទៅមីនុយ", "back_to_menu")],
                ]

        except Exception as e:
            force_log(f"Error showing specific shift report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]

        await event.edit(message, buttons=buttons)

    async def close_current_shift(self, event):
        """Close the current active shift or create new shift if none exists"""
        chat_id = int(event.chat_id)
        current_time = DateUtils.now()
        force_log(f"CLOSE_CURRENT_SHIFT: Called for chat_id: {chat_id} at {current_time}")

        try:
            current_shift = await self.shift_service.get_current_shift(chat_id)
            
            if current_shift:
                force_log(f"CLOSE_CURRENT_SHIFT: Found current shift - id={current_shift.id}, number={current_shift.number}, is_closed={current_shift.is_closed}")

            if not current_shift:
                # No active shift, just create a new one
                new_shift = await self.shift_service.create_shift(chat_id)

                message = f"""
✅ វេនថ្មីត្រូវបានបង្កើតដោយជោគជ័យ!

📊 វេន #{new_shift.number}
⏰ ចាប់ផ្តើម: {new_shift.start_time.strftime('%Y-%m-%d %I:%M %p')}
🟢 ស្ថានភាព: កំពុងបន្ត

💡 ឥឡូវនេះប្រតិបត្តិការថ្មីទាំងអស់នឹងត្រូវបានកត់ត្រាក្នុងវេននេះ។
"""
            else:
                # Close the current shift and create new one
                closed_shift = await self.shift_service.close_shift(current_shift.id)

                if closed_shift:
                    # Automatically create a new shift after closing the current one
                    await self.shift_service.create_shift(chat_id)

                    # Get final summary
                    shift_summary = await self.shift_service.get_shift_income_summary(
                        closed_shift.id, chat_id
                    )
                    duration = closed_shift.end_time - closed_shift.start_time
                    total_seconds = abs(duration.total_seconds())
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)

                    # Use new shift report format for closed shift
                    shift_report = shift_report_format(
                        closed_shift.number,
                        closed_shift.start_time,
                        closed_shift.start_time,
                        closed_shift.end_time,
                        shift_summary,
                        auto_closed=False  # Manual close
                    )
                    
                    message = f"✅ វេនត្រូវបានបិទដោយជោគជ័យ!\n\n{shift_report}"
                else:
                    message = "❌ បរាជ័យក្នុងការបិទវេន។ សូមសាកល្បងម្តងទៀត។"

        except Exception as e:
            force_log(f"Error closing shift: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការបិទវេន។ សូមសាកល្បងម្តងទៀត។"

        await event.edit(message, buttons=None)

    async def close_menu(self, event):
        """Close the menu (delete message)"""
        try:
            await event.query.delete_message()
        except Exception as e:
            force_log(f"Error deleting message: {e}", "ERROR")
            # Fallback to editing the message
            await event.edit("Menu closed.", buttons=None)

    async def show_support(self, event):
        """Show support information"""
        message = """
🆘 ត្រូវការជំនួយ?
• បញ្ហាបច្ចេកទេសជាមួយBot
• សំណួរអំពីលក្ខណៈពិសេសអាជីវកម្ម
• សំណើរបាយការណ៍ផ្ទាល់ខ្លួន

📧 វិធីសាស្រ្តទំនាក់ទំនង:
Telegram: https://t.me/HK_688

⏰ ម៉ោងការគាំទ្រ:
ច័ន្ទ - អាទិត្យ: 9:00 AM - 11:00 PM
"""

        buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
        await event.edit(message, buttons=buttons)

    async def check_auto_close_shift(self, chat_id: int) -> bool:
        """Check if the current shift should be auto-closed and close it if needed"""
        try:
            closed_shift = await self.shift_service.auto_close_shift_for_chat(chat_id)
            if closed_shift:
                force_log(f"Auto-closed shift {closed_shift.id} for chat {chat_id}")
                return True
            return False
        except Exception as e:
            force_log(f"Error checking auto close for chat {chat_id}: {e}", "ERROR")
            return False

    async def configure_auto_close(self, event, times_list: List[str] = None):
        """Configure auto close settings for a chat with multiple times"""
        chat_id = event.chat_id

        try:
            if not times_list:
                message = "❌ សូមផ្តល់បញ្ជីម៉ោងបិទវេន (ឧ. 08:00, 16:00, 23:59)។"
                await event.respond(message)
                return

            # Enable auto close with multiple times
            config = await self.shift_config_service.update_auto_close_settings(
                chat_id=chat_id, enabled=True, auto_close_times=times_list
            )

            # Format the times list for display
            times_display = ", ".join(times_list)

            message = f"""
✅ បានកំណត់បិទវេនដោយស្វ័យប្រវត្តិ!

⏰ វេននឹងត្រូវបានបិទនៅម៉ោង: {times_display}

💡 វេនសកម្មនឹងត្រូវបានបិទដោយស្វ័យប្រវត្តិរាល់ថ្ងៃនច្នៃម៉ោងដែលបានកំណត់។

📝 ឧទាហរណ៍: វេននឹងបិទនៅម៉ោង {times_list[0]} ហើយវេនថ្មីនឹងចាប់ផ្តើមដោយស្វ័យប្រវត្តិ។
"""

        except Exception as e:
            force_log(f"Error configuring auto close: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការកំណត់ការបិទដោយស្វ័យប្រវត្តិ។"

        await event.respond(message)

    async def disable_auto_close(self, event):
        """Disable auto close for a chat"""
        chat_id = event.chat_id

        try:
            await self.shift_config_service.update_auto_close_settings(
                chat_id=chat_id, enabled=False
            )

            message = """
✅ បានបិទការបិទវេនដោយស្វ័យប្រវត្តិ!

💡 ឥឡូវនេះអ្នកត្រូវបិទវេនដោយដៃតែម្តង។
"""
        except Exception as e:
            force_log(f"Error disabling auto close: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការបិទការកំណត់ស្វ័យប្រវត្តិ។"

        await event.respond(message)

    async def show_auto_close_status(self, event):
        """Show current auto close configuration for a chat"""
        chat_id = event.chat_id

        try:
            config = await self.shift_config_service.get_configuration(chat_id)

            if not config or not config.auto_close_enabled:
                message = """
📊 ស្ថានភាពការបិទវេនស្វ័យប្រវត្តិ

🔴 មិនបានបើក

💡 ប្រើ /autoclose <times> ដើម្បីបើក
ឧទាហរណ៍: /autoclose 08:00,16:00,23:59
"""
            else:
                auto_close_times = config.get_auto_close_times_list()
                if auto_close_times:
                    times_display = ", ".join(auto_close_times)
                    settings_text = f"⏰ បិទនៅម៉ោង: {times_display}"
                else:
                    settings_text = "គ្មានការកំណត់ម៉ោងបិទ"

                message = f"""
📊 ស្ថានភាពការបិទវេនស្វ័យប្រវត្តិ

🟢 បានបើក

{settings_text}

💡 ប្រើ /autoclose off ដើម្បីបិទ
"""
        except Exception as e:
            force_log(f"Error showing auto close status: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយកស្ថានភាពការកំណត់។"

        await event.respond(message)

    async def show_weekly_reports(self, event):
        """Show weekly report options for current month"""
        try:
            from datetime import datetime
            from calendar import monthrange
            
            now = DateUtils.now()
            current_month = now.month
            current_year = now.year
            
            # Get the number of days in current month
            _, days_in_month = monthrange(current_year, current_month)
            
            message = f"📆 របាយការណ៍ប្រចាំសប្តាហ៍ - {now.strftime('%B %Y')}\n\nជ្រើសរើសសប្តាហ៍:"
            
            buttons = []
            
            # Week 1: 1-7
            week1_end = min(7, days_in_month)
            buttons.append([(f"សប្តាហ៍ 1 (1-{week1_end})", f"week_{current_year}-{current_month:02d}-1")])
            
            # Week 2: 8-14
            if days_in_month >= 8:
                week2_end = min(14, days_in_month)
                buttons.append([(f"សប្តាហ៍ 2 (8-{week2_end})", f"week_{current_year}-{current_month:02d}-2")])
            
            # Week 3: 15-21
            if days_in_month >= 15:
                week3_end = min(21, days_in_month)
                buttons.append([(f"សប្តាហ៍ 3 (15-{week3_end})", f"week_{current_year}-{current_month:02d}-3")])
            
            # Week 4: 22-end of month
            if days_in_month >= 22:
                buttons.append([(f"សប្តាហ៍ 4 (22-{days_in_month})", f"week_{current_year}-{current_month:02d}-4")])
            
            buttons.append([("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")])
            
            await event.edit(message, buttons=buttons)
            
        except Exception as e:
            force_log(f"Error showing weekly reports: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            await event.edit(message, buttons=buttons)

    async def show_monthly_reports(self, event):
        """Show monthly report options"""
        try:
            from datetime import datetime
            
            now = DateUtils.now()
            current_year = now.year
            
            message = f"📊 របាយការណ៍ប្រចាំខែ - {current_year}\n\nជ្រើសរើសខែ:"
            
            buttons = []
            
            # Show months in two columns like the main bot
            for month in range(1, 13, 2):
                month_date_1 = datetime(current_year, month, 1)
                label_1 = month_date_1.strftime("%B %Y")
                callback_value_1 = month_date_1.strftime("%Y-%m")
                
                row = [(label_1, f"month_{callback_value_1}")]
                
                if month + 1 <= 12:
                    month_date_2 = datetime(current_year, month + 1, 1)
                    label_2 = month_date_2.strftime("%B %Y")
                    callback_value_2 = month_date_2.strftime("%Y-%m")
                    row.append((label_2, f"month_{callback_value_2}"))
                
                buttons.append(row)
            
            buttons.append([("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")])
            
            await event.edit(message, buttons=buttons)
            
        except Exception as e:
            force_log(f"Error showing monthly reports: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            await event.edit(message, buttons=buttons)

    async def show_weekly_report(self, event, data):
        """Show report for a specific week"""
        chat_id = int(event.chat_id)
        week_data = data.replace("week_", "")
        
        try:
            from datetime import datetime
            from calendar import monthrange
            
            # Parse week data: YYYY-MM-W (e.g., "2024-02-1")
            parts = week_data.split("-")
            year = int(parts[0])
            month = int(parts[1])
            week_number = int(parts[2])
            
            # Calculate week date range
            _, days_in_month = monthrange(year, month)
            
            if week_number == 1:
                start_day = 1
                end_day = min(7, days_in_month)
            elif week_number == 2:
                start_day = 8
                end_day = min(14, days_in_month)
            elif week_number == 3:
                start_day = 15
                end_day = min(21, days_in_month)
            elif week_number == 4:
                start_day = 22
                end_day = days_in_month
            else:
                raise ValueError("Invalid week number")
            
            start_date = datetime(year, month, start_day)
            end_date = datetime(year, month, end_day, 23, 59, 59)
            
            # Get income data for the week
            incomes = await self.income_service.get_income_by_date_and_chat_id(
                chat_id=chat_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not incomes:
                message = f"""
📆 របាយការណ៍សប្តាហ៍ {week_number} ({start_day}-{end_day} {start_date.strftime('%B %Y')})

🔴 គ្មានប្រតិបត្តិការសម្រាប់សប្តាហ៍នេះទេ។
"""
            else:
                # Use weekly report format similar to telegram bot service
                from helper import weekly_transaction_report
                message = weekly_transaction_report(incomes, start_date, end_date)
            
            await event.delete()
            await event.respond(message, parse_mode='HTML')
            
        except Exception as e:
            force_log(f"Error showing weekly report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            await event.edit(message, buttons=buttons)

    async def show_monthly_report(self, event, data):
        """Show report for a specific month"""
        chat_id = int(event.chat_id)
        month_data = data.replace("month_", "")
        
        try:
            from datetime import datetime
            from calendar import monthrange
            
            # Parse month data: YYYY-MM (e.g., "2024-02")
            start_date = datetime.strptime(month_data, "%Y-%m")
            
            # Get last day of month
            _, last_day = monthrange(start_date.year, start_date.month)
            end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)
            
            # Get income data for the month
            incomes = await self.income_service.get_income_by_date_and_chat_id(
                chat_id=chat_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not incomes:
                period_text = start_date.strftime("%B %Y")
                message = f"គ្មានប្រតិបត្តិការសម្រាប់ {period_text} ទេ។"
            else:
                # Use monthly report format similar to telegram bot service
                from helper import monthly_transaction_report
                message = monthly_transaction_report(incomes, start_date, end_date)
            
            await event.delete()
            await event.respond(message, parse_mode='HTML')
            
        except Exception as e:
            force_log(f"Error showing monthly report: {e}", "ERROR")
            message = "❌ មានបញ្ហាក្នុងការទាញយករបាយការណ៍។ សូមសាកល្បងម្តងទៀត។"
            buttons = [[("🔙 ត្រឡប់ទៅមីនុយ", "back_to_menu")]]
            await event.edit(message, buttons=buttons)
