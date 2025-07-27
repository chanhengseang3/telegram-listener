journalctl -u mytelegrambot -f
find . -maxdepth 1 -type f -name '*.log' ! -name 'telegram_bot_20250722_06.log' -exec rm {} \;
mpstat
