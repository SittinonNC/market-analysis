import os
import time
import datetime
import pytz
import requests
import feedparser
import yfinance as yf
from groq import Groq

BANGKOK_TZ = pytz.timezone('Asia/Bangkok')

RSS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/rss/topstories"),
    ("Investing.com Gold", "https://www.investing.com/rss/news_14.rss"),
]

# Magnificent 7
MAG7 = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "TSLA": "Tesla",
}

# Additional watchlist
WATCHLIST = {
    "ASTS": "AST SpaceMobile",
    "UNH": "UnitedHealth",
    "EOSE": "Eos Energy",
    "RKLB": "Rocket Lab",
    "OKLO": "Oklo",
    "ONDS": "Ondas Holdings",
}


def fetch_single(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d")
    if hist.empty or len(hist) < 1:
        raise ValueError(f"No data for {symbol}")
    current = round(hist["Close"].iloc[-1], 2)
    high = round(hist["High"].iloc[-1], 2)
    low = round(hist["Low"].iloc[-1], 2)
    prev_close = round(hist["Close"].iloc[-2], 2) if len(hist) >= 2 else current
    change_pct = round(((current - prev_close) / prev_close) * 100, 2) if prev_close else 0.0
    return {"price": current, "change": change_pct, "high": high, "low": low}


def fetch_prices() -> dict:
    prices = {}

    # Gold & S&P 500
    for key, symbol in [("gold", "GC=F"), ("sp500", "^GSPC")]:
        try:
            data = fetch_single(symbol)
            prices[key] = data
            print(f"  {symbol}: ${data['price']} ({data['change']:+.2f}%)")
        except Exception as e:
            print(f"  Warning: Failed to fetch {symbol}: {e}")
            prices[key] = {"price": "N/A", "change": "N/A", "high": "N/A", "low": "N/A"}

    # Magnificent 7
    prices["mag7"] = {}
    for symbol, name in MAG7.items():
        try:
            data = fetch_single(symbol)
            prices["mag7"][symbol] = {"name": name, **data}
            print(f"  {symbol}: ${data['price']} ({data['change']:+.2f}%)")
        except Exception as e:
            print(f"  Warning: Failed to fetch {symbol}: {e}")
            prices["mag7"][symbol] = {"name": name, "price": "N/A", "change": "N/A", "high": "N/A", "low": "N/A"}

    # Watchlist
    prices["watchlist"] = {}
    for symbol, name in WATCHLIST.items():
        try:
            data = fetch_single(symbol)
            prices["watchlist"][symbol] = {"name": name, **data}
            print(f"  {symbol}: ${data['price']} ({data['change']:+.2f}%)")
        except Exception as e:
            print(f"  Warning: Failed to fetch {symbol}: {e}")
            prices["watchlist"][symbol] = {"name": name, "price": "N/A", "change": "N/A", "high": "N/A", "low": "N/A"}

    return prices


def fetch_news() -> str:
    articles = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:5]
            for entry in entries:
                title = entry.get("title", "No title").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                summary = summary[:200] if summary else ""
                articles.append(f"[{source_name}] {title}\n{summary}")
            print(f"  Fetched {len(entries)} articles from {source_name}")
        except Exception as e:
            print(f"  Warning: Failed to fetch {source_name}: {e}")

    combined = "\n\n".join(articles)
    return combined[:3000]


def fmt_change(v):
    if isinstance(v, float):
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    return str(v)


def fmt_price(v, prefix="$"):
    if isinstance(v, float):
        return f"{prefix}{v:,.2f}"
    return str(v)


def build_price_context(prices: dict) -> str:
    gold = prices["gold"]
    sp500 = prices["sp500"]

    lines = [
        f"Gold (XAU/USD): {fmt_price(gold['price'])} | Change: {fmt_change(gold['change'])} | High: {gold['high']} | Low: {gold['low']}",
        f"S&P 500: {fmt_price(sp500['price'], prefix='')} | Change: {fmt_change(sp500['change'])} | High: {sp500['high']} | Low: {sp500['low']}",
        "",
        "Magnificent 7:",
    ]
    for symbol, d in prices["mag7"].items():
        lines.append(f"  {symbol} ({d['name']}): {fmt_price(d['price'])} | Change: {fmt_change(d['change'])}")

    lines += ["", "Watchlist:"]
    for symbol, d in prices["watchlist"].items():
        lines.append(f"  {symbol} ({d['name']}): {fmt_price(d['price'])} | Change: {fmt_change(d['change'])}")

    return "\n".join(lines)


