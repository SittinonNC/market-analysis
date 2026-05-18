import os
import re
import math
import time
import datetime
import pytz
import requests
import feedparser
import yfinance as yf
from bs4 import BeautifulSoup
from groq import Groq
from config import PORTFOLIO, FINANCIAL_GOALS, TARGET_ALLOCATION
from technicals import fetch_all_indicators, format_indicators
from line_flex import build_market_bubble, build_portfolio_bubble, send_flex, send_text

# Truth Social: username → known account ID (fallback if RSS fails)
TRUTH_SOCIAL_ACCOUNTS = [
    "realDonaldTrump",
]

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

def fetch_economic_calendar() -> dict:
    """ดึง ForexFactory Calendar — วันนี้ทุกสกุล + 3 วันข้างหน้า USD"""
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        events = resp.json()

        now = datetime.datetime.now(BANGKOK_TZ)
        today_str = now.strftime("%Y-%m-%d")
        major_currencies = {"USD", "EUR", "GBP", "JPY", "CNY", "AUD", "CAD"}

        today_events = [
            e for e in events
            if e.get("impact") == "High"
            and e.get("country") in major_currencies
            and e.get("date", "").startswith(today_str)
        ]

        upcoming_events = []
        for day_offset in range(1, 4):
            future_str = (now + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
            upcoming_events += [
                e for e in events
                if e.get("impact") == "High"
                and e.get("country") == "USD"
                and e.get("date", "").startswith(future_str)
            ]

        print(f"  ForexFactory calendar: {len(today_events)} today, {len(upcoming_events)} upcoming (3-day USD)")
        return {"today": today_events, "upcoming": upcoming_events}
    except Exception as e:
        print(f"  Warning: Failed to fetch ForexFactory calendar: {e}")
        return {"today": [], "upcoming": []}


def fetch_forexfactory_news() -> str:
    """Scrape Flash News จาก ForexFactory (best-effort — JS-heavy site)"""
    try:
        url = "https://www.forexfactory.com/news"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        headlines = []

        # ลอง selector หลายแบบ เพราะ ForexFactory อาจเปลี่ยน HTML structure
        for item in soup.select(".flashes__item, .news__item, .flash-item, article.news")[:10]:
            text = item.get_text(separator=" ", strip=True)
            if len(text) > 20:
                headlines.append(text[:300])

        # Fallback: ดึง <h3>/<h4> ถ้าไม่เจอ container
        if not headlines:
            for tag in soup.find_all(["h3", "h4"])[:10]:
                t = tag.get_text(strip=True)
                if len(t) > 15:
                    headlines.append(t)

        # Fallback สุดท้าย: ดึง meta description
        if not headlines:
            for meta in soup.find_all("meta", attrs={"name": "description"})[:3]:
                content = meta.get("content", "").strip()
                if len(content) > 20:
                    headlines.append(content[:300])

        result = "\n".join(f"• {h}" for h in headlines)
        print(f"  ForexFactory news: {len(headlines)} items scraped")
        return result if result else ""
    except Exception as e:
        print(f"  Warning: ForexFactory news scraping failed: {e}")
        return ""


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


# ── Portfolio Allocation & Financial Planning ─────────────────────────────────

def calculate_allocation(pnl: dict) -> dict:
    """คำนวณ % allocation ปัจจุบันแต่ละ asset class vs TARGET_ALLOCATION"""
    total = pnl.get("__total__", {}).get("value", 0.0)
    if not isinstance(total, float) or total == 0:
        return {}

    mag7_symbols = set(MAG7.keys())
    watch_symbols = set(WATCHLIST.keys())
    class_values = {"mag7": 0.0, "watchlist": 0.0, "crypto": 0.0, "gold": 0.0}

    for symbol, data in pnl.items():
        if symbol == "__total__":
            continue
        val = data.get("value", 0.0)
        if not isinstance(val, float):
            continue
        if symbol in mag7_symbols:
            class_values["mag7"] += val
        elif symbol == "GOLD_OZ":
            class_values["gold"] += val
        elif symbol in watch_symbols:
            class_values["watchlist"] += val
        # crypto ใน portfolio จริงยังไม่มี → 0

    result = {}
    for cls, val in class_values.items():
        current_pct = (val / total * 100) if total else 0.0
        target_pct = TARGET_ALLOCATION.get(cls, 0)
        diff = current_pct - target_pct
        if diff > 2:
            status = "Overweight"
        elif diff < -2:
            status = "Underweight"
        else:
            status = "On Target"
        result[cls] = {
            "value": val,
            "current_pct": round(current_pct, 1),
            "target_pct": target_pct,
            "diff": round(diff, 1),
            "status": status,
        }

    result["__total__"] = total
    return result


def build_portfolio_planning_context(pnl: dict, allocation: dict) -> str:
    """สร้าง context สำหรับ Groq prompt — portfolio planning"""
    if not allocation or "__total__" not in allocation:
        return "ไม่มีข้อมูลพอร์ต"

    total_val = allocation["__total__"]
    goal = FINANCIAL_GOALS
    target_val = goal["target_portfolio_value"]
    target_date = goal["target_date"]
    monthly = goal["monthly_investment"]
    risk = goal["risk_profile"]

    lines = [
        f"Total Portfolio Value: ${total_val:,.2f}",
        f"Goal: ${target_val:,.0f} by {target_date} | Monthly Investment: ${monthly}/mo | Risk Profile: {risk}",
        "",
        "Current Allocation vs Target:",
    ]
    for cls, d in allocation.items():
        if cls == "__total__":
            continue
        lines.append(
            f"  {cls:12s}: {d['current_pct']:5.1f}% (target {d['target_pct']}%) "
            f"→ {d['status']} ({d['diff']:+.1f}%)"
        )

    if isinstance(target_val, (int, float)) and target_val > total_val > 0:
        gap = target_val - total_val
        annual_rate = 0.10
        monthly_rate = annual_rate / 12
        if monthly > 0:
            try:
                n = math.log((gap * monthly_rate / monthly) + 1) / math.log(1 + monthly_rate)
                est_years = round(n / 12, 1)
            except (ValueError, ZeroDivisionError):
                est_years = None
        else:
            est_years = None
        progress_pct = total_val / target_val * 100
        lines += [
            "",
            f"Progress: ${total_val:,.0f} / ${target_val:,.0f} ({progress_pct:.1f}%)",
        ]
        if est_years is not None:
            lines.append(
                f"Estimated to reach goal: ~{est_years} yrs "
                f"(assuming 10% annual return + ${monthly}/mo contributions)"
            )

    return "\n".join(lines)


# ── Truth Social ──────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_truth_social(username: str, limit: int = 5) -> list:
    posts = []
    try:
        rss_url = f"https://truthsocial.com/@{username}.rss"
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:limit]:
            content = strip_html(entry.get("summary", entry.get("title", "")))
            date = entry.get("published", "")[:10]
            if content:
                posts.append(f"[Truth Social @{username} {date}] {content[:500]}")
        print(f"  Fetched {len(posts)} posts from Truth Social @{username}")
    except Exception as e:
        print(f"  Warning: Truth Social @{username} failed: {e}")
    return posts


