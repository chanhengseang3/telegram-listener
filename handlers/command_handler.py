import json
from calendar import monthrange
from datetime import datetime, timedelta

from telethon import Button

from models import ConversationService, IncomeService, CurrencyEnum
from telethon import Button
from helper import total_summary_report


class CommandHandler:
    @staticmethod
    def format_totals_message(period_text: str, incomes):
        title = f"សរុបប្រតិបត្តិការ {period_text}"
        return total_summary_report(incomes, title)

    async def handle_date_input_response(self, event, question):
        try:
            day_str = event.message.text.strip()
            day = int(day_str)

            if day < 1 or day > 31:
                await event.respond("ថ្ងៃមិនត្រឹមត្រូវ។ សូមជ្រើសរើសថ្ងៃពី 1 ដល់ 31។")
                return

            conversation_service = ConversationService()
            context_data = {}
            if question.context_data:
                context_data = json.loads(question.context_data)

            current_month = context_data.get(
                "current_month", datetime.now().strftime("%Y-%m")
            )
            date_str = f"{current_month}-{day:02d}"

            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d")
                await conversation_service.mark_as_replied(
                    chat_id=event.chat_id, message_id=question.message_id
                )

                income_service = IncomeService()
                incomes = await income_service.get_income_by_date_and_chat_id(
                    chat_id=event.chat_id,
                    start_date=selected_date,
                    end_date=selected_date + timedelta(days=1),
                )

                await event.delete()
                if not incomes:
                    await event.respond(
                        f"គ្មានប្រតិបត្តិការសម្រាប់ថ្ងៃទី {selected_date.strftime('%d %b %Y')} ទេ។"
                    )
                    return

                message = self.format_totals_message(
                    f"ថ្ងៃទី {selected_date.strftime('%d %b %Y')}", incomes
                )
                await event.client.send_message(event.chat_id, message)

            except ValueError:
                await event.respond("ទម្រង់កាលបរិច្ឆេទមិនត្រឹមត្រូវ")

        except ValueError:
            await event.respond("សូមវាយថ្ងៃជាលេខពី 1 ដល់ 31")
        except Exception as e:
            print(f"Error in handle_date_input_response: {e}")
            await event.respond("មានបញ្ហាក្នុងការដំណើរការសំណើរបស់អ្នក។ សូមព្យាយាមម្តងទៀត។")

    async def handle_daily_summary(self, event):
        today = datetime.now()
        buttons = []

        for i in range(2, -1, -1):
            day = today - timedelta(days=i)
            label = day.strftime("%b %d")
            callback_value = day.strftime("%Y-%m-%d")
            buttons.append([Button.inline(label, f"summary_of_{callback_value}")])

        buttons.append([Button.inline("ថ្ងៃផ្សេងទៀត", "other_dates")])
        buttons.append([Button.inline("ត្រឡប់ក្រោយ", "menu")])

        await event.edit("ឆែករបាយការណ៍ថ្ងៃ:", buttons=buttons)

    async def handle_weekly_summary(self, event):
        now = datetime.now()
        year, month = now.year, now.month

        first_day = datetime(year, month, 1)
        days_to_monday = (first_day.weekday() - 0) % 7
        first_monday = first_day - timedelta(days=days_to_monday)

        _, last_day = monthrange(year, month)
        last_date = datetime(year, month, last_day)

        buttons = []
        current_monday = first_monday

        while current_monday <= last_date:
            sunday = current_monday + timedelta(days=6)
            if current_monday.month != sunday.month:
                label = f"{current_monday.strftime('%d %b')} - {sunday.strftime('%d %b %Y')}"
            else:
                label = (
                    f"{current_monday.strftime('%d')} - {sunday.strftime('%d %b %Y')}"
                )

            callback_value = current_monday.strftime("%Y-%m-%d")
            buttons.append([Button.inline(label, f"summary_week_{callback_value}")])

            current_monday += timedelta(days=7)

        buttons.append([Button.inline("ត្រឡប់ក្រោយ", "menu")])
        await event.edit("ជ្រើសរើសសប្តាហ៍:", buttons=buttons)

    async def handle_monthly_summary(self, event):
        now = datetime.now()
        year = now.year
        buttons = []

        for month in range(1, 13):
            month_date = datetime(year, month, 1)
            label = month_date.strftime("%B %Y")
            callback_value = month_date.strftime("%Y-%m")
            buttons.append([Button.inline(label, f"summary_month_{callback_value}")])

        buttons.append([Button.inline("ត្រឡប់ក្រោយ", "menu")])
        await event.edit("ជ្រើសរើសខែ:", buttons=buttons)

    async def handle_other_dates(self, event):
        chat_id = event.chat_id

        result = await event.client.send_message(
            chat_id,
            "ឆែករបាយការណ៍ថ្ងៃទី:\n\nសូមវាយថ្ងៃ (1-31) ជាការឆ្លើយតបសារនេះដោយប្រើប៊ូតុង 'Reply' ឬ 'ឆ្លើយតប'",
        )

        conversation_service = ConversationService()
        current_month = datetime.now().strftime("%Y-%m")
        context_data = json.dumps({"current_month": current_month})
        await conversation_service.save_question(
            chat_id=chat_id,
            message_id=result.id,
            question_type="date_input",
            context_data=context_data,
        )
        await event.delete()

    async def handle_date_summary(self, event, data):
        chat_id = event.chat_id
        date_str = data.replace("summary_of_", "")

        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d")
            income_service = IncomeService()
            incomes = await income_service.get_income_by_date_and_chat_id(
                chat_id=chat_id,
                start_date=selected_date,
                end_date=selected_date + timedelta(days=1),
            )

            await event.answer(
                f"Fetching data for {selected_date.strftime('%d %b %Y')}"
            )
            await event.delete()
            if not incomes:
                await event.client.send_message(
                    chat_id,
                    f"គ្មានប្រតិបត្តិការសម្រាប់ថ្ងៃទី {selected_date.strftime('%d %b %Y')} ទេ។",
                )
                return

            message = self.format_totals_message(
                f"ថ្ងៃទី {selected_date.strftime('%d %b %Y')}", incomes
            )
            await event.client.send_message(chat_id, message)

        except ValueError:
            await event.client.send_message(chat_id, "ទម្រង់កាលបរិច្ឆេទមិនត្រឹមត្រូវ")

    async def handle_period_summary(self, event, data):
        chat_id = event.chat_id

        try:
            if data.startswith("summary_week_"):
                start_date = datetime.strptime(
                    data.replace("summary_week_", ""), "%Y-%m-%d"
                )
                end_date = start_date + timedelta(days=7)
                period_text = f"{start_date.strftime('%d')} - {(end_date - timedelta(days=1)).strftime('%d %b %Y')}"
            elif data.startswith("summary_month_"):
                start_date = datetime.strptime(
                    data.replace("summary_month_", ""), "%Y-%m"
                )
                from calendar import monthrange

                _, last_day = monthrange(start_date.year, start_date.month)
                end_date = start_date.replace(day=last_day) + timedelta(days=1)
                period_text = start_date.strftime("%B %Y")
            else:
                raise ValueError("Invalid period format")

            await event.answer(f"Fetching data for {period_text}")

            await event.delete()
            income_service = IncomeService()
            incomes = await income_service.get_income_by_date_and_chat_id(
                chat_id=chat_id, start_date=start_date, end_date=end_date
            )

            if not incomes:
                await event.client.send_message(
                    chat_id, f"គ្មានប្រតិបត្តិការសម្រាប់ {period_text} ទេ។"
                )
                return

            message = self.format_totals_message(period_text, incomes)
            await event.client.send_message(chat_id, message)

        except ValueError:
            await event.client.send_message(chat_id, "ទម្រង់កាលបរិច្ឆេទមិនត្រឹមត្រូវ")
