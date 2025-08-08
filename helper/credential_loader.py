import os


class CredentialLoader:
    REQUIRED_ENV_VARS = [
        "BOT_TOKEN",
        "BOT_NAME",
        "DB_USER",
        "DB_HOST",
        "DB_NAME",
        "API_ID1",
        "API_HASH1",
        "PHONE_NUMBER1",
    ]

    OPTIONAL_ENV_VARS = ["TIMEZONE"]

    def __init__(self):
        self.bot_token: str = ""
        self.bot_name: str = ""
        self.db_user: str = ""
        self.db_password: str = ""
        self.db_host: str = ""
        self.db_name: str = ""
        self.api_id1: str = ""
        self.api_hash1: str = ""
        self.phone_number1: str = ""
        self.admin_bot_token: str = ""
        self.autosum_business_bot_token: str = ""
        self.private_chat_bot_token: str = ""
        
        # Support for multiple phone numbers (2-9)
        for i in range(2, 10):
            setattr(self, f'api_id{i}', "")
            setattr(self, f'api_hash{i}', "")
            setattr(self, f'phone_number{i}', "")

    def load_credentials(self) -> dict:
        print("Loading credentials...")
        missing = []
        self.bot_token = os.getenv("BOT_TOKEN") or ""
        self.bot_name = os.getenv("BOT_NAME") or ""
        self.db_user = os.getenv("DB_USER") or ""
        self.db_password = os.getenv("DB_PASSWORD") or ""
        self.db_host = os.getenv("DB_HOST") or ""
        self.db_name = os.getenv("DB_NAME") or ""
        self.api_id1 = os.getenv("API_ID1") or ""
        self.api_hash1 = os.getenv("API_HASH1") or ""
        self.phone_number1 = os.getenv("PHONE_NUMBER1") or ""
        self.admin_bot_token = os.getenv("ADMIN_BOT_TOKEN") or ""
        self.autosum_business_bot_token = os.getenv("AUTOSUM_BUSINESS_BOT_TOKEN") or ""
        self.private_chat_bot_token = os.getenv("PRIVATE_CHAT_BOT") or ""

        # Load additional phone number configurations (2-9)
        for i in range(2, 10):
            setattr(self, f'api_id{i}', os.getenv(f'API_ID{i}') or "")
            setattr(self, f'api_hash{i}', os.getenv(f'API_HASH{i}') or "")
            setattr(self, f'phone_number{i}', os.getenv(f'PHONE_NUMBER{i}') or "")

        for var in self.REQUIRED_ENV_VARS:
            if not getattr(self, var.lower()):
                missing.append(var)

        if missing:
            error_msg = (
                f"Missing required environment variables: {', '.join(missing)}\n"
            )
            error_msg += "For local development, set these in your .env file.\n"
            error_msg += "For CI/CD deployment, set these as GitHub Secrets in your repository settings."
            raise EnvironmentError(error_msg)

        print("Credentials loaded successfully")
        return {
            "bot_token": self.bot_token,
            "bot_name": self.bot_name,
            "api_id1": self.api_id1,
            "api_hash1": self.api_hash1,
            "phone_number1": self.phone_number1,
        }