def fetch_all_truth_social() -> str:
    all_posts = []
    for username in TRUTH_SOCIAL_ACCOUNTS:
        all_posts.extend(fetch_truth_social(username))
    return "\n\n".join(all_posts)


# ── News ──────────────────────────────────────────────────────────────────────

def fetch_news() -> str:
    articles = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:5]
            for entry in entries:
                title = entry.get("title", "No title").strip()

                # Try to get full content first, fall back to summary
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = strip_html(entry.content[0].get("value", ""))
                if not content:
                    content = strip_html(entry.get("summary", entry.get("description", "")))

                content = content[:600] if content else ""
                articles.append(f"[{source_name}]\nหัวข้อ: {title}\nเนื้อหา: {content}")
            print(f"  Fetched {len(entries)} articles from {source_name}")
        except Exception as e:
            print(f"  Warning: Failed to fetch {source_name}: {e}")

    return "\n\n".join(articles)[:6000]


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


def get_groq_analysis(
    prices: dict,
    fear_greed: dict,
    calendar: dict,
    news: str,
    truth_posts: str,
    technicals: dict,
    ff_news: str = "",
    allocation: dict = None,
) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        price_context = build_price_context(prices, fear_greed)
        technical_context = build_technical_context(prices, technicals)

        # ── ForexFactory Calendar ────────────────────────────────
        today_events = calendar.get("today", [])
        upcoming_events = calendar.get("upcoming", [])

        if today_events:
            cal_lines = ["วันนี้ — High-Impact (USD/EUR/GBP/JPY/CNY/AUD/CAD):"]
            for e in today_events:
                cal_lines.append(
                    f"  [{e.get('country','?')}] {e.get('time','?')} {e.get('title','?')} "
                    f"| Forecast: {e.get('forecast','?')} | Previous: {e.get('previous','?')}"
                )
        else:
            cal_lines = ["วันนี้: ไม่มี High-Impact events"]

        if upcoming_events:
            cal_lines.append("3 วันข้างหน้า — High-Impact USD:")
            for e in upcoming_events:
                cal_lines.append(
                    f"  {e.get('date','?')[:10]} {e.get('title','?')} "
                    f"| Forecast: {e.get('forecast','?')} | Previous: {e.get('previous','?')}"
                )
        calendar_text = "\n".join(cal_lines)

        # ── ForexFactory News ────────────────────────────────────
        ff_news_section = (
            f"FOREXFACTORY NEWS:\n{ff_news}" if ff_news.strip()
            else "FOREXFACTORY NEWS:\nไม่สามารถดึงข่าวได้ (JS-rendered site)"
        )

        # ── Portfolio Planning ───────────────────────────────────
        portfolio_planning = (
            build_portfolio_planning_context({}, allocation)
            if allocation
            else "ไม่มีข้อมูลพอร์ต"
        )

        # ── Truth Social ─────────────────────────────────────────
        truth_section = f"\nTRUTH SOCIAL POSTS (Trump):\n{truth_posts}" if truth_posts.strip() else ""

        user_prompt = f"""Analyze the following market data and technical indicators. Format your response EXACTLY as shown in the template below. Use plain text only — no **, no #, no markdown.

MARKET DATA:
{price_context}

TECHNICAL INDICATORS:
{technical_context}

FOREXFACTORY CALENDAR:
{calendar_text}

{ff_news_section}
{truth_section}
LATEST NEWS (full content from all sources):
{news}

PORTFOLIO FINANCIAL PLANNING:
{portfolio_planning}

OUTPUT FORMAT (follow this structure exactly, write content in Thai):

════════════════════
📊 ภาพรวมตลาด
════════════════════
ความเชื่อมั่น: [Bullish/Bearish/Neutral]
เหตุผล: [อธิบาย 1-2 ประโยค อ้างอิง Fear&Greed VIX DXY EMA MACD]

════════════════════
💰 ทองคำ (XAU/USD)
════════════════════
แนวโน้ม: [ทิศทาง + EMA alignment]
RSI: [ค่า] → [สัญญาณ] | MACD: [Bullish/Bearish] | BB: [ตำแหน่ง]
แนวรับ: [ระดับ 1] / [ระดับ 2]
แนวต้าน: [ระดับ 1] / [ระดับ 2]

[🟢 สัญญาณ: BUY  หรือ  🔴 สัญญาณ: SELL]
จุดเข้า: $[ราคา] – $[ราคา]
Stop Loss: $[ราคา]  (ATR=[ค่า])
เป้าหมาย: $[ราคา]
ความเสี่ยง: [ปัจจัยเสี่ยง 1 ประโยค]

════════════════════
📈 S&P 500
════════════════════
แนวโน้ม: [ทิศทาง + EMA]
RSI: [ค่า] → [สัญญาณ] | MACD: [Bullish/Bearish]
แนวรับ: [ระดับ 1] / [ระดับ 2]
แนวต้าน: [ระดับ 1] / [ระดับ 2]
จุดเข้า: [ระดับ] | Stop Loss: [ระดับ]

════════════════════
₿ Crypto
════════════════════
BTC — RSI: [ค่า] | MACD: [สัญญาณ]
จุดเข้า: $[ราคา] | Stop Loss: $[ราคา]

ETH — RSI: [ค่า] | MACD: [สัญญาณ]
จุดเข้า: $[ราคา] | Stop Loss: $[ราคา]

════════════════════
🏆 Magnificent 7
════════════════════
AAPL  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
MSFT  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
NVDA  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
AMZN  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
META  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
GOOGL RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
TSLA  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]

════════════════════
👁 Watchlist
════════════════════
ASTS  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
UNH   RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
EOSE  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
RKLB  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
OKLO  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]
ONDS  RSI:[ค่า] MACD:[สัญญาณ] เข้า:$[ราคา]–$[ราคา]

════════════════════
🏦 ForexFactory Calendar & Upcoming Events
════════════════════
วันนี้ (High-Impact ทุกสกุล):
[event] — [สกุลเงิน] — ผลคาด: [Bullish/Bearish/Mixed ต่อ USD/ตลาด]
[ถ้าไม่มี: ไม่มีข้อมูลเศรษฐกิจสำคัญวันนี้]

สัปดาห์นี้ USD สำคัญ (upcoming):
[event] — [วัน] — คาดว่าจะกระทบ [อธิบายสั้น]
[ถ้าไม่มี: ไม่มี USD events สำคัญใน 3 วันข้างหน้า]

════════════════════
🐦 Trump Truth Social
════════════════════
[สรุปโพสต์ล่าสุดของ Trump ที่เกี่ยวกับเศรษฐกิจ/ตลาด/นโยบาย]
ผลต่อตลาด: [🟢 Bullish / 🔴 Bearish / 🟡 Neutral] — [เหตุผล 1 ประโยค]
[ถ้าไม่มีโพสต์ที่เกี่ยวข้อง: ไม่มีโพสต์ที่กระทบตลาดล่าสุด]

════════════════════
📰 วิเคราะห์ข่าวทุกแหล่ง
════════════════════
รวมข่าวจากทุกแหล่ง วิเคราะห์และสรุปภาพรวม:

ข่าวที่ 1:
หัวข้อ: [ชื่อข่าว] — [แหล่งข่าว]
สรุป: [สรุปเนื้อหาสำคัญ 2-3 ประโยค]
ผลต่อตลาด: [🟢 ข่าวดี / 🔴 ข่าวร้าย / 🟡 Neutral]
กระทบ: [ระบุหุ้น/สินทรัพย์ที่ได้รับผลกระทบ]

ข่าวที่ 2:
หัวข้อ: [ชื่อข่าว] — [แหล่งข่าว]
สรุป: [สรุปเนื้อหาสำคัญ 2-3 ประโยค]
ผลต่อตลาด: [🟢 ข่าวดี / 🔴 ข่าวร้าย / 🟡 Neutral]
กระทบ: [ระบุหุ้น/สินทรัพย์ที่ได้รับผลกระทบ]

ข่าวที่ 3:
หัวข้อ: [ชื่อข่าว] — [แหล่งข่าว]
สรุป: [สรุปเนื้อหาสำคัญ 2-3 ประโยค]
ผลต่อตลาด: [🟢 ข่าวดี / 🔴 ข่าวร้าย / 🟡 Neutral]
กระทบ: [ระบุหุ้น/สินทรัพย์ที่ได้รับผลกระทบ]

ภาพรวมข่าววันนี้: [🟢 Bullish dominant / 🔴 Bearish dominant / 🟡 Mixed] — [สรุป 1 ประโยค]

════════════════════
💼 วิเคราะห์พอร์ต & วางแผนการเงิน
════════════════════
Allocation ปัจจุบัน vs เป้าหมาย:
mag7    : [XX%] (เป้า [YY%]) → [Overweight/Underweight/On Target]
watchlist: [XX%] (เป้า [YY%]) → [Overweight/Underweight/On Target]
crypto  : [XX%] (เป้า [YY%]) → [Overweight/Underweight/On Target]
gold    : [XX%] (เป้า [YY%]) → [Overweight/Underweight/On Target]

Rebalancing แนะนำ:
[ซื้อ/ขาย/ถือ อะไร เท่าไหร่ อิงจาก allocation ปัจจุบัน vs target]

ความคืบหน้าสู่เป้าหมาย:
มูลค่าปัจจุบัน: $[X,XXX] | เป้า: $[XX,XXX] ภายใน [YYYY]
ประมาณถึงเป้า: ~[X] ปี (ลงทุน $[X]/เดือน + ผลตอบแทน 10%/ปี)

คำแนะนำ: [2-3 ประโยค อิง risk profile และสภาพตลาดปัจจุบัน]

════════════════════
⚡ สรุปคำแนะนำ
════════════════════
[สรุป 2-3 ประโยค พร้อมคำเตือนความเสี่ยง]"""

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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[1/9] Fetching prices...")
    prices = fetch_prices()

    print("[2/9] Fetching Fear & Greed Index...")
    fear_greed = fetch_fear_greed()

    print("[3/9] Fetching ForexFactory calendar...")
    calendar = fetch_economic_calendar()

    print("[4/9] Fetching news (RSS feeds)...")
    news = fetch_news()

    print("[4.5/9] Fetching Truth Social posts...")
    truth_posts = fetch_all_truth_social()

    print("[5/9] Fetching ForexFactory news...")
    ff_news = fetch_forexfactory_news()

    print("[5.5/9] Computing technical indicators (RSI, MACD, BB, EMA, ATR)...")
    all_symbols = (
        ["GC=F", "^GSPC", "DX-Y.NYB", "^VIX", "BTC-USD", "ETH-USD"]
        + list(MAG7.keys())
        + list(WATCHLIST.keys())
    )
    technicals = fetch_all_indicators(all_symbols, period="1y")

    print("[6/9] Calculating portfolio P&L...")
    pnl = calculate_portfolio_pnl(prices)

    print("[6.5/9] Calculating portfolio allocation...")
    allocation = calculate_allocation(pnl)

    print("[7/9] Calling Groq API...")
    analysis = get_groq_analysis(
        prices, fear_greed, calendar, news, truth_posts, technicals,
        ff_news=ff_news, allocation=allocation,
    )

    now_bangkok = datetime.datetime.now(BANGKOK_TZ)
    date_str = now_bangkok.strftime("%d %b %Y")
    time_str = now_bangkok.strftime("%H:%M")

    print("[8/9] Sending Flex bubbles to LINE...")
    send_flex(
        f"📊 Market Briefing {date_str} {time_str}",
        build_market_bubble(prices, fear_greed, date_str, time_str),
    )
    send_flex(
        f"💼 Portfolio {date_str} {time_str}",
        build_portfolio_bubble(pnl, allocation, calendar, FINANCIAL_GOALS, date_str, time_str),
    )

    print("[9/9] Sending Groq analysis as text...")
    disclaimer = "⚠️ AI-generated analysis. Not financial advice."
    send_text(f"📝 วิเคราะห์ตลาด\n\n{analysis}\n\n{disclaimer}")

    print(f"\n✅ Done at {now_bangkok.strftime('%Y-%m-%d %H:%M:%S')} Bangkok time")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
