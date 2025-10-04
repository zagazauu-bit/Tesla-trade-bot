import yfinance as yf
import alpaca_trade_api as tradeapi
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import datetime
from config import BOT_TOKEN, ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, ADMIN_ID

# Alpaca API
api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, api_version="v2")

# Alerts storage
alerts = {}  # chat_id -> list of (price, action)

# Strategy state
strategy_enabled = False

# --- Logging Helper ---
def log_trade(action, price, reason="manual"):
    with open("trades.log", "a") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{timestamp} | {action.upper()} | TSLA | Price: {price:.2f} | Reason: {reason}\n")

# --- Menu Keyboard ---
menu_keyboard = [
    ["📊 Tesla Price", "📦 Position", "💰 Account"],
    ["✅ Buy 1 Share", "❌ Sell 1 Share"],
    ["🔔 Set Alert", "📈 Strategy On", "⏹ Strategy Off"]
]
reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome to Tesla Trade Bot!\nChoose an option:",
        reply_markup=reply_markup
    )

# --- WhoAmI Command ---
async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"👤 Your Telegram ID is: {user_id}")

# --- Account Command ---
async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        acc = api.get_account()
        msg = (
            f"💰 Account Info:\n"
            f"- Equity: ${acc.equity}\n"
            f"- Buying Power: ${acc.buying_power}\n"
            f"- Cash: ${acc.cash}\n"
            f"- Status: {acc.status}"
        )
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- Alerts Commands ---
async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        price = float(context.args[0])
        action = context.args[1].lower()
        if action not in ["buy", "sell"]:
            await update.message.reply_text("⚠️ Use: /setalert <price> <buy/sell>")
            return
        alerts.setdefault(chat_id, []).append((price, action))
        await update.message.reply_text(f"🔔 Alert set: {action.upper()} if TSLA reaches ${price:.2f}")
    except Exception:
        await update.message.reply_text("⚠️ Correct format: /setalert 250 buy")

async def my_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in alerts or not alerts[chat_id]:
        await update.message.reply_text("ℹ️ You have no alerts set.")
    else:
        msg = "📋 Your alerts:\n"
        for price, action in alerts[chat_id]:
            msg += f"- {action.upper()} at ${price}\n"
        await update.message.reply_text(msg)

async def clear_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    alerts.pop(chat_id, None)
    await update.message.reply_text("🧹 All alerts cleared.")

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    stock = yf.Ticker("TSLA")
    price = stock.history(period="1d")["Close"].iloc[-1]

    for chat_id, user_alerts in list(alerts.items()):
        triggered = []
        for alert_price, action in user_alerts:
            if action == "buy" and price <= alert_price:
                api.submit_order("TSLA", qty=1, side="buy", type="market", time_in_force="gtc")
                log_trade("BUY", price, "Alert Trigger")
                await context.bot.send_message(chat_id, f"✅ Auto-BUY: TSLA at ${price:.2f}")
                triggered.append((alert_price, action))
            elif action == "sell" and price >= alert_price:
                api.submit_order("TSLA", qty=1, side="sell", type="market", time_in_force="gtc")
                log_trade("SELL", price, "Alert Trigger")
                await context.bot.send_message(chat_id, f"✅ Auto-SELL: TSLA at ${price:.2f}")
                triggered.append((alert_price, action))
        for t in triggered:
            user_alerts.remove(t)

# --- Strategy Commands ---
async def strategy_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global strategy_enabled
    strategy_enabled = True
    await update.message.reply_text("📈 Moving Average Strategy ENABLED ✅")

async def strategy_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global strategy_enabled
    strategy_enabled = False
    await update.message.reply_text("⏹ Moving Average Strategy DISABLED ❌")

async def strategy_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ ENABLED" if strategy_enabled else "❌ DISABLED"
    await update.message.reply_text(f"📊 Strategy status: {status}")

