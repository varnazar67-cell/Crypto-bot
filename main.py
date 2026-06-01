import os
import requests
import ccxt
import pandas as pd
import mplfinance as mpf
import time
import threading
import json
from flask import Flask

# ======================
# TELEGRAM CONFIG
# ======================
TOKEN = "8834703546:AAHy2MZwD2BaA2j-apTaSKC1qMl6kg8-UgY"
CHAT_ID = "8108131641"

def send_telegram_text(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
    except Exception as e:
        print("TELEGRAM TEXT ERROR:", e, flush=True)


def send_signal_to_telegram(caption, coin):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        
        mexc_url = f"https://www.mexc.com/exchange/{coin}_USDT"
        bingx_url = f"https://bingx.com/spot/{coin}USDT"
        
        reply_markup = {
            "inline_keyboard": [
                [{"text": "Биржа MEXC ↗", "url": mexc_url}],
                [{"text": "Биржа BINGX ↗", "url": bingx_url}]
            ]
        }
        
        with open("chart.png", "rb") as f:
            requests.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": json.dumps(reply_markup)
                },
                files={"photo": f},
                timeout=30
            )
    except Exception as e:
        print("TELEGRAM SIGNAL ERROR:", e, flush=True)


# ======================
# EXCHANGE CONFIG
# ======================
bingx = ccxt.bingx({
    "enableRateLimit": True,
    "timeout": 15000  # 👈 Захист від зависання: таймаут 15 секунд
})

COINS = [
    "BTC", "ETH", "SOL", "HYPE", "LINK", "DOGE", "XRP", "NEAR", 
    "TAO", "ZEC", "LTC", "AAVE", "RIVER", "AVAX", "INJ", "WLD", "WIF", "XLM"
]

TIMEFRAMES = {
    "1H": {"mexc": "60m", "bingx": "1h"},
    "2H": {"mexc": "2h",  "bingx": "2h"},
    "4H": {"mexc": "4h",  "bingx": "4h"}
}


# ======================
# DATA FETCHERS
# ======================
def get_mexc_ohlcv(symbol, interval, limit=100):
    try:
        url = "https://api.mexc.com/api/v3/klines"
        r = requests.get(
            url,
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=15
        )
        data = r.json()
        if not isinstance(data, list):
            return None

        cleaned = []
        for c in data:
            cleaned.append([c[0], c[1], c[2], c[3], c[4], c[5]])

        df = pd.DataFrame(cleaned, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
        df.set_index("time", inplace=True)
        return df
    except Exception as e:
        print(f"MEXC ERROR ({symbol}):", e, flush=True)
        return None


def get_bingx_ohlcv(symbol, tf, limit=100):
    try:
        data = bingx.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        if not data:
            return None

        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)
        return df
    except Exception as e:
        print(f"BINGX ERROR ({symbol}):", e, flush=True)
        return None


# ======================
# STRATEGY LOGIC
# ======================
def resistance(df):
    if df is None or len(df) < 50:
        return None
    return df["high"].rolling(50).max().iloc[-1]


def volume_ok(df):
    if df is None or len(df) < 20:
        return False
    return df["volume"].iloc[-1] > df["volume"].rolling(20).mean().iloc[-1]


def make_chart(df, level):
    try:
        add_plot = mpf.make_addplot([level] * len(df), color="red")
        mpf.plot(df, type="candle", style="charles", addplot=add_plot, volume=True, savefig="chart.png")
    except Exception as e:
        print("CHART ERROR:", e, flush=True)


def format_price(val):
    if val >= 100: return f"{val:.2f}"
    if val >= 1: return f"{val:.4f}"
    return f"{val:.6f}".rstrip('0').rstrip('.')


# ======================
# SCANNER
# ======================
def scan_exchange(exchange_name, df, coin, tf_name):
    if df is None:
        return

    level = resistance(df)
    if level is None:
        return

    price = df["close"].iloc[-1]
    touch = abs(price - level) / level < 0.002
    vol = volume_ok(df)
    rejection = df["close"].iloc[-1] < df["open"].iloc[-1]

    # 👇 ТУТ ДОДАНО flush=True ДЛЯ МИТТЄВОГО ВІДОБРАЖЕННЯ В КОНСОЛІ
    print(exchange_name, coin, tf_name, f"Price: {price}", f"Level: {level}", f"Touch: {touch}", flush=True)

    if touch and vol and rejection:
        make_chart(df, level)
        
        p_str = format_price(price)
        l_str = format_price(level)
        
        caption = (
            f"*{coin} ({tf_name})*\n"
            f"Сопротивление: {l_str}\n"
            f"Цена: {p_str}"
        )
        
        send_signal_to_telegram(caption, coin)


# ======================
# MAIN LOGIC
# ======================
def main():
    for coin in COINS:
        for tf_name, tf_modes in TIMEFRAMES.items():
            
            # 1. Сканування MEXC
            mexc_symbol = f"{coin}USDT"
            mexc_df = get_mexc_ohlcv(mexc_symbol, tf_modes["mexc"])
            scan_exchange("🔴 MEXC", mexc_df, coin, tf_name)

            # 2. Сканування BINGX
            bingx_symbol = f"{coin}/USDT"
            bingx_df = get_bingx_ohlcv(bingx_symbol, tf_modes["bingx"])
            scan_exchange("🔵 BINGX", bingx_df, coin, tf_name)

            time.sleep(0.5)


def bot_loop():
    send_telegram_text("🚀 Бот успішно запущений на Render!\nСканую 18 монет на таймфреймах: 1H, 2H, 4H.")

    while True:
        try:
            print("SCAN START", flush=True) # 👈 Миттєвий принт
            main()
            print("SCAN END", flush=True)   # 👈 Миттєвий принт
        except Exception as e:
            print("LOOP ERROR:", e, flush=True)
        
        time.sleep(300)


# ======================
# FLASK SERVER
# ======================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

threading.Thread(target=bot_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
