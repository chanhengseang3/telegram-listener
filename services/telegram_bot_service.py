import asyncio
import os

from telethon import TelegramClient, events
from handlers import EventHandler


class TelegramBotService:
    def __init__(self):
        self.bot: TelegramClient = None  # type: ignore
        self.event_handler = EventHandler()

    async def start(self, bot_token: str):
        self.bot = TelegramClient(
            "bot", int(os.getenv("API_ID")), os.getenv("API_HASH")  # type: ignore
        )  # type: ignore
        await self.bot.start(bot_token=bot_token)  # type: ignore
        self._register_event_handlers()

        try:
            print("Bot is running...")
            await self.bot.run_until_disconnected()  # type: ignore
        except asyncio.CancelledError:
            await self.bot.disconnect()  # type: ignore
            print("Bot stopped by user")

    def _register_event_handlers(self):
        @self.bot.on(events.NewMessage(pattern="/menu"))
        async def menu_handler(event):
            await self.event_handler.menu(event)

        # Register command handler
        @self.bot.on(events.NewMessage(pattern="/register"))
        async def register_handler(event):
            await self.event_handler.register(event)

        # Callback query handler
        @self.bot.on(events.CallbackQuery())
        async def callback_handler(event):
            await self.event_handler.callback(event)

        # Message handler
        @self.bot.on(events.NewMessage())
        async def message_handler(event):
            await self.event_handler.message(event)