async def check_strategy(context: ContextTypes.DEFAULT_TYPE):
    global strategy_enabled
    if not strategy_enabled:
        return

    data = yf.download("TSLA", period="1mo", interval="1d")
    data["SMA5"] = data["Close"].rolling(window=5).mean()
    data["SMA20"] = data["Close"].rolling(window=20).mean()

    short_ma = data["SMA5"].iloc[-1]
    long_ma = data["SMA20"].iloc[-1]
    price = data["Close"].iloc[-1]

    if short_ma > long_ma:
        api.submit_order("TSLA", qty=1, side="buy", type="market", time_in_force="gtc")
        log_trade("BUY", price, "Strategy Signal")
        await context.bot.send_message(context.job.chat_id, f"📈 Strategy BUY signal at ${price:.2f}")
    elif short_ma < long_ma:
        api.submit_order("TSLA", qty=1, side="sell", type="market", time_in_force="gtc")
        log_trade("SELL", price, "Strategy Signal")
        await context.bot.send_message(context.job.chat_id, f"📉 Strategy SELL signal at ${price:.2f}")

# --- Show Logs Command ---
async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 Unauthorized.")
        return
    try:
        with open("trades.log", "r") as f:
            lines = f.readlines()[-10:]  # last 10 trades
        await update.message.reply_text("📜 Recent Trades:\n" + "".join(lines))
    except FileNotFoundError:
        await update.message.reply_text("📭 No trades logged yet.")

# --- Handle Button Presses ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "📊 Tesla Price":
        stock = yf.Ticker("TSLA")
        price = stock.history(period="1d")["Close"].iloc[-1]
        await update.message.reply_text(f"📊 Tesla (TSLA): ${price:.2f}")

    elif text == "📦 Position":
        try:
            positions = api.list_positions()
            for pos in positions:
                if pos.symbol == "TSLA":
                    await update.message.reply_text(
                        f"📦 Tesla Holdings:\nShares: {pos.qty}\nValue: ${pos.market_value}"
                    )
                    return
            await update.message.reply_text("⚠️ No Tesla shares held.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    elif text == "💰 Account":
        await account(update, context)

    elif text == "✅ Buy 1 Share":
        try:
            stock = yf.Ticker("TSLA")
            price = stock.history(period="1d")["Close"].iloc[-1]
            api.submit_order("TSLA", qty=1, side="buy", type="market", time_in_force="gtc")
            log_trade("BUY", price, "Manual Trade")
            await update.message.reply_text("✅ Bought 1 Tesla share.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    elif text == "❌ Sell 1 Share":
        try:
            stock = yf.Ticker("TSLA")
            price = stock.history(period="1d")["Close"].iloc[-1]
            api.submit_order("TSLA", qty=1, side="sell", type="market", time_in_force="gtc")
            log_trade("SELL", price, "Manual Trade")
            await update.message.reply_text("✅ Sold 1 Tesla share.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")

    elif text == "📈 Strategy On":
        global strategy_enabled
        strategy_enabled = True
        await update.message.reply_text("📈 Auto-strategy ENABLED ✅")

    elif text == "⏹ Strategy Off":
        global strategy_enabled
        strategy_enabled = False
        await update.message.reply_text("⏹ Auto-strategy DISABLED ❌")

    # --- Admin Only Commands ---
    elif text == "/stopbot":
        if update.effective_user.id == ADMIN_ID:
            await update.message.reply_text("🛑 Bot stopped by admin.")
            raise SystemExit
        else:
            await update.message.reply_text("🚫 Unauthorized command.")

    elif text == "/reset":
        if update.effective_user.id == ADMIN_ID:
            context.chat_data.clear()
            await update.message.reply_text("♻️ Bot memory reset.")
        else:
            await update.message.reply_text("🚫 Unauthorized command.")

# --- Main ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("account", account))
    app.add_handler(CommandHandler("setalert", set_alert))
    app.add_handler(CommandHandler("myalerts", my_alerts))
    app.add_handler(CommandHandler("clearalerts", clear_alerts))
    app.add_handler(CommandHandler("strategy", strategy_status))
    app.add_handler(CommandHandler("strategy_on", strategy_on))
    app.add_handler(CommandHandler("strategy_off", strategy_off))
    app.add_handler(CommandHandler("logs", show_logs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))

    job_queue = app.job_queue
    job_queue.run_repeating(check_alerts, interval=60, first=10)
    job_queue.run_repeating(check_strategy, interval=300, first=20)

    app.run_polling()

if __name__ == "__main__":
    main()
