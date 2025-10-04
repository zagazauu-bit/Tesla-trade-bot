# Tesla Trade Bot

A Telegram bot that trades Tesla (TSLA) stock using Alpaca API.

## Features
- Get Tesla stock price
- Buy/sell shares
- Account balance & buying power (/account)
- Set price alerts with auto-trading
- Moving Average strategy (SMA5/SMA20)
- Trade logging
- Admin-only commands

## Setup
1. Clone repo and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Fill `config.py` with your keys:
   - `BOT_TOKEN` (Telegram bot token)
   - `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`
   - Run `/whoami` to get your Telegram ID and paste into `ADMIN_ID`
3. Run the bot:
   ```bash
   python bot.py
   ```
