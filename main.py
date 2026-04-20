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


def fetch_prices() -> dict:
    prices = {}
    tickers = {
        "gold": "GC=F",
        "sp500": "^GSPC",
    }

    for key, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="2d")
            if hist.empty or len(hist) < 1:
                raise ValueError(f"No data returned for {symbol}")

            current = round(hist["Close"].iloc[-1], 2)
            high = round(hist["High"].iloc[-1], 2)
            low = round(hist["Low"].iloc[-1], 2)

            if len(hist) >= 2:
                prev_close = round(hist["Close"].iloc[-2], 2)
            else:
                prev_close = current

            change_pct = round(((current - prev_close) / prev_close) * 100, 2) if prev_close else 0.0

            prices[f"{key}_price"] = current
            prices[f"{key}_change"] = change_pct
            prices[f"{key}_high"] = high
            prices[f"{key}_low"] = low

            print(f"  {symbol}: ${current} ({change_pct:+.2f}%)")

        except Exception as e:
            print(f"  Warning: Failed to fetch {symbol}: {e}")
            prices[f"{key}_price"] = "N/A"
            prices[f"{key}_change"] = "N/A"
            prices[f"{key}_high"] = "N/A"
            prices[f"{key}_low"] = "N/A"

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


def get_groq_analysis(prices: dict, news: str) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        gold_price = prices.get("gold_price", "N/A")
        gold_change = prices.get("gold_change", "N/A")
        gold_high = prices.get("gold_high", "N/A")
        gold_low = prices.get("gold_low", "N/A")
        sp500_price = prices.get("sp500_price", "N/A")
        sp500_change = prices.get("sp500_change", "N/A")
        sp500_high = prices.get("sp500_high", "N/A")
        sp500_low = prices.get("sp500_low", "N/A")

        change_fmt = lambda v: f"{v:+.2f}" if isinstance(v, float) else str(v)

        user_prompt = f"""Analyze the following market data and news. Provide a comprehensive morning briefing.

CURRENT PRICES:
Gold (XAU/USD): {gold_price} USD | Change: {change_fmt(gold_change)}% | High: {gold_high} | Low: {gold_low}
S&P 500: {sp500_price} | Change: {change_fmt(sp500_change)}% | High: {sp500_high} | Low: {sp500_low}

LATEST NEWS:
{news}

Please provide:
1. Overall market sentiment (Bullish/Bearish/Neutral) with reasoning
2. Gold Analysis:
   - Trend direction and strength
   - Key support levels (2 levels)
   - Key resistance levels (2 levels)
   - Best entry zone for today
   - Risk factors to watch
3. S&P 500 Analysis:
   - Trend direction
   - Key support levels (2 levels)
   - Key resistance levels (2 levels)
   - Market outlook for today
4. Top 3 most important news items affecting markets today
5. Overall recommendation and risk warning

Write the entire response in Thai language. Be specific with price numbers."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert financial analyst specializing in gold (XAU/USD) and US stock markets. "
                        "Your job is to analyze current market data and news to provide actionable trading insights. "
                        "Always be specific with price levels. Format your response in a clear, structured way. "
                        "Use emojis sparingly but effectively. Write in Thai language. "
                        "Do NOT use any Markdown formatting such as ** or * for bold/italic. Use plain text only."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.3,
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"  Warning: Groq API failed: {e}")
        return f"⚠️ การวิเคราะห์ AI ไม่สำเร็จ: {e}\n\nข้อมูลราคาแสดงอยู่ด้านบน กรุณาวิเคราะห์เองจากข้อมูลดิบ"


def build_line_message(prices: dict, analysis: str) -> str:
    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    date_str = now_bangkok.strftime("%d %b %Y")

    gold_price = prices.get("gold_price", "N/A")
    gold_change = prices.get("gold_change", "N/A")
    sp500_price = prices.get("sp500_price", "N/A")
    sp500_change = prices.get("sp500_change", "N/A")

    def fmt_change(v):
        if isinstance(v, float):
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.2f}%"
        return str(v)

    gold_price_fmt = f"${gold_price:,.2f}" if isinstance(gold_price, float) else str(gold_price)
    sp500_price_fmt = f"{sp500_price:,.2f}" if isinstance(sp500_price, float) else str(sp500_price)

    time_str = now_bangkok.strftime("%H:%M")
    message = (
        f"📊 Daily Market Briefing\n"
        f"📅 {date_str} | ⏰ {time_str} (Bangkok Time)\n\n"
        f"💰 GOLD (XAU/USD): {gold_price_fmt} ({fmt_change(gold_change)})\n"
        f"📈 S&P 500: {sp500_price_fmt} ({fmt_change(sp500_change)})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{analysis}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ This is AI-generated analysis. Not financial advice. Trade at your own risk."
    )
    return message


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

    # LINE text message limit is 5000 characters; split if needed
    max_len = 5000
    chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)]

    for i, chunk in enumerate(chunks):
        try:
            response = requests.post(
                url,
                headers=headers,
                json={
                    "to": user_id,
                    "messages": [{"type": "text", "text": chunk}],
                },
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
