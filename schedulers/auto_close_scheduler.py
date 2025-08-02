import asyncio

from helper.logger_utils import force_log
from services import ShiftService
from services.telegram_business_bot_service import AutosumBusinessBot


class AutoCloseScheduler:
    """Dedicated scheduler for auto-closing shifts that runs every minute"""

    def __init__(self, bot_service: AutosumBusinessBot):
        self.shift_service = ShiftService()
        self.bot_service = bot_service
        self.is_running = False

    async def start_scheduler(self):
        """Start the auto-close scheduler to run every minute"""
        self.is_running = True
        force_log("Auto-close scheduler started - will run every minute")

        while self.is_running:
            try:
                await self.check_auto_close_shifts()
                # Wait 1 minute (60 seconds) before next run
                await asyncio.sleep(60)
            except Exception as e:
                force_log(f"Error in auto-close scheduler loop: {e}")
                # Wait 1 minute before retrying if there's an error
                await asyncio.sleep(60)

    async def stop_scheduler(self):
        """Stop the auto-close scheduler"""
        self.is_running = False
        force_log("Auto-close scheduler stopped")

    async def check_auto_close_shifts(self):
        """Check and auto-close shifts based on configuration"""
        force_log("Starting auto-close shift check...")

        try:
            # Use the existing method from ShiftService to check and auto-close all shifts
            closed_shifts = await self.shift_service.check_and_auto_close_shifts()

            if closed_shifts:
                force_log(
                    f"Auto-closed {len(closed_shifts)} shifts: {[shift['id'] for shift in closed_shifts]}"
                )

                # Send shift summaries to chats
                for shift in closed_shifts:
                    force_log(
                        f"Auto-closed shift {shift['id']} for chat {shift['chat_id']}"
                    )

                    # Send shift summary to chat if bot service is available
                    if self.bot_service:
                        await self._send_shift_summary(shift)
            else:
                force_log("No shifts needed auto-closing")

        except Exception as e:
            force_log(f"Error in auto-close shift check: {e}")
            import traceback

            force_log(f"Traceback: {traceback.format_exc()}")

    async def _send_shift_summary(self, shift_info: dict):
        """Send shift summary to the chat"""
        try:
            chat_id = shift_info["chat_id"]
            shift_id = shift_info["id"]
            shift_number = shift_info["number"]

            # Get shift details for timing information
            shift = await self.shift_service.get_shift_by_id(shift_id)
            
            # Get shift summary
            summary = await self.shift_service.get_shift_income_summary(
                shift_id, chat_id
            )

            # Format the summary message
            if summary["transaction_count"] > 0:
                # Format currency breakdown
                currency_details = []
                for currency, data in summary['currencies'].items():
                    if currency == 'USD':
                        currency_details.append(f"• {currency}: ${data['amount']:,.2f} ({data['count']} ប្រតិបត្តិការ)")
                    elif currency == 'KHR':
                        khr_amount = int(data['amount'])
                        currency_details.append(f"• {currency}: ៛{khr_amount:,} ({data['count']} ប្រតិបត្តិការ)")
                    else:
                        currency_details.append(f"• {currency}: {data['amount']:,.2f} ({data['count']} ប្រតិបត្តិការ)")
                
                currency_text = "\n".join(currency_details)

                message = f"""
🔒 វេន #{shift_number} បានបិទដោយស្វ័យប្រវត្តិ

📊 សរុបចំណូល:
{currency_text}

📝 ព័ត៌មានលម្អិត:
• ពេលចាប់ផ្តើមវេន: {shift.start_time.strftime('%I:%M:%S %p')}
• ពេលបញ្ចប់វេន: {shift.end_time.strftime('%I:%M:%S %p')}

⚡ បិទដោយ: ការកំណត់ពេលវេលាស្វ័យប្រវត្តិ
                """.strip()
            else:
                message = f"""
🔒 វេន #{shift_number} បានបិទដោយស្វ័យប្រវត្តិ

📊 សរុបចំណូល:
• មិនមានប្រតិបត្តិការ

📝 ព័ត៌មានលម្អិត:
• ពេលចាប់ផ្តើមវេន: {shift.start_time.strftime('%I:%M:%S %p')}
• ពេលបញ្ចប់វេន: {shift.end_time.strftime('%I:%M:%S %p')}

⚡ បិទដោយ: ការកំណត់ពេលវេលាស្វ័យប្រវត្តិ
                """.strip()

            # Send message
            success = await self.bot_service.send_message(chat_id, message)
            if success:
                force_log(f"Sent shift summary for shift {shift_id} to chat {chat_id}")
            else:
                force_log(
                    f"Failed to send shift summary for shift {shift_id} to chat {chat_id}"
                )

        except Exception as e:
            force_log(
                f"Error sending shift summary for shift {shift_info.get('id', 'unknown')}: {e}"
            )
            import traceback

            force_log(f"Shift summary error traceback: {traceback.format_exc()}")
