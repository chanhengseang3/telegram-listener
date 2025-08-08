# Deployment Guide

This project can now be deployed in three different modes using the same codebase:

## 1. Full Deployment (Original)
Run both bots and telethon client together:
```bash
python main.py
```

## 2. Bots Only Deployment
Run only the Telegram bots without telethon client:
```bash
python main_bots_only.py
```

## 3. Telethon Client Only Deployment
Run only the telethon client(s) for message listening:
```bash
python main_telethon_only.py
```

## Environment Variables

### Required for all deployments:
- `BOT_TOKEN` - Main Telegram bot token
- `BOT_NAME` - Bot name
- `DB_USER` - Database username
- `DB_HOST` - Database host
- `DB_NAME` - Database name
- `DB_PASSWORD` - Database password

### Required for telethon client deployment:
- `API_ID1` - Telegram API ID for phone 1
- `API_HASH1` - Telegram API hash for phone 1
- `PHONE_NUMBER1` - Phone number 1

### Optional for multiple phone numbers:
- `API_ID2`, `API_HASH2`, `PHONE_NUMBER2` - For second phone
- `API_ID3`, `API_HASH3`, `PHONE_NUMBER3` - For third phone
- ... up to `API_ID9`, `API_HASH9`, `PHONE_NUMBER9`

### Optional bot tokens:
- `ADMIN_BOT_TOKEN` - Admin bot token
- `AUTOSUM_BUSINESS_BOT_TOKEN` - Business bot token  
- `PRIVATE_CHAT_BOT` - Private chat bot token

## Deployment Examples

### Deploy with multiple phone numbers (telethon only):
```bash
export API_ID1="your_api_id_1"
export API_HASH1="your_api_hash_1" 
export PHONE_NUMBER1="+1234567890"

export API_ID2="your_api_id_2"
export API_HASH2="your_api_hash_2"
export PHONE_NUMBER2="+1234567891"

python main_telethon_only.py
```

### Deploy bots only:
```bash
export BOT_TOKEN="your_bot_token"
export ADMIN_BOT_TOKEN="your_admin_token"
# ... other bot environment variables

python main_bots_only.py
```

## Docker Deployment

You can create separate Docker containers for each deployment mode:

### Dockerfile.telethon
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main_telethon_only.py"]
```

### Dockerfile.bots  
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main_bots_only.py"]
```

## Session Files

- Telethon session files (e.g., `+85568813335.session`) will be created in the working directory
- Make sure to persist these files between deployments to avoid re-authentication
- Each phone number will have its own session file

## Logs

- Full deployment: `telegram_bot.log`
- Bots only: `telegram_bots.log` 
- Telethon only: `telethon_client.log`