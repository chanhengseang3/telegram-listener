import asyncio
import logging
import signal
from typing import Set

from alembic import command
from alembic.config import Config

from config import load_environment
from helper.credential_loader import CredentialLoader
from schedulers import AutoCloseScheduler
from schedulers.trial_expiry_scheduler import TrialExpiryScheduler
from services.telegram_admin_bot_service import TelegramAdminBot
from services.telegram_business_bot_service import AutosumBusinessBot
from services.telegram_private_bot_service import TelegramPrivateBot
from services.telegram_standard_bot_service import TelegramBotService
from services.telethon_client_service import TelethonClientService

load_environment()


# Configure logging first, before any services are imported
# Custom handler that ensures logs are written to file immediately
class ForceFileHandler(logging.FileHandler):
    """Custom handler that ensures logs are written to file immediately"""

    def emit(self, record):
        super().emit(record)
        self.flush()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[ForceFileHandler("telegram_bot.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

tasks: Set[asyncio.Task] = set()


def handle_signals(loop: asyncio.AbstractEventLoop) -> None:
    """
    Handle signal of event loop
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(loop)))


async def shutdown(loop: asyncio.AbstractEventLoop) -> None:
    """
    Handle shut down of event loop
    """
    tasks_to_cancel = [t for t in tasks if not t.done()]
    if tasks_to_cancel:
        for task in tasks_to_cancel:
            task.cancel()
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

    loop.stop()


async def main(loader: CredentialLoader) -> None:
    """
    Main function
    """
    try:
        telegram_bot_service = TelegramBotService()
        telethon_client_service = TelethonClientService()
        admin_bot = TelegramAdminBot(loader.admin_bot_token)
        business_bot = AutosumBusinessBot(loader.autosum_business_bot_token)
        private_bot = TelegramPrivateBot(loader.private_chat_bot_token)
        auto_close_scheduler = AutoCloseScheduler(bot_service=business_bot)
        trial_expiry_scheduler = TrialExpiryScheduler()

        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        loop = asyncio.get_running_loop()
        handle_signals(loop)

        # # Set telethon client reference in admin bot for username lookup
        # admin_bot.set_telethon_client(telethon_client_service)
        
        # Start all services
        service_tasks = [
            asyncio.create_task(telegram_bot_service.start(loader.bot_token)),
            asyncio.create_task(
                telethon_client_service.start(
                    loader.phone_number1, loader.api_id1, loader.api_hash1
                )
            ),
            asyncio.create_task(admin_bot.start_polling()),
            asyncio.create_task(auto_close_scheduler.start_scheduler()),
            asyncio.create_task(trial_expiry_scheduler.start_scheduler()),
        ]

        # Add business bot only if token is provided
        if loader.autosum_business_bot_token:
            logger.info("Starting business bot...")
            service_tasks.append(asyncio.create_task(business_bot.start_polling()))
        else:
            logger.warning("Business bot token not provided, skipping business bot")

        # Add private bot only if token is provided
        if loader.private_chat_bot_token:
            logger.info("Starting private bot...")
            service_tasks.append(asyncio.create_task(private_bot.start_polling()))
        else:
            logger.warning("Private bot token not provided, skipping private bot")

        tasks.update(service_tasks)
        await asyncio.gather(*service_tasks)

    except Exception as e:
        print(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    try:
        loader = CredentialLoader()
        loader.load_credentials()
        asyncio.run(main(loader))

    except KeyboardInterrupt:
        print("\nBot stopped by user")
