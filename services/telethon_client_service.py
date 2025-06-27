from datetime import date, datetime, timedelta, timezone, time
from typing import List, Set
from alembic.op import f
from telethon import TelegramClient, events

from helper import extract_amount_and_currency, extract_trx_id
from helper.total_summary_report_helper import total_summary_report
from models import ChatService, IncomeService
from models.income_balance import CurrencyEnum, IncomeBalance


class TelethonClientService:
    def __init__(self):
        self.client = None
        self.service = IncomeService()

    async def start(self, username, api_id, api_hash):
        self.client = TelegramClient(username, int(api_id), api_hash)
        await self.client.connect()
        await self.client.start(phone=loader.phone_number)  # type: ignore
        await self.client.start(phone=username)  # type: ignore
        print("Account " + username + " started...")

        chat_service = ChatService()

        @self.client.on(events.NewMessage(pattern="/verify"))
        async def _verify_current_date_report(event):
            chat = event.chat_id
            today = datetime.now(timezone.utc).date()
            yesterday = today - timedelta(days=1)
            start_of_yesterday = datetime.combine(
                yesterday, time.min, tzinfo=timezone.utc
            )

            last_msg = await self.service.get_last_yesterday_message(start_of_yesterday)
            min_id = int(getattr(last_msg, "message_id", 0)) if last_msg else 0

            incomes = []
            processed_ids = set()

            async for msg in self.client.iter_messages(  # type: ignore
                chat, search="paid by", min_id=min_id
            ):
                if not (msg.text and msg.date) or msg.id in processed_ids:
                    continue

                currency, amount = extract_amount_and_currency(msg.text)
                trx_id = extract_trx_id(msg.text)
                processed_ids.add(msg.id)

                if not (currency and amount):
                    continue

                currency_code = next(
                    (c.name for c in CurrencyEnum if c.value == currency), None
                )
                if not currency_code:
                    continue

                try:
                    amount_value = float(str(amount).replace(",", "").replace(" ", ""))
                except Exception:
                    continue

                incomes.append(
                    IncomeBalance(
                        amount=amount_value,
                        chat_id=chat,
                        currency=currency_code,
                        original_amount=amount_value,
                        income_date=msg.date,
                        message_id=msg.id,
                        message=msg.text,
                        trx_id=trx_id,
                    )
                )

            summary = total_summary_report(incomes, "របាយការណ៍សរុបប្រចាំថ្ងៃនេះ")
            await event.client.send_message(chat, summary)

        @self.client.on(events.NewMessage)  # type: ignore
        async def _new_message_listener(event):
            chat_ids = chat_service.get_all_chat_ids()
            if event.chat_id not in chat_ids:
                return

            currency, amount = extract_amount_and_currency(event.message.text)
            message_id: int = event.message.id
            trx_id = extract_trx_id(event.message.text)

            if await self.service.get_income_by_message_id(
                message_id
            ) and await self.service.get_income_by_trx_id(trx_id):
                return

            if currency and amount and trx_id:
                await self.service.insert_income(
                    event.chat_id,
                    amount,
                    currency,
                    amount,
                    message_id,
                    event.message.text,
                    trx_id,
                )

        await self.client.run_until_disconnected()  # type: ignore
