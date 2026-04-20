"""
Conditional price alert — runs every hour during market hours.
Sends a LINE notification if any asset moves beyond its threshold.
"""
import os
import datetime
import requests
import pytz
import yfinance as yf
from config import ALERT_THRESHOLD_STOCKS, ALERT_THRESHOLD_GOLD, ALERT_THRESHOLD_CRYPTO

BANGKOK_TZ = pytz.timezone('Asia/Bangkok')

WATCH = {
    "gold":  ("GC=F",    ALERT_THRESHOLD_GOLD,   "💰 ทอง (XAU/USD)", "$"),
    "sp500": ("^GSPC",   ALERT_THRESHOLD_STOCKS,  "📈 S&P 500",       ""),
    "vix":   ("^VIX",    5.0,                     "📉 VIX",           ""),
    "btc":   ("BTC-USD", ALERT_THRESHOLD_CRYPTO,  "₿ BTC",            "$"),
    "eth":   ("ETH-USD", ALERT_THRESHOLD_CRYPTO,  "🔷 ETH",           "$"),
    "AAPL":  ("AAPL",    ALERT_THRESHOLD_STOCKS,  "🍎 AAPL",          "$"),
    "MSFT":  ("MSFT",    ALERT_THRESHOLD_STOCKS,  "🪟 MSFT",          "$"),
    "NVDA":  ("NVDA",    ALERT_THRESHOLD_STOCKS,  "🟢 NVDA",          "$"),
    "AMZN":  ("AMZN",    ALERT_THRESHOLD_STOCKS,  "📦 AMZN",          "$"),
    "META":  ("META",    ALERT_THRESHOLD_STOCKS,  "👤 META",          "$"),
    "GOOGL": ("GOOGL",   ALERT_THRESHOLD_STOCKS,  "🔍 GOOGL",         "$"),
    "TSLA":  ("TSLA",    ALERT_THRESHOLD_STOCKS,  "🚗 TSLA",          "$"),
    "ASTS":  ("ASTS",    ALERT_THRESHOLD_STOCKS,  "🛰 ASTS",           "$"),
    "UNH":   ("UNH",     ALERT_THRESHOLD_STOCKS,  "🏥 UNH",           "$"),
    "EOSE":  ("EOSE",    ALERT_THRESHOLD_STOCKS,  "🔋 EOSE",          "$"),
    "RKLB":  ("RKLB",    ALERT_THRESHOLD_STOCKS,  "🚀 RKLB",          "$"),
    "OKLO":  ("OKLO",    ALERT_THRESHOLD_STOCKS,  "⚛️ OKLO",          "$"),
    "ONDS":  ("ONDS",    ALERT_THRESHOLD_STOCKS,  "📡 ONDS",          "$"),
}


def fetch_change(symbol: str) -> tuple:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d")
    if hist.empty or len(hist) < 1:
        raise ValueError(f"No data for {symbol}")
    current = round(hist["Close"].iloc[-1], 2)
    prev = round(hist["Close"].iloc[-2], 2) if len(hist) >= 2 else current
    change_pct = round(((current - prev) / prev) * 100, 2) if prev else 0.0
    return current, change_pct


def send_line(message: str):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("LINE credentials not set")
        return
    try:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": [{"type": "text", "text": message}]},
            timeout=30,
        )
        resp.raise_for_status()
        print("Alert sent to LINE")
    except Exception as e:
        print(f"Failed to send LINE alert: {e}")


def main():
    now = datetime.datetime.now(BANGKOK_TZ)
    triggered = []

    for key, (symbol, threshold, label, prefix) in WATCH.items():
        try:
            price, change_pct = fetch_change(symbol)
            print(f"  {symbol}: {price} ({change_pct:+.2f}%)")
            if abs(change_pct) >= threshold:
                direction = "▲ ขึ้น" if change_pct > 0 else "▼ ลง"
                triggered.append(
                    f"{label}: {prefix}{price:,.2f} | {direction} {abs(change_pct):.2f}% (threshold: {threshold}%)"
                )
        except Exception as e:
            print(f"  Warning: {symbol}: {e}")

    if triggered:
        time_str = now.strftime("%d %b %Y %H:%M")
        lines = [
            "🚨 Price Alert!",
            f"⏰ {time_str} (Bangkok Time)",
            "",
            "สินทรัพย์ที่เคลื่อนไหวผิดปกติ:",
            "",
        ] + triggered + [
            "",
            "⚠️ Not financial advice.",
        ]
        message = "\n".join(lines)
        print(f"\n{len(triggered)} alert(s) triggered")
        send_line(message)
    else:
        print("\nNo alerts triggered — all assets within normal range")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