def get_groq_analysis(prices: dict, news: str) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        price_context = build_price_context(prices)

        user_prompt = f"""Analyze the following market data and news. Provide a comprehensive briefing.

CURRENT PRICES:
{price_context}

LATEST NEWS:
{news}

Please provide:

1. Overall market sentiment (Bullish/Bearish/Neutral) with reasoning

2. Gold (XAU/USD) Analysis:
   - Trend direction and strength
   - Support (2 levels) and Resistance (2 levels)
   - ACTION: clearly state BUY or SELL signal with reasoning
   - If BUY: exact entry price zone and stop loss
   - If SELL: exact exit/sell price target and stop loss
   - Risk factors to watch

3. S&P 500 Analysis:
   - Trend direction
   - Support (2 levels) and Resistance (2 levels)
   - Best buy entry price zone for today
   - Outlook

4. Magnificent 7 — for each stock (AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA):
   - 1-line sentiment
   - Recommended buy entry price zone

5. Watchlist — for each stock (ASTS, UNH, EOSE, RKLB, OKLO, ONDS):
   - 1-line sentiment
   - Recommended buy entry price zone

6. Top 3 most important news affecting markets today

7. Overall recommendation and risk warning

Write the entire response in Thai language. Be specific with price numbers."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert financial analyst specializing in gold, US stock markets, and individual equities. "
                        "Your job is to analyze current market data and news to provide actionable trading insights. "
                        "Always be specific with price levels. Format your response in a clear, structured way. "
                        "Use emojis sparingly but effectively. Write in Thai language. "
                        "Do NOT use any Markdown formatting such as ** or * for bold/italic. Use plain text only."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3000,
            temperature=0.3,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"  Warning: Groq API failed: {e}")
        return f"⚠️ การวิเคราะห์ AI ไม่สำเร็จ: {e}\n\nข้อมูลราคาแสดงอยู่ด้านบน กรุณาวิเคราะห์เองจากข้อมูลดิบ"


def build_line_message(prices: dict, analysis: str) -> str:
    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    date_str = now_bangkok.strftime("%d %b %Y")
    time_str = now_bangkok.strftime("%H:%M")

    gold = prices["gold"]
    sp500 = prices["sp500"]

    # Header
    lines = [
        "📊 Daily Market Briefing",
        f"📅 {date_str} | ⏰ {time_str} (Bangkok Time)",
        "",
        f"💰 GOLD (XAU/USD): {fmt_price(gold['price'])} ({fmt_change(gold['change'])})",
        f"📈 S&P 500: {fmt_price(sp500['price'], prefix='')} ({fmt_change(sp500['change'])})",
        "",
        "── Magnificent 7 ──",
    ]

    for symbol, d in prices["mag7"].items():
        arrow = "▲" if isinstance(d["change"], float) and d["change"] >= 0 else "▼"
        lines.append(f"{arrow} {symbol}: {fmt_price(d['price'])} ({fmt_change(d['change'])})")

    lines += ["", "── Watchlist ──"]
    for symbol, d in prices["watchlist"].items():
        arrow = "▲" if isinstance(d["change"], float) and d["change"] >= 0 else "▼"
        lines.append(f"{arrow} {symbol}: {fmt_price(d['price'])} ({fmt_change(d['change'])})")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        analysis,
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ This is AI-generated analysis. Not financial advice. Trade at your own risk.",
    ]

    return "\n".join(lines)


def send_line(message: str):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not token or not user_id:
        print("  Error: LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    max_len = 5000
    chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)]

    for i, chunk in enumerate(chunks):
        try:
            response = requests.post(
                url,
                headers=headers,
                json={"to": user_id, "messages": [{"type": "text", "text": chunk}]},
                timeout=30,
            )
            response.raise_for_status()
            print(f"  LINE chunk {i + 1}/{len(chunks)} sent successfully")
        except requests.exceptions.HTTPError as e:
            print(f"  Error sending LINE chunk {i + 1}: {e}")
            print(f"  Response: {response.text}")
        except Exception as e:
            print(f"  Error sending LINE chunk {i + 1}: {e}")

        if i < len(chunks) - 1:
            time.sleep(1)


def main():
    print("[1/5] Fetching prices...")
    prices = fetch_prices()

    print("[2/5] Fetching news...")
    news = fetch_news()

    print("[3/5] Calling Groq API for analysis...")
    analysis = get_groq_analysis(prices, news)

    print("[4/5] Building LINE message...")
    message = build_line_message(prices, analysis)

    print("[5/5] Sending to LINE...")
    send_line(message)

    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    print(f"\n✅ Execution complete at {now_bangkok.strftime('%Y-%m-%d %H:%M:%S')} Bangkok time")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
