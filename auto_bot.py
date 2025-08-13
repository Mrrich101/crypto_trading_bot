import ccxt
import time
import numpy as np
import requests

# === Settings ===
USE_TESTNET = True  # Set False for real trading (be careful)
API_KEY = "TJB8sS7jk1GbQq1VlCzWzjQAVxPshaSg6vDQ2ADRZNCIAY9VLojVNGBvuWTvUKbP"
SECRET_KEY = "msXS29ZWt6mJaAfCA0GKnWAH6dU9Lp8hcOJgL5TcMaGsAbDb3jJAxwIF4Gb2Ex1q"
TRADING_PAIR = "BTC/USDT"
TRADE_AMOUNT = 0.001  # Amount of BTC per trade
STOP_LOSS_PERCENT = 2.0
TAKE_PROFIT_PERCENT = 3.0
CHECK_INTERVAL = 60  # seconds
SMA_SHORT_PERIOD = 50
SMA_LONG_PERIOD = 200
TRADE_COOLDOWN = 300  # seconds (5 minutes)

# Telegram bot settings
TELEGRAM_BOT_TOKEN = "7199940538:AAFZmfUHK1JqLucIOWRrtjxnvlIw7oBVhKo"
TELEGRAM_CHAT_ID = "668548663"
# ================

exchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": SECRET_KEY,
    "enableRateLimit": True,
})

if USE_TESTNET:
    exchange.set_sandbox_mode(True)
    print("🔹 Running on Binance TESTNET (no real money)")
else:
    print("⚠ Running on Binance MAIN (real money)")

last_buy_price = None
trailing_stop_price = None
last_trade_time = 0

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("⚠ Failed to send Telegram message:", e)

def fetch_balance():
    return exchange.fetch_balance()

def print_balances():
    balance = fetch_balance()
    usdt_balance = balance['total'].get('USDT', 0)
    btc_balance = balance['total'].get('BTC', 0)
    print(f"💰 USDT Balance: {usdt_balance:.6f}")
    print(f"💰 BTC Balance: {btc_balance:.6f}")

def fetch_latest_price():
    ticker = exchange.fetch_ticker(TRADING_PAIR)
    return ticker['last']

def fetch_ohlcv(limit=250):
    bars = exchange.fetch_ohlcv(TRADING_PAIR, timeframe='1m', limit=limit)
    return [bar[4] for bar in bars]

def calculate_sma(prices, period):
    if len(prices) < period:
        return None
    return np.mean(prices[-period:])

def place_order(side):
    global last_buy_price, trailing_stop_price, last_trade_time
    print(f"📈 Placing {side.upper()} order for {TRADE_AMOUNT} {TRADING_PAIR}...")
    try:
        order = exchange.create_market_order(TRADING_PAIR, side, TRADE_AMOUNT)
        print("✅ Order placed:", order)
        price = order.get('average') or fetch_latest_price()
        last_trade_time = time.time()
        if side == "buy":
            last_buy_price = price
            trailing_stop_price = price * (1 - STOP_LOSS_PERCENT / 100)
            msg = f"🚀 Bought {TRADE_AMOUNT} {TRADING_PAIR} at {price:.2f}. Trailing stop set at {trailing_stop_price:.2f}"
            print(msg)
            send_telegram_message(msg)
        elif side == "sell":
            last_buy_price = None
            trailing_stop_price = None
            msg = f"🛑 Sold {TRADE_AMOUNT} {TRADING_PAIR} at {price:.2f}. Position closed."
            print(msg)
            send_telegram_message(msg)
    except Exception as e:
        print("❌ Order failed:", e)
        send_telegram_message(f"❌ Order failed: {e}")

def update_trailing_stop(current_price):
    global trailing_stop_price
    if trailing_stop_price is None:
        return
    new_stop = current_price * (1 - STOP_LOSS_PERCENT / 100)
    if new_stop > trailing_stop_price:
        print(f"🔧 Updating trailing stop from {trailing_stop_price:.2f} to {new_stop:.2f}")
        trailing_stop_price = new_stop

if __name__ == "__main__":
    print("=== Starting Advanced Trading Bot with Telegram Alerts ===")
    prices = fetch_ohlcv()
    sma_short = calculate_sma(prices, SMA_SHORT_PERIOD)
    sma_long = calculate_sma(prices, SMA_LONG_PERIOD)
    print(f"Initial SMA{SMA_SHORT_PERIOD}: {sma_short:.2f}, SMA{SMA_LONG_PERIOD}: {sma_long:.2f}")

    while True:
        try:
            current_price = fetch_latest_price()
            prices.append(current_price)
            if len(prices) > 250:
                prices.pop(0)

            sma_short = calculate_sma(prices, SMA_SHORT_PERIOD)
            sma_long = calculate_sma(prices, SMA_LONG_PERIOD)
            print_balances()
            print(f"💹 Price: {current_price:.2f} | SMA{SMA_SHORT_PERIOD}: {sma_short:.2f} | SMA{SMA_LONG_PERIOD}: {sma_long:.2f}")

            if sma_short and sma_long:
                trend = "up" if sma_short > sma_long else "down"
                print(f"📊 Trend detected: {trend}")
            else:
                trend = None
                print("📊 Not enough data to determine trend.")

            time_since_last_trade = time.time() - last_trade_time
            if time_since_last_trade < TRADE_COOLDOWN:
                print(f"⏳ Cooldown active: waiting {int(TRADE_COOLDOWN - time_since_last_trade)} seconds before next trade.")
                time.sleep(CHECK_INTERVAL)
                continue

            if last_buy_price:
                update_trailing_stop(current_price)
                change_pct = ((current_price - last_buy_price) / last_buy_price) * 100
                if current_price <= trailing_stop_price:
                    print("⚠ Trailing stop triggered!")
                    place_order("sell")
                elif change_pct >= TAKE_PROFIT_PERCENT:
                    print("🎯 Take profit triggered!")
                    place_order("sell")
            else:
                if trend == "up":
                    place_order("buy")
                else:
                    print("⛔ Trend is down, skipping buy.")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            print("⚠ Error:", e)
            send_telegram_message(f"⚠ Error: {e}")
            print("⏳ Retrying after backoff...")
            time.sleep(CHECK_INTERVAL * 2)
