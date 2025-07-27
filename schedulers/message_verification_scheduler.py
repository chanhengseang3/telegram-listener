import asyncio
import datetime
from datetime import timedelta
from typing import List

import pytz
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import Message

from helper import extract_amount_and_currency, extract_trx_id
from helper.logger_utils import force_log
from services import ChatService, IncomeService, ShiftService


class MessageVerificationScheduler:
    def __init__(self, telethon_client: TelegramClient):
        self.client = telethon_client
        self.chat_service = ChatService()
        self.income_service = IncomeService()
        self.shift_service = ShiftService()
        self.is_running = False

    async def start_scheduler(self):
        """Start the scheduler to run every 10 minutes"""
        self.is_running = True
        force_log("Message verification scheduler started - will run every 10 minutes")

        while self.is_running:
            try:
                await self.verify_messages()
                # Wait 10 minutes (600 seconds) before next run
                await asyncio.sleep(600)
            except Exception as e:
                force_log(f"Error in scheduler loop: {e}")
                # Wait 1 minute before retrying if there's an error
                await asyncio.sleep(60)

    async def stop_scheduler(self):
        """Stop the scheduler"""
        self.is_running = False
        force_log("Message verification scheduler stopped")

    async def verify_messages(self):
        """Main verification method that reads messages from last 20 minutes"""
        force_log("Starting message verification job...")

        try:
            # Get all chat IDs from database (excluding FREE package chats)
            chat_ids = await self.chat_service.get_all_active_chat_ids_excluding_free()
            force_log(f"Found {len(chat_ids)} non-free chats to verify")

            # Calculate time range (last 30 minutes)
            now = datetime.datetime.now(pytz.UTC)
            thirty_minutes_ago = now - datetime.timedelta(minutes=30)
            force_log(f"Checking messages from {thirty_minutes_ago} to {now}")

            verification_count = 0
            new_messages_found = 0

            for i, chat_id in enumerate(chat_ids):
                try:
                    # Get chat info to check if it's active
                    chat = await self.chat_service.get_chat_by_chat_id(chat_id)
                    if not chat or not chat.is_active:
                        force_log(f"Skipping inactive chat {chat_id}")
                        continue

                    force_log(
                        f"Verifying messages for chat {chat_id} ({chat.group_name})"
                    )

                    # Read messages from the chat within the time range
                    messages = await self._get_bot_messages_in_timeframe(
                        chat_id, thirty_minutes_ago, now
                    )

                    verification_count += len(messages)

                    for message in messages:
                        await self._verify_and_store_message(chat, message)
                        new_messages_found += 1

                    # Rate limiting: Add delay between chats to prevent Telegram API rate limits
                    # 200ms delay between chats, longer delay every 20 chats
                    if i < len(chat_ids) - 1:  # Don't delay after the last chat
                        if (i + 1) % 20 == 0:
                            force_log(
                                f"Processed {i + 1} chats, taking longer break to prevent rate limits..."
                            )
                            await asyncio.sleep(2)  # 2 seconds break every 20 chats
                        else:
                            await asyncio.sleep(0.2)  # 200ms between each chat

                except Exception as chat_error:
                    force_log(f"Error processing chat {chat_id}: {chat_error}")
                    continue

            force_log(
                f"Verification job completed. Checked {verification_count} messages, processed {new_messages_found} new messages"
            )

        except Exception as e:
            force_log(f"Error in verify_messages: {e}")
            import traceback

            force_log(f"Traceback: {traceback.format_exc()}")

    async def _get_bot_messages_in_timeframe(
        self, chat_id: int, start_time: datetime.datetime, end_time: datetime.datetime
    ) -> List[Message]:
        """Get bot messages from a specific chat within the given timeframe"""
        messages = []

        try:
            # Get messages from the chat starting from 30 minutes ago
            all_messages = await self.client.get_messages(
                chat_id, offset_date=start_time, reverse=True, limit=100, wait_time=0.5
            )
            force_log(f"Found {len(all_messages)} messages from {chat_id}")

            for message in all_messages:
                # Check if message is within our time range
                message_time = message.date
                if message_time.tzinfo is None:
                    message_time = pytz.UTC.localize(message_time)

                if message_time < start_time:
                    # We've gone too far back in time
                    break

                if start_time <= message_time <= end_time:
                    # Check if message is from a bot
                    sender = await message.get_sender()
                    is_bot = getattr(sender, "bot", False)

                    if is_bot and message.text:

                        username = getattr(sender, "username", "")

                        lowercase_username = username.lower()
                        if "salmon" in lowercase_username or "report" in lowercase_username or "kambaul" in lowercase_username:
                            force_log(
                                f"Message from user with 'salmon/report/kambaul' in username ({username}), ignoring")
                            continue

                        if username != "AutosumBusinessBot" and username != "AutoSum_bot":
                            messages.append(message)
                            force_log(
                                f"Found bot message in timeframe: {message.id} from {message_time}"
                            )
        except FloodWaitError as e:
            force_log(f"FloodWaitError for chat {chat_id}: waiting {e.seconds} seconds")
            await asyncio.sleep(e.seconds + 1)
            # Recursively retry after waiting
            return await self._get_bot_messages_in_timeframe(
                chat_id, start_time, end_time
            )
        except RPCError as e:
            force_log(f"RPCError for chat {chat_id}: {e}")
            force_log(
                f"Chat {chat_id} appears to be inaccessible or deactivated, marking as inactive"
            )
            try:
                # Mark the chat as inactive in the database
                await self.chat_service.update_chat_status(chat_id, False)
                force_log(f"Successfully marked chat {chat_id} as inactive")
            except Exception as db_error:
                force_log(f"Failed to mark chat {chat_id} as inactive: {db_error}")
        except Exception as e:
            force_log(f"General error getting messages for chat {chat_id}: {e}")

            # Fallback string check for other exception types
            error_msg = str(e)
            if "Could not find the input entity" in error_msg:
                force_log(
                    f"Chat {chat_id} entity not found (fallback detection), marking as inactive"
                )
                try:
                    await self.chat_service.update_chat_status(chat_id, False)
                    force_log(f"Successfully marked chat {chat_id} as inactive")
                except Exception as db_error:
                    force_log(f"Failed to mark chat {chat_id} as inactive: {db_error}")

        return messages

    async def _verify_and_store_message(self, chat, message: Message):
        """Verify if message exists in database, if not then store it"""
        try:
            chat_id = message.chat_id or chat.chat_id
            message_id = message.id
            message_text = message.text

            force_log(f"Verifying message {message_id} from chat {chat_id}")

            # Check message timestamp vs chat registration
            message_time = message.date
            if message_time.tzinfo is None:
                message_time = pytz.UTC.localize(message_time)

            # Convert chat created_at to UTC for comparison
            from helper import DateUtils

            chat_created = chat.created_at
            if chat_created.tzinfo is None:
                chat_created = DateUtils.localize_datetime(chat_created)
            chat_created_utc = chat_created.astimezone(pytz.UTC)

            # Add a 5-minute buffer to handle any timestamp precision issues
            chat_created_with_buffer = chat_created_utc - timedelta(minutes=5)

            if message_time < chat_created_with_buffer:
                force_log(
                    f"Message {message_id} timestamp {message_time} is before chat registration buffer {chat_created_with_buffer}, skipping"
                )
                return

            # Check if this message already exists in database (using both chat_id and message_id)
            exists = await self.income_service.get_income_by_chat_and_message_id(
                chat_id, message_id
            )
            if exists:
                force_log(
                    f"Message {message_id} from chat {chat_id} already exists in database, skipping"
                )
                return

            # Extract currency and amount from message
            currency, amount = extract_amount_and_currency(message_text)
            if not (currency and amount):
                force_log(
                    f"No valid currency/amount found in message {message_id}, skipping"
                )
                return

            # Extract transaction ID
            trx_id = extract_trx_id(message_text)

            force_log(
                f"Processing new message {message_id}: currency={currency}, amount={amount}, trx_id={trx_id}"
            )

            # Check for duplicates using comprehensive check
            # Not check for now, suppose chat_id + message_id is unique
            # is_duplicate = await self.income_service.check_duplicate_transaction(
            #     chat_id, trx_id, message_id
            # )
            # if is_duplicate:
            #     force_log(f"Duplicate transaction found for message {message_id}, skipping")
            #     return

            # Get sender username
            sender = await message.get_sender()
            username = getattr(sender, "username", "") or ""
            
            # Store the message as income
            force_log(f"Storing income for message {message_id}")
            result = await self.income_service.insert_income(
                chat_id,
                amount,
                currency,
                amount,  # original_amount
                message_id,
                message_text,
                trx_id,
                None,  # shift_id
                chat.enable_shift,  # enable_shift
                username,  # sent_by
            )

            force_log(
                f"Successfully stored income record with id={result.id} for message {message_id}"
            )

        except Exception as e:
            force_log(f"Error verifying/storing message {message.id}: {e}")
            import traceback

            force_log(f"Traceback: {traceback.format_exc()}")
