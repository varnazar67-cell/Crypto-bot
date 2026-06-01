import os
import requests
import ccxt
import pandas as pd
import mplfinance as mpf
import time
import threading
from flask import Flask

# ======================
# TELEGRAM
# ======================

TOKEN = os.getenv("8834703546:AAHy2MZwD2BaA2j-apTaSKC1qMl6kg8-UgY")
CHAT_ID = os.getenv("8108131641")

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

        requests.post(
            url,
            data={
                "chat_id": CHAT_ID,
                "text": text
            },
            timeout=15
        )

    except Exception as e:
        print("TELEGRAM ERROR:", e)


def send_photo():
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"

        with open("chart.png", "rb") as f:
            requests.post(
                url,
                data={"chat_id": CHAT_ID},
                files={"photo": f},
                timeout=30
            )

    except Exception as e:
        print("PHOTO ERROR:", e)


# ======================
# EXCHANGE
# ======================

bingx = ccxt.bingx({
    "enableRateLimit": True
})

symbol_bingx = "BTC/USDT"

# ======================
# TIMEFRAMES
# ======================

timeframes = {
    "1H": "1h",
    "2H": "1h",
    "4H": "1h"
}

# ======================
# MEXC DATA
# ======================

def get_mexc_ohlcv(symbol="BTCUSDT", interval="60m", limit=100):

    try:

        url = "https://api.mexc.com/api/v3/klines"

        r = requests.get(
            url,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            },
            timeout=15
        )

        data = r.json()

        if not isinstance(data, list):
            return None

        cleaned = []

        for c in data:
            cleaned.append([
                c[0],
                c[1],
                c[2],
                c[3],
                c[4],
                c[5]
            ])

        df = pd.DataFrame(
            cleaned,
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        df["time"] = pd.to_datetime(df["time"], unit="ms")

        df[
            ["open", "high", "low", "close", "volume"]
        ] = df[
            ["open", "high", "low", "close", "volume"]
        ].astype(float)

        df.set_index("time", inplace=True)

        return df

    except Exception as e:
        print("MEXC ERROR:", e)
        return None


# ======================
# BINGX DATA
# ======================

def get_bingx_ohlcv(tf="1h"):

    try:

        data = bingx.fetch_ohlcv(
            symbol_bingx,
            timeframe=tf,
            limit=100
        )

        if not data:
            return None

        df = pd.DataFrame(
            data,
            columns=[
                "time",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        )

        df["time"] = pd.to_datetime(df["time"], unit="ms")

        df.set_index("time", inplace=True)

        return df

    except Exception as e:
        print("BINGX ERROR:", e)
        return None


# ======================
# LEVELS
# ======================

def resistance(df):

    if df is None or len(df) < 50:
        return None

    return df["high"].rolling(50).max().iloc[-1]


def volume_ok(df):

    if df is None or len(df) < 20:
        return False

    return (
        df["volume"].iloc[-1]
        >
        df["volume"].rolling(20).mean().iloc[-1]
    )


# ======================
# CHART
# ======================

def make_chart(df, level):

    try:

        add_plot = mpf.make_addplot(
            [level] * len(df),
            color="red"
        )

        mpf.plot(
            df,
            type="candle",
            style="charles",
            addplot=add_plot,
            volume=True,
            savefig="chart.png"
        )

    except Exception as e:
        print("CHART ERROR:", e)


# ======================
# SCAN LOGIC
# ======================

def scan_exchange(exchange_name, df, tf_name):

    if df is None:
        return

    level = resistance(df)

    if level is None:
        return

    price = df["close"].iloc[-1]

    touch = abs(price - level) / level < 0.002

    vol = volume_ok(df)

    rejection = (
        df["close"].iloc[-1]
        <
        df["open"].iloc[-1]
    )

    print(
        exchange_name,
        tf_name,
        price,
        level,
        touch,
        vol,
        rejection
    )

    if touch and vol and rejection:

        make_chart(df, level)

        send_photo()

        send_telegram(
            f"{exchange_name} SIGNAL\n\n"
            f"TF: {tf_name}\n"
            f"Price: {price:.2f}\n"
            f"Level: {level:.2f}"
        )


# ======================
# MAIN
# ======================

def main():

    for tf_name, tf in timeframes.items():

        mexc_df = get_mexc_ohlcv(
            symbol="BTCUSDT",
            interval="60m"
        )

        scan_exchange(
            "🔴 MEXC",
            mexc_df,
            tf_name
        )

    for tf_name, tf in timeframes.items():

        bingx_df = get_bingx_ohlcv(tf)

        scan_exchange(
            "🔵 BINGX",
            bingx_df,
            tf_name
        )


# ======================
# BOT LOOP
# ======================

def bot_loop():

    while True:

        try:

            print("SCAN START")

            main()

            print("SCAN END")

        except Exception as e:

            print("LOOP ERROR:", e)

        time.sleep(300)


# ======================
# FLASK FOR RENDER
# ======================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"


threading.Thread(
    target=bot_loop,
    daemon=True
).start()


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
