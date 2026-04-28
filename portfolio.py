"""
portfolio.py — Portfolio Analysis & Financial Planning
รันแยกจาก main.py โดยเฉพาะ ส่ง LINE รายงานพอร์ต + วางแผนการเงิน
"""

import os
import math
import time
import datetime
import pytz
import requests
import yfinance as yf
from groq import Groq
from config import PORTFOLIO, FINANCIAL_GOALS, TARGET_ALLOCATION

BANGKOK_TZ = pytz.timezone("Asia/Bangkok")

MAG7 = {"AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"}
WATCHLIST = {"ASTS", "UNH", "EOSE", "RKLB", "OKLO", "ONDS"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def fmt_price(v, prefix="$"):
    return f"{prefix}{v:,.2f}" if isinstance(v, float) else str(v)

def fmt_pct(v):
    return f"{v:+.2f}%" if isinstance(v, float) else str(v)

def arrow(v):
    return ("▲" if v >= 0 else "▼") if isinstance(v, float) else "•"


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
            current = round(hist["Close"].iloc[-1], 2)
            prev = round(hist["Close"].iloc[-2], 2) if len(hist) >= 2 else current
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
    total_value = 0.0
    total_cost = 0.0

    for symbol, holding in PORTFOLIO.items():
        if symbol == "GOLD_OZ":
            qty = holding.get("oz", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            current_price = prices.get("GC=F", {}).get("price", "N/A")
        else:
            qty = holding.get("shares", 0)
            avg_cost = holding.get("avg_cost", 0.0)
            current_price = prices.get(symbol, {}).get("price", "N/A")

        if qty == 0 or avg_cost == 0:
            continue

        if not isinstance(current_price, float):
            pnl[symbol] = {"qty": qty, "avg_cost": avg_cost, "current_price": "N/A",
                           "value": "N/A", "cost": qty * avg_cost, "gain": "N/A", "gain_pct": "N/A"}
            continue

        cost = qty * avg_cost
        value = qty * current_price
        gain = value - cost
        gain_pct = (gain / cost * 100) if cost else 0.0

        pnl[symbol] = {
            "qty": qty,
            "avg_cost": avg_cost,
            "current_price": current_price,
            "value": value,
            "cost": cost,
            "gain": gain,
            "gain_pct": gain_pct,
            "today_change": prices.get(symbol if symbol != "GOLD_OZ" else "GC=F", {}).get("change", "N/A"),
        }
        total_value += value
        total_cost += cost

    if total_cost > 0:
        pnl["__total__"] = {
            "value": total_value,
            "cost": total_cost,
            "gain": total_value - total_cost,
            "gain_pct": ((total_value - total_cost) / total_cost * 100),
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
        target_pct = TARGET_ALLOCATION.get(cls, 0)
        diff = current_pct - target_pct
        status = "Overweight" if diff > 2 else ("Underweight" if diff < -2 else "On Target")
        result[cls] = {
            "value": val,
            "current_pct": round(current_pct, 1),
            "target_pct": target_pct,
            "diff": round(diff, 1),
            "status": status,
        }

    result["__total__"] = total
    return result


# ── Groq Analysis ─────────────────────────────────────────────────────────────

def build_pnl_context(pnl: dict) -> str:
    lines = []
    for symbol, d in pnl.items():
        if symbol == "__total__":
            continue
        if isinstance(d.get("gain"), float):
            today = f"  วันนี้: {fmt_pct(d.get('today_change', 'N/A'))}" if isinstance(d.get("today_change"), float) else ""
            lines.append(
                f"{symbol}: ราคา {fmt_price(d['current_price'])} | ทุน {fmt_price(d['avg_cost'])} | "
                f"P&L {fmt_price(d['gain'], prefix='$')} ({fmt_pct(d['gain_pct'])}){today}"
            )
    total = pnl.get("__total__", {})
    if isinstance(total.get("value"), float):
        lines += [
            "",
            f"รวมพอร์ต: {fmt_price(total['value'])} | ต้นทุน: {fmt_price(total['cost'])} | "
            f"P&L: {fmt_price(total['gain'], prefix='$')} ({fmt_pct(total['gain_pct'])})",
        ]
    return "\n".join(lines)


def build_allocation_context(allocation: dict) -> str:
    if not allocation or "__total__" not in allocation:
        return "ไม่มีข้อมูล"
    total = allocation["__total__"]
    lines = [f"มูลค่าพอร์ตรวม: ${total:,.2f}", ""]
    for cls in ["mag7", "watchlist", "crypto", "gold"]:
        d = allocation.get(cls)
        if d is None:
            continue
        lines.append(
            f"  {cls:12s}: {d['current_pct']:5.1f}% (เป้า {d['target_pct']}%) "
            f"→ {d['status']} ({d['diff']:+.1f}%)"
        )
    return "\n".join(lines)


def build_goals_context(allocation: dict) -> str:
    if not allocation or "__total__" not in allocation:
        return ""
    total_val = allocation["__total__"]
    g = FINANCIAL_GOALS
    target_val = g["target_portfolio_value"]
    monthly = g["monthly_investment"]
    risk = g["risk_profile"]
    target_date = g["target_date"]

    lines = [
        f"เป้าหมาย: ${target_val:,.0f} ภายใน {target_date}",
        f"ลงทุนรายเดือน: ${monthly}/mo | Risk profile: {risk}",
        f"ความคืบหน้า: ${total_val:,.0f} / ${target_val:,.0f} ({total_val/target_val*100:.1f}%)",
    ]

    if target_val > total_val > 0 and monthly > 0:
        gap = target_val - total_val
        monthly_rate = 0.10 / 12
        try:
            n = math.log((gap * monthly_rate / monthly) + 1) / math.log(1 + monthly_rate)
            est_years = round(n / 12, 1)
            lines.append(f"ประมาณถึงเป้า: ~{est_years} ปี (ผลตอบแทน 10%/ปี + ${monthly}/เดือน)")
        except (ValueError, ZeroDivisionError):
            pass

    return "\n".join(lines)


def get_portfolio_analysis(pnl: dict, allocation: dict) -> str:
    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

        pnl_ctx = build_pnl_context(pnl)
        alloc_ctx = build_allocation_context(allocation)
        goals_ctx = build_goals_context(allocation)

        user_prompt = f"""วิเคราะห์พอร์ตการลงทุนต่อไปนี้และให้คำแนะนำ ใช้ภาษาไทย ห้ามใช้ ** หรือ # หรือ Markdown ใดๆ

PORTFOLIO P&L:
{pnl_ctx}

ASSET ALLOCATION vs TARGET:
{alloc_ctx}

FINANCIAL GOALS:
{goals_ctx}

ตอบตาม format นี้เท่านั้น:

════════════════════
💼 สรุป Portfolio วันนี้
════════════════════
มูลค่ารวม: $[X,XXX] | P&L รวม: $[±X,XXX] ([±X.XX]%)
สถานะ: [ดีขึ้น/แย่ลง/ทรงตัว] เมื่อเทียบกับทุน

════════════════════
📊 วิเคราะห์รายหุ้น
════════════════════
[ชื่อหุ้น]: [ราคา] P&L [±$XXX] ([±%]) → [แนะนำ: ถือ/ซื้อเพิ่ม/ลดความเสี่ยง] — [เหตุผล 1 ประโยค]
(ทำทุกหุ้นในพอร์ต)

════════════════════
🎯 Allocation vs เป้าหมาย
════════════════════
[asset class]: [XX%] (เป้า [YY%]) → [Overweight/Underweight/On Target]
[วิเคราะห์สั้น: ว่าควรปรับอะไร]

════════════════════
⚖️ Rebalancing แนะนำ
════════════════════
[ระบุชัดเจน: ซื้อเพิ่ม/ขายทำกำไร/ถือ ตัวไหน เท่าไหร่ เพราะอะไร]

════════════════════
🏆 ความคืบหน้าสู่เป้าหมาย
════════════════════
มูลค่าปัจจุบัน: $[X,XXX] | เป้า: $[XX,XXX] ภายใน [YYYY]
คืบหน้า: [X.X]% | ประมาณถึงเป้า: ~[X] ปี
คำแนะนำ: [2-3 ประโยค อิง risk profile และสถานะพอร์ตปัจจุบัน]"""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert portfolio manager and financial planner. "
                        "Analyze the user's portfolio P&L, asset allocation vs targets, and financial goals. "
                        "Give concrete, actionable advice in Thai language. "
                        "Be specific: name exact stocks to buy/hold/reduce and why. "
                        "Do NOT use Markdown formatting like ** or *. Plain text only."
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
        return f"⚠️ การวิเคราะห์ AI ไม่สำเร็จ: {e}"


# ── Build LINE Message ────────────────────────────────────────────────────────

def build_portfolio_message(pnl: dict, allocation: dict, analysis: str) -> str:
    now = datetime.datetime.now(BANGKOK_TZ)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%H:%M")

    total = pnl.get("__total__", {})
    gain = total.get("gain", 0.0)
    gain_pct = total.get("gain_pct", 0.0)
    total_val = total.get("value", 0.0)
    header_emoji = "📈" if isinstance(gain, float) and gain >= 0 else "📉"

    lines = [
        "╔══════════════════════╗",
        "   💼 Portfolio Report",
        f"   📅 {date_str}  ⏰ {time_str}",
        "╚══════════════════════╝",
        "",
    ]

    # P&L Summary
    if isinstance(total_val, float):
        lines += [
            "── P&L Summary ──────────────",
            f"{header_emoji} มูลค่ารวม : ${total_val:,.2f}",
            f"   P&L รวม  : ${gain:+,.2f} ({gain_pct:+.2f}%)",
            "",
        ]

    # Per-holding detail
    lines.append("── รายหุ้น ──────────────────")
    for symbol, d in pnl.items():
        if symbol == "__total__":
            continue
        if isinstance(d.get("gain"), float):
            g_arrow = "▲" if d["gain"] >= 0 else "▼"
            pad = " " * max(0, 5 - len(symbol))
            today_str = f"  วันนี้: {d['today_change']:+.2f}%" if isinstance(d.get("today_change"), float) else ""
            lines.append(
                f"{g_arrow} {symbol}{pad}: {fmt_price(d['current_price'])}"
                f"  P&L {d['gain']:+,.2f} ({d['gain_pct']:+.2f}%){today_str}"
            )

    # Allocation
    if allocation and "__total__" in allocation:
        lines += ["", "── Allocation vs Target ─────"]
        alloc_emoji = {"Overweight": "🔴", "Underweight": "🟡", "On Target": "🟢"}
        label_map = {
            "mag7": "Mag7    ",
            "watchlist": "Watch   ",
            "crypto": "Crypto  ",
            "gold": "Gold    ",
        }
        for cls in ["mag7", "watchlist", "crypto", "gold"]:
            d = allocation.get(cls)
            if d is None:
                continue
            emoji = alloc_emoji.get(d["status"], "⚪")
            lbl = label_map.get(cls, cls)
            lines.append(
                f"{emoji} {lbl}: {d['current_pct']:5.1f}% (เป้า {d['target_pct']}%)  {d['status']}"
            )

    # Goals progress
    g = FINANCIAL_GOALS
    target_val = g["target_portfolio_value"]
    if isinstance(total_val, float) and target_val > 0:
        progress_pct = total_val / target_val * 100
        lines += [
            "",
            "── เป้าหมาย ─────────────────",
            f"   เป้า : ${target_val:,.0f}  ภายใน {g['target_date']}",
            f"   ปัจจุบัน: ${total_val:,.0f}  ({progress_pct:.1f}%)",
            f"   ลงทุน/เดือน: ${g['monthly_investment']}  |  Risk: {g['risk_profile']}",
        ]

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━",
        analysis,
        "━━━━━━━━━━━━━━━━━━",
        "⚠️ AI-generated analysis. Not financial advice.",
    ]

    return "\n".join(lines)


# ── Send LINE ─────────────────────────────────────────────────────────────────

def send_line(message: str):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("  Error: LINE credentials not set")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    chunks = [message[i:i + 5000] for i in range(0, len(message), 5000)]

    for i, chunk in enumerate(chunks):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json={"to": user_id, "messages": [{"type": "text", "text": chunk}]},
                timeout=30,
            )
            resp.raise_for_status()
            print(f"  LINE chunk {i+1}/{len(chunks)} sent OK")
        except Exception as e:
            print(f"  Error sending LINE chunk {i+1}: {e}")
        if i < len(chunks) - 1:
            time.sleep(1)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[1/4] Fetching portfolio prices...")
    prices = fetch_holding_prices()

    print("[2/4] Calculating P&L & allocation...")
    pnl = calculate_pnl(prices)
    allocation = calculate_allocation(pnl)

    print("[3/4] Calling Groq for portfolio analysis...")
    analysis = get_portfolio_analysis(pnl, allocation)

    print("[4/4] Sending LINE message...")
    message = build_portfolio_message(pnl, allocation, analysis)
    send_line(message)

    now = datetime.datetime.now(BANGKOK_TZ)
    print(f"\n✅ Done at {now.strftime('%Y-%m-%d %H:%M:%S')} Bangkok time")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
