"""
portfolio.py — Portfolio Analysis & Financial Planning + News Summary
รันแยกจาก main.py โดยเฉพาะ ส่ง LINE รายงานพอร์ต + วิเคราะห์ข่าว + วางแผนการเงิน
"""

import os
import re
import math
import time
import datetime
import pytz
import requests
import feedparser
import yfinance as yf
from groq import Groq
from config import PORTFOLIO, FINANCIAL_GOALS, TARGET_ALLOCATION
from line_flex import build_portfolio_bubble, send_flex, send_text
from dashboard_data import save_snapshot

BANGKOK_TZ = pytz.timezone("Asia/Bangkok")

MAG7      = {"AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"}
WATCHLIST = {"ASTS", "UNH", "EOSE", "RKLB", "OKLO", "ONDS"}

RSS_FEEDS = [
    ("BBC Business",  "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("CNBC",          "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch",   "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/rss/topstories"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def fmt_price(v, prefix="$"):
    return f"{prefix}{v:,.2f}" if isinstance(v, float) else str(v)

def fmt_pct(v):
    return f"{v:+.2f}%" if isinstance(v, float) else str(v)

# ── Fetch News ────────────────────────────────────────────────────────────────

def fetch_news() -> str:
    articles = []
    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                title = entry.get("title", "").strip()
                summary = strip_html(entry.get("summary", entry.get("description", "")))[:400]
                if title:
                    articles.append(f"[{source_name}] {title}\n{summary}")
            print(f"  News: {len(feed.entries[:4])} from {source_name}")
        except Exception as e:
            print(f"  Warning: {source_name} failed: {e}")
    return "\n\n".join(articles)[:5000]


# ── Fetch Prices ──────────────────────────────────────────────────────────────

def fetch_holding_prices() -> dict:
    """ดึงราคาเฉพาะหุ้นที่ถือ + Gold"""
    prices = {}
    symbols_needed = set()
    for symbol, h in PORTFOLIO.items():
        if symbol == "GOLD_OZ":
            if h.get("oz", 0) > 0:
                symbols_needed.add("GC=F")
        else:
            if h.get("shares", 0) > 0:
                symbols_needed.add(symbol)

    for symbol in symbols_needed:
        try:
            hist = yf.Ticker(symbol).history(period="5d")
            if hist.empty:
                raise ValueError("No data")
            current = round(float(hist["Close"].iloc[-1]), 2)
            prev    = round(float(hist["Close"].iloc[-2]), 2) if len(hist) >= 2 else current
            change_pct = round(((current - prev) / prev) * 100, 2) if prev else 0.0
            prices[symbol] = {"price": current, "change": change_pct}
            print(f"  {symbol}: ${current} ({change_pct:+.2f}%)")
        except Exception as e:
            print(f"  Warning: {symbol} failed: {e}")
            prices[symbol] = {"price": "N/A", "change": "N/A"}
    return prices


# ── P&L ───────────────────────────────────────────────────────────────────────

def calculate_pnl(prices: dict) -> dict:
    pnl = {}
    total_value = total_cost = 0.0

    for symbol, holding in PORTFOLIO.items():
        if symbol == "GOLD_OZ":
            qty      = holding.get("oz", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            price_key = "GC=F"
        else:
            qty      = holding.get("shares", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            price_key = symbol

        if qty == 0 or avg_cost == 0:
            continue

        current_price = prices.get(price_key, {}).get("price", "N/A")
        today_change  = prices.get(price_key, {}).get("change", "N/A")

        if not isinstance(current_price, float):
            pnl[symbol] = {
                "qty": qty, "avg_cost": avg_cost, "current_price": "N/A",
                "value": "N/A", "cost": qty * avg_cost,
                "gain": "N/A", "gain_pct": "N/A", "today_change": "N/A",
            }
            continue

        cost  = qty * avg_cost
        value = qty * current_price
        gain  = value - cost
        gain_pct = (gain / cost * 100) if cost else 0.0

        pnl[symbol] = {
            "qty": qty, "avg_cost": avg_cost, "current_price": current_price,
            "value": value, "cost": cost,
            "gain": gain, "gain_pct": gain_pct, "today_change": today_change,
        }
        total_value += value
        total_cost  += cost

    if total_cost > 0:
        pnl["__total__"] = {
            "value":    total_value,
            "cost":     total_cost,
            "gain":     total_value - total_cost,
            "gain_pct": (total_value - total_cost) / total_cost * 100,
        }
    return pnl


# ── Allocation ────────────────────────────────────────────────────────────────

def calculate_allocation(pnl: dict) -> dict:
    total = pnl.get("__total__", {}).get("value", 0.0)
    if not isinstance(total, float) or total == 0:
        return {}

    class_values = {"mag7": 0.0, "watchlist": 0.0, "crypto": 0.0, "gold": 0.0}
    for symbol, data in pnl.items():
        if symbol == "__total__":
            continue
        val = data.get("value", 0.0)
        if not isinstance(val, float):
            continue
        if symbol in MAG7:
            class_values["mag7"] += val
        elif symbol == "GOLD_OZ":
            class_values["gold"] += val
        elif symbol in WATCHLIST:
            class_values["watchlist"] += val

    result = {}
    for cls, val in class_values.items():
        current_pct = (val / total * 100) if total else 0.0
        target_pct  = TARGET_ALLOCATION.get(cls, 0)
        diff   = current_pct - target_pct
        status = "Overweight" if diff > 2 else ("Underweight" if diff < -2 else "On Target")
        result[cls] = {
            "value": val, "current_pct": round(current_pct, 1),
            "target_pct": target_pct, "diff": round(diff, 1), "status": status,
        }
    result["__total__"] = total
    return result


# ── Context Builders ──────────────────────────────────────────────────────────

def build_pnl_context(pnl: dict) -> str:
    lines = []
    for symbol, d in pnl.items():
        if symbol == "__total__":
            continue
        if isinstance(d.get("gain"), float):
            today = f" | วันนี้: {fmt_pct(d['today_change'])}" if isinstance(d.get("today_change"), float) else ""
            lines.append(
                f"{symbol}: ราคา {fmt_price(d['current_price'])} | ทุน {fmt_price(d['avg_cost'])} | "
                f"P&L {d['gain']:+,.2f} ({fmt_pct(d['gain_pct'])}){today}"
            )
    total = pnl.get("__total__", {})
    if isinstance(total.get("value"), float):
        lines += [
            "",
            f"รวมพอร์ต: {fmt_price(total['value'])} | ต้นทุน: {fmt_price(total['cost'])} | "
            f"P&L: {total['gain']:+,.2f} ({fmt_pct(total['gain_pct'])})",
        ]
    return "\n".join(lines)


def build_allocation_context(allocation: dict) -> str:
    if not allocation or "__total__" not in allocation:
        return "ไม่มีข้อมูล"
    lines = [f"มูลค่าพอร์ตรวม: ${allocation['__total__']:,.2f}", ""]
    for cls in ["mag7", "watchlist", "crypto", "gold"]:
        d = allocation.get(cls)
        if not d:
            continue
        lines.append(
            f"  {cls:12s}: {d['current_pct']:5.1f}% (เป้า {d['target_pct']}%) "
            f"→ {d['status']} ({d['diff']:+.1f}%)"
        )
    return "\n".join(lines)


def build_goals_context(allocation: dict) -> str:
    if not allocation or "__total__" not in allocation:
        return ""
    total_val   = allocation["__total__"]
    target_val  = FINANCIAL_GOALS["target_portfolio_value"]
    monthly     = FINANCIAL_GOALS["monthly_investment"]
    risk        = FINANCIAL_GOALS["risk_profile"]
    target_date = FINANCIAL_GOALS["target_date"]

    lines = [
        f"เป้าหมาย: ${target_val:,.0f} ภายใน {target_date}",
        f"ลงทุนรายเดือน: ${monthly} | Risk: {risk}",
        f"ความคืบหน้า: ${total_val:,.0f} / ${target_val:,.0f} ({total_val/target_val*100:.1f}%)",
    ]
    if target_val > total_val > 0 and monthly > 0:
        gap          = target_val - total_val
        monthly_rate = 0.10 / 12
        try:
            n         = math.log((gap * monthly_rate / monthly) + 1) / math.log(1 + monthly_rate)
            est_years = round(n / 12, 1)
            lines.append(f"ประมาณถึงเป้า: ~{est_years} ปี (ผลตอบแทน 10%/ปี + ${monthly}/เดือน)")
        except (ValueError, ZeroDivisionError):
            pass
    return "\n".join(lines)


# ── Groq Analysis ─────────────────────────────────────────────────────────────

def get_portfolio_analysis(pnl: dict, allocation: dict, news: str) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        user_prompt = f"""วิเคราะห์พอร์ตการลงทุนและข่าวต่อไปนี้ ใช้ภาษาไทยทั้งหมด ห้ามใช้ ** # หรือ Markdown

PORTFOLIO P&L:
{build_pnl_context(pnl)}

ASSET ALLOCATION vs TARGET:
{build_allocation_context(allocation)}

FINANCIAL GOALS:
{build_goals_context(allocation)}

ข่าวตลาดล่าสุด:
{news}

ตอบตาม format นี้เท่านั้น ห้ามเพิ่มข้อความนอก format:

════════════════════
💼 สรุป Portfolio วันนี้
════════════════════
มูลค่ารวม: $[X,XXX.XX] | P&L รวม: $[±X,XXX.XX] ([±X.XX]%)
สถานะ: [ดีขึ้น/แย่ลง/ทรงตัว] เมื่อเทียบกับทุนที่ลงไป
ประเมิน: [ประเมินสั้นๆ ว่าพอร์ตโดยรวมเป็นอย่างไร 1 ประโยค]

════════════════════
📊 วิเคราะห์รายหุ้น
════════════════════
[ทำทุกหุ้นในพอร์ต ตาม format นี้:]
[SYMBOL] [ราคา] — P&L [±$XXX.XX] ([±XX.XX]%)
แนะนำ: [ถือ / ซื้อเพิ่ม / ลดความเสี่ยง]
เหตุผล: [1-2 ประโยค อธิบายว่าทำไม]

════════════════════
⚖️ Rebalancing แนะนำ
════════════════════
Allocation ปัจจุบัน:
mag7     : [XX.X]% (เป้า [XX]%) → [สถานะ]
watchlist: [XX.X]% (เป้า [XX]%) → [สถานะ]
crypto   : [XX.X]% (เป้า [XX]%) → [สถานะ]
gold     : [XX.X]% (เป้า [XX]%) → [สถานะ]

ควรปรับ:
[ระบุชัดเจน ซื้อเพิ่ม/ขาย/เพิ่มประเภทสินทรัพย์อะไร เท่าไหร่ เพราะอะไร]

════════════════════
📰 สรุปข่าวกระทบพอร์ต
════════════════════
ข่าวที่ 1:
หัวข้อ: [ชื่อข่าว]
ผลต่อพอร์ต: [🟢 บวก / 🔴 ลบ / 🟡 กลางๆ] — [สรุป 1-2 ประโยค ว่ากระทบหุ้นในพอร์ตอย่างไร]

ข่าวที่ 2:
หัวข้อ: [ชื่อข่าว]
ผลต่อพอร์ต: [🟢 บวก / 🔴 ลบ / 🟡 กลางๆ] — [สรุป 1-2 ประโยค ว่ากระทบหุ้นในพอร์ตอย่างไร]

ข่าวที่ 3:
หัวข้อ: [ชื่อข่าว]
ผลต่อพอร์ต: [🟢 บวก / 🔴 ลบ / 🟡 กลางๆ] — [สรุป 1-2 ประโยค ว่ากระทบหุ้นในพอร์ตอย่างไร]

════════════════════
🏆 ความคืบหน้าสู่เป้าหมาย
════════════════════
มูลค่าปัจจุบัน : $[X,XXX]
เป้าหมาย      : $[XX,XXX] ภายใน [YYYY]
คืบหน้า        : [X.X]%
ประมาณถึงเป้า  : ~[X.X] ปี
คำแนะนำ: [2 ประโยค อิง risk profile และสถานะพอร์ตตอนนี้]"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert portfolio manager and financial planner specializing in US equities. "
                        "Analyze the portfolio P&L, allocation vs targets, financial goals, and latest news. "
                        "Give concrete, actionable advice in Thai. Name exact stocks to buy/hold/reduce and why. "
                        "Connect news to specific holdings in the portfolio. "
                        "IMPORTANT: Output ONLY the formatted sections as instructed. "
                        "Do NOT add any text before or after the sections. "
                        "Do NOT use Markdown formatting. Plain text only."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2500,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"  Warning: Groq API failed: {e}")
        return f"⚠️ การวิเคราะห์ AI ไม่สำเร็จ: {e}"


# ── Build LINE Message ────────────────────────────────────────────────────────


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[1/5] Fetching portfolio prices...")
    prices = fetch_holding_prices()

    print("[2/5] Calculating P&L & allocation...")
    pnl        = calculate_pnl(prices)
    allocation = calculate_allocation(pnl)

    print("[3/5] Fetching news...")
    news = fetch_news()

    print("[4/5] Calling Groq for portfolio + news analysis...")
    analysis = get_portfolio_analysis(pnl, allocation, news)

    print("[5/5] Sending Flex + analysis to LINE...")
    now      = datetime.datetime.now(BANGKOK_TZ)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%H:%M")

    send_flex(
        f"💼 Portfolio {date_str} {time_str}",
        build_portfolio_bubble(pnl, allocation, {}, FINANCIAL_GOALS, date_str, time_str),
    )
    send_text(f"📝 วิเคราะห์พอร์ต\n\n{analysis}\n\n⚠️ AI-generated. ไม่ใช่คำแนะนำทางการเงิน")

    save_snapshot("portfolio", {
        "pnl": pnl,
        "allocation": allocation,
        "news": news,
        "analysis": analysis,
    })

    now = datetime.datetime.now(BANGKOK_TZ)
    print(f"\n✅ Done at {now.strftime('%Y-%m-%d %H:%M:%S')} Bangkok time")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
