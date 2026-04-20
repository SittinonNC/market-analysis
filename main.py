import os
import time
import datetime
import pytz
import requests
import feedparser
import yfinance as yf
from groq import Groq
from config import PORTFOLIO
from technicals import fetch_all_indicators, format_indicators

BANGKOK_TZ = pytz.timezone('Asia/Bangkok')

RSS_FEEDS = [
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/rss/topstories"),
    ("Investing.com Gold", "https://www.investing.com/rss/news_14.rss"),
]

MAG7 = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "TSLA": "Tesla",
}

WATCHLIST = {
    "ASTS": "AST SpaceMobile",
    "UNH": "UnitedHealth",
    "EOSE": "Eos Energy",
    "RKLB": "Rocket Lab",
    "OKLO": "Oklo",
    "ONDS": "Ondas Holdings",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def fmt_change(v):
    if isinstance(v, float):
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    return str(v)


def fmt_price(v, prefix="$"):
    if isinstance(v, float):
        return f"{prefix}{v:,.2f}"
    return str(v)


def arrow(v):
    if isinstance(v, float):
        return "▲" if v >= 0 else "▼"
    return "•"


# ── Price Fetching ────────────────────────────────────────────────────────────

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

    # Core indices & commodities
    core = {
        "gold": "GC=F",
        "sp500": "^GSPC",
        "dxy": "DX-Y.NYB",
        "vix": "^VIX",
        "btc": "BTC-USD",
        "eth": "ETH-USD",
    }
    for key, symbol in core.items():
        try:
            data = fetch_single(symbol)
            prices[key] = data
            print(f"  {symbol}: {data['price']} ({data['change']:+.2f}%)")
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


# ── Fear & Greed ──────────────────────────────────────────────────────────────

def fetch_fear_greed() -> dict:
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        fg = data["fear_and_greed"]
        score = round(fg["score"], 1)
        rating = fg["rating"]
        print(f"  Fear & Greed: {score} ({rating})")
        return {"score": score, "rating": rating}
    except Exception as e:
        print(f"  Warning: Failed to fetch Fear & Greed: {e}")
        return {"score": "N/A", "rating": "N/A"}


# ── Economic Calendar ─────────────────────────────────────────────────────────

def fetch_economic_calendar() -> list:
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        today_str = datetime.datetime.now(BANGKOK_TZ).strftime("%Y-%m-%d")
        high_impact = [
            e for e in events
            if e.get("country") == "USD"
            and e.get("impact") == "High"
            and e.get("date", "").startswith(today_str)
        ]
        print(f"  Economic calendar: {len(high_impact)} high-impact USD events today")
        return high_impact
    except Exception as e:
        print(f"  Warning: Failed to fetch economic calendar: {e}")
        return []


# ── Portfolio P&L ─────────────────────────────────────────────────────────────

def calculate_portfolio_pnl(prices: dict) -> dict:
    pnl = {}
    total_value = 0.0
    total_cost = 0.0
    has_holdings = False

    all_stocks = {**{s: prices["mag7"][s] for s in prices["mag7"]},
                  **{s: prices["watchlist"][s] for s in prices["watchlist"]}}

    for symbol, holding in PORTFOLIO.items():
        if symbol == "GOLD_OZ":
            shares = holding.get("oz", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            current_price = prices["gold"]["price"]
        else:
            shares = holding.get("shares", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            current_price = all_stocks.get(symbol, {}).get("price", "N/A")

        if shares == 0 or avg_cost == 0:
            continue

        has_holdings = True

        if not isinstance(current_price, float):
            pnl[symbol] = {"value": "N/A", "cost": shares * avg_cost, "gain": "N/A", "gain_pct": "N/A"}
            continue

        cost = shares * avg_cost
        value = shares * current_price
        gain = value - cost
        gain_pct = (gain / cost) * 100 if cost else 0.0

        pnl[symbol] = {
            "shares": shares,
            "avg_cost": avg_cost,
            "current_price": current_price,
            "value": value,
            "cost": cost,
            "gain": gain,
            "gain_pct": gain_pct,
        }
        total_value += value
        total_cost += cost

    if has_holdings:
        pnl["__total__"] = {
            "value": total_value,
            "cost": total_cost,
            "gain": total_value - total_cost,
            "gain_pct": ((total_value - total_cost) / total_cost * 100) if total_cost else 0.0,
        }

    return pnl


# ── News ──────────────────────────────────────────────────────────────────────

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

    return "\n\n".join(articles)[:3000]


# ── Groq Analysis ─────────────────────────────────────────────────────────────

def build_technical_context(prices: dict, technicals: dict) -> str:
    """Build technical analysis section for all symbols."""
    all_symbols = {
        "GC=F": ("gold", "Gold (XAU/USD)"),
        "^GSPC": ("sp500", "S&P 500"),
        "BTC-USD": ("btc", "Bitcoin"),
        "ETH-USD": ("eth", "Ethereum"),
    }
    mag7_map = {s: s for s in ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"]}
    watch_map = {s: s for s in ["ASTS", "UNH", "EOSE", "RKLB", "OKLO", "ONDS"]}

    lines = []

    for symbol, (price_key, label) in all_symbols.items():
        ind = technicals.get(symbol, {})
        price = prices.get(price_key, {}).get("price", 0)
        current_price = price if isinstance(price, float) else 0
        lines.append(format_indicators(label, ind, current_price))
        lines.append("")

    lines.append("── Magnificent 7 ──")
    for symbol in mag7_map:
        ind = technicals.get(symbol, {})
        price = prices["mag7"].get(symbol, {}).get("price", 0)
        current_price = price if isinstance(price, float) else 0
        lines.append(format_indicators(symbol, ind, current_price))
        lines.append("")

    lines.append("── Watchlist ──")
    for symbol in watch_map:
        ind = technicals.get(symbol, {})
        price = prices["watchlist"].get(symbol, {}).get("price", 0)
        current_price = price if isinstance(price, float) else 0
        lines.append(format_indicators(symbol, ind, current_price))
        lines.append("")

    return "\n".join(lines)


def build_price_context(prices: dict, fear_greed: dict) -> str:
    gold = prices["gold"]
    sp500 = prices["sp500"]
    dxy = prices["dxy"]
    vix = prices["vix"]
    btc = prices["btc"]
    eth = prices["eth"]

    lines = [
        f"Fear & Greed Index: {fear_greed['score']} ({fear_greed['rating']})",
        f"VIX: {fmt_price(vix['price'], prefix='')} ({fmt_change(vix['change'])})",
        f"DXY (US Dollar): {fmt_price(dxy['price'], prefix='')} ({fmt_change(dxy['change'])})",
        "",
        f"Gold (XAU/USD): {fmt_price(gold['price'])} | Change: {fmt_change(gold['change'])} | High: {gold['high']} | Low: {gold['low']}",
        f"S&P 500: {fmt_price(sp500['price'], prefix='')} | Change: {fmt_change(sp500['change'])} | High: {sp500['high']} | Low: {sp500['low']}",
        "",
        f"BTC: {fmt_price(btc['price'])} ({fmt_change(btc['change'])})",
        f"ETH: {fmt_price(eth['price'])} ({fmt_change(eth['change'])})",
        "",
        "Magnificent 7:",
    ]
    for symbol, d in prices["mag7"].items():
        lines.append(f"  {symbol} ({d['name']}): {fmt_price(d['price'])} | Change: {fmt_change(d['change'])}")

    lines += ["", "Watchlist:"]
    for symbol, d in prices["watchlist"].items():
        lines.append(f"  {symbol} ({d['name']}): {fmt_price(d['price'])} | Change: {fmt_change(d['change'])}")

    return "\n".join(lines)


def get_groq_analysis(prices: dict, fear_greed: dict, calendar: list, news: str, technicals: dict) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        price_context = build_price_context(prices, fear_greed)
        technical_context = build_technical_context(prices, technicals)

        calendar_text = ""
        if calendar:
            cal_lines = ["High-Impact USD Events Today:"]
            for e in calendar:
                cal_lines.append(f"  {e.get('time','?')} - {e.get('title','?')} | Forecast: {e.get('forecast','?')} | Previous: {e.get('previous','?')}")
            calendar_text = "\n".join(cal_lines)
        else:
            calendar_text = "No high-impact USD economic events today."

        user_prompt = f"""Analyze the following market data and technical indicators. Provide a comprehensive briefing.

MARKET DATA (Price + Macro):
{price_context}

TECHNICAL INDICATORS (RSI, MACD, Bollinger Bands, EMA, ATR):
{technical_context}

ECONOMIC CALENDAR:
{calendar_text}

LATEST NEWS:
{news}

Please provide a precise analysis using BOTH price data AND technical indicators:

1. Overall market sentiment (Bullish/Bearish/Neutral)
   - Reference Fear & Greed, VIX, DXY, and overall EMA/MACD signals

2. Gold (XAU/USD) — Full Technical Analysis:
   - Trend direction (based on EMA alignment)
   - RSI and MACD interpretation
   - Bollinger Band position
   - Support (2 levels from BB lower + EMA) and Resistance (2 levels from BB upper + EMA)
   - ACTION SIGNAL: BUY or SELL (must be clearly stated)
   - If BUY: exact entry zone + stop loss (use ATR) + take profit target
   - If SELL: exact exit price + stop loss (use ATR) + downside target
   - Key risk factors

3. S&P 500 — Technical Analysis:
   - EMA trend, RSI, MACD interpretation
   - Support and Resistance (2 each)
   - Best entry zone today with stop loss

4. Crypto (BTC & ETH):
   - RSI and MACD for each
   - Recommended entry zone with stop loss

5. Magnificent 7 — for each (AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA):
   - RSI signal + MACD trend
   - EMA position (bullish/bearish)
   - Recommended buy entry zone

6. Watchlist — for each (ASTS, UNH, EOSE, RKLB, OKLO, ONDS):
   - RSI signal + MACD trend
   - Recommended buy entry zone

7. Economic Calendar: which events today could move markets and direction

8. Top 3 most important news affecting markets

9. Overall recommendation and risk warning

Write entirely in Thai language. Always reference specific indicator values when giving entry/exit levels."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert quantitative financial analyst specializing in gold, US equities, crypto, and macro indicators. "
                        "You have access to real technical indicators: RSI, MACD, Bollinger Bands, EMA (20/50/200), and ATR. "
                        "Always use these indicator values to support your BUY/SELL signals and entry/exit levels. "
                        "Use ATR for stop loss calculation. Use Bollinger Bands for support/resistance. "
                        "Use RSI for overbought/oversold. Use MACD for momentum and crossover signals. "
                        "Use EMA alignment for trend direction. "
                        "Write in Thai language. Do NOT use Markdown formatting like ** or *. Plain text only."
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
        return f"⚠️ การวิเคราะห์ AI ไม่สำเร็จ: {e}\n\nกรุณาดูข้อมูลราคาด้านบนและวิเคราะห์เองครับ"


# ── Build Message ─────────────────────────────────────────────────────────────

def build_line_message(prices: dict, fear_greed: dict, calendar: list, pnl: dict, analysis: str) -> str:
    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    date_str = now_bangkok.strftime("%d %b %Y")
    time_str = now_bangkok.strftime("%H:%M")

    gold = prices["gold"]
    sp500 = prices["sp500"]
    dxy = prices["dxy"]
    vix = prices["vix"]
    btc = prices["btc"]
    eth = prices["eth"]

    fg_score = fear_greed["score"]
    fg_rating = fear_greed["rating"]

    lines = [
        "📊 Daily Market Briefing",
        f"📅 {date_str} | ⏰ {time_str} (Bangkok Time)",
        "",
        "── Market Indicators ──",
        f"😱 Fear & Greed: {fg_score} — {fg_rating}",
        f"📉 VIX: {fmt_price(vix['price'], prefix='')} ({fmt_change(vix['change'])})",
        f"💵 DXY: {fmt_price(dxy['price'], prefix='')} ({fmt_change(dxy['change'])})",
        "",
        "── Commodities & Indices ──",
        f"💰 GOLD: {fmt_price(gold['price'])} ({fmt_change(gold['change'])})",
        f"📈 S&P 500: {fmt_price(sp500['price'], prefix='')} ({fmt_change(sp500['change'])})",
        "",
        "── Crypto ──",
        f"{arrow(btc['change'])} BTC: {fmt_price(btc['price'])} ({fmt_change(btc['change'])})",
        f"{arrow(eth['change'])} ETH: {fmt_price(eth['price'])} ({fmt_change(eth['change'])})",
        "",
        "── Magnificent 7 ──",
    ]

    for symbol, d in prices["mag7"].items():
        lines.append(f"{arrow(d['change'])} {symbol}: {fmt_price(d['price'])} ({fmt_change(d['change'])})")

    lines += ["", "── Watchlist ──"]
    for symbol, d in prices["watchlist"].items():
        lines.append(f"{arrow(d['change'])} {symbol}: {fmt_price(d['price'])} ({fmt_change(d['change'])})")

    # Portfolio P&L
    if pnl and "__total__" in pnl:
        total = pnl["__total__"]
        gain_emoji = "📈" if total["gain"] >= 0 else "📉"
        lines += [
            "",
            "── Portfolio P&L ──",
        ]
        for symbol, data in pnl.items():
            if symbol == "__total__":
                continue
            if isinstance(data.get("gain"), float):
                g_emoji = "▲" if data["gain"] >= 0 else "▼"
                lines.append(
                    f"{g_emoji} {symbol}: ${data['current_price']:,.2f} | "
                    f"P&L: ${data['gain']:+,.2f} ({data['gain_pct']:+.2f}%)"
                )
        lines.append(
            f"{gain_emoji} รวม: ${total['value']:,.2f} | กำไร/ขาดทุน: ${total['gain']:+,.2f} ({total['gain_pct']:+.2f}%)"
        )

    # Economic Calendar
    if calendar:
        lines += ["", "── Economic Calendar (วันนี้) ──"]
        for e in calendar:
            lines.append(f"⏰ {e.get('time','?')} | {e.get('title','?')} | Forecast: {e.get('forecast','?')}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        analysis,
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ AI-generated analysis. Not financial advice. Trade at your own risk.",
    ]

    return "\n".join(lines)


# ── Send LINE ─────────────────────────────────────────────────────────────────

def send_line(message: str):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")

    if not token or not user_id:
        print("  Error: LINE_CHANNEL_ACCESS_TOKEN or LINE_USER_ID not set")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    max_len = 5000
    chunks = [message[i:i + max_len] for i in range(0, len(message), max_len)]

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json={"to": user_id, "messages": [{"type": "text", "text": chunk}]},
                timeout=30,
            )
            resp.raise_for_status()
            print(f"  LINE chunk {i + 1}/{len(chunks)} sent successfully")
        except requests.exceptions.HTTPError as e:
            print(f"  Error sending LINE chunk {i + 1}: {e} — {resp.text}")
        except Exception as e:
            print(f"  Error sending LINE chunk {i + 1}: {e}")

        if i < len(chunks) - 1:
            time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[1/7] Fetching prices...")
    prices = fetch_prices()

    print("[2/7] Fetching Fear & Greed Index...")
    fear_greed = fetch_fear_greed()

    print("[3/7] Fetching economic calendar...")
    calendar = fetch_economic_calendar()

    print("[4/7] Fetching news...")
    news = fetch_news()

    print("[5/7] Computing technical indicators (RSI, MACD, BB, EMA, ATR)...")
    all_symbols = (
        ["GC=F", "^GSPC", "DX-Y.NYB", "^VIX", "BTC-USD", "ETH-USD"]
        + list(MAG7.keys())
        + list(WATCHLIST.keys())
    )
    technicals = fetch_all_indicators(all_symbols, period="1y")

    print("[6/7] Calculating portfolio P&L...")
    pnl = calculate_portfolio_pnl(prices)

    print("[7/7] Calling Groq API...")
    analysis = get_groq_analysis(prices, fear_greed, calendar, news, technicals)

    message = build_line_message(prices, fear_greed, calendar, pnl, analysis)
    send_line(message)

    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    print(f"\n✅ Done at {now_bangkok.strftime('%Y-%m-%d %H:%M:%S')} Bangkok time")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
