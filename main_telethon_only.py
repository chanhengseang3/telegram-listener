import asyncio
import logging
import signal
from typing import Set

from alembic import command
from alembic.config import Config

from config import load_environment
from helper.credential_loader import CredentialLoader
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
    handlers=[ForceFileHandler("telethon_client.log"), logging.StreamHandler()],
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
    Main function for telethon client only
    """
    try:
        logger.info("Starting Telethon Client Only Mode...")
        telethon_client_service = TelethonClientService()

        # Run database migrations
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        loop = asyncio.get_running_loop()
        handle_signals(loop)

        # Support multiple phone numbers from environment variables
        phone_configs = []
        
        # Check for multiple phone number configurations
        for i in range(1, 10):  # Support up to 9 phone numbers
            api_id = getattr(loader, f'api_id{i}', None)
            api_hash = getattr(loader, f'api_hash{i}', None)
            phone_number = getattr(loader, f'phone_number{i}', None)
            
            if api_id and api_hash and phone_number:
                phone_configs.append({
                    'phone': phone_number,
                    'api_id': api_id,
                    'api_hash': api_hash
                })
                logger.info(f"Found configuration for phone number {i}: {phone_number}")

        if not phone_configs:
            raise ValueError("No phone number configurations found")

        # Start telethon clients for all configured phone numbers
        service_tasks = []
        
        for i, config in enumerate(phone_configs):
            if i == 0:
                # Use the existing service for the first phone number
                task = asyncio.create_task(
                    telethon_client_service.start(
                        config['phone'], config['api_id'], config['api_hash']
                    )
                )
                service_tasks.append(task)
                logger.info(f"Started primary telethon client for {config['phone']}")
            else:
                # Create additional services for other phone numbers
                additional_service = TelethonClientService()
                task = asyncio.create_task(
                    additional_service.start(
                        config['phone'], config['api_id'], config['api_hash']
                    )
                )
                service_tasks.append(task)
                logger.info(f"Started additional telethon client for {config['phone']}")

        tasks.update(service_tasks)
        logger.info(f"All {len(service_tasks)} telethon clients started successfully")
        
        await asyncio.gather(*service_tasks)

    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise


if __name__ == "__main__":
    try:
        loader = CredentialLoader()
        loader.load_credentials()
        asyncio.run(main(loader))

    except KeyboardInterrupt:
        print("\nTelethon clients stopped by user")