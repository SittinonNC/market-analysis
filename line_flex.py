"""
LINE Flex Message builders + sender.

Used by main.py / portfolio.py / alert.py to render market/portfolio/alert
data as a styled Flex bubble instead of plain text. Free-form Groq analysis
is still sent as a separate text message — Flex is not suited for long prose.
"""
import os
import time
import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

GREEN = "#1B873B"
RED   = "#D32F2F"
GREY  = "#888888"
DARK  = "#222222"
BG_HEADER = "#1F2937"


def _color(v) -> str:
    if not isinstance(v, (int, float)):
        return DARK
    return GREEN if v >= 0 else RED


def _sign(v) -> str:
    if not isinstance(v, (int, float)):
        return ""
    return "+" if v >= 0 else ""


# ── Primitive row builders ───────────────────────────────────────────────────

def _section_header(label: str) -> dict:
    return {
        "type": "text",
        "text": label,
        "size": "sm",
        "weight": "bold",
        "color": GREY,
        "margin": "lg",
    }


def _separator(margin: str = "sm") -> dict:
    return {"type": "separator", "margin": margin}


def _kv_row(label: str, value: str, value_color: str = DARK) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": DARK, "flex": 5},
            {"type": "text", "text": value, "size": "sm", "color": value_color,
             "align": "end", "flex": 5, "weight": "bold"},
        ],
    }


def _price_row(label: str, price: str, change_pct) -> dict:
    """Three-column row: symbol | price | %change (colored)."""
    if isinstance(change_pct, (int, float)):
        change_str = f"{_sign(change_pct)}{change_pct:.2f}%"
        change_col = _color(change_pct)
    else:
        change_str = "—"
        change_col = GREY
    return {
        "type": "box",
        "layout": "horizontal",
        "margin": "sm",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": DARK, "flex": 4, "weight": "bold"},
            {"type": "text", "text": price, "size": "sm", "color": DARK, "flex": 5, "align": "end"},
            {"type": "text", "text": change_str, "size": "sm", "color": change_col, "flex": 4, "align": "end"},
        ],
    }


def _header(title: str, subtitle: str) -> dict:
    return {
        "type": "box",
        "layout": "vertical",
        "backgroundColor": BG_HEADER,
        "paddingAll": "md",
        "contents": [
            {"type": "text", "text": title, "color": "#FFFFFF", "weight": "bold", "size": "lg"},
            {"type": "text", "text": subtitle, "color": "#CCCCCC", "size": "xs", "margin": "xs"},
        ],
    }


def _footer_note(text: str) -> dict:
    return {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {"type": "text", "text": text, "size": "xxs", "color": GREY, "wrap": True, "align": "center"},
        ],
    }


# ── Bubble builders ──────────────────────────────────────────────────────────

def build_market_bubble(prices: dict, fear_greed: dict, date_str: str, time_str: str) -> dict:
    """Market dashboard: F&G, macro, commodities, crypto, mag7, watchlist."""
    body = []

    # Macro
    fg_score = fear_greed.get("score")
    fg_rating = fear_greed.get("rating", "—")
    fg_text = f"{fg_score:.0f} · {fg_rating}" if isinstance(fg_score, float) else f"— · {fg_rating}"
    body += [
        _section_header("MACRO"),
        _separator(),
        _kv_row("Fear & Greed", fg_text),
    ]
    for key, label in [("vix", "VIX"), ("dxy", "DXY")]:
        d = prices.get(key, {})
        body.append(_price_row(label, f"{d.get('price', 0):,.2f}", d.get("change")))

    # Commodities & index
    body += [_section_header("COMMODITIES & INDEX"), _separator()]
    for key, label in [("gold", "GOLD"), ("sp500", "S&P 500")]:
        d = prices.get(key, {})
        body.append(_price_row(label, f"${d.get('price', 0):,.2f}", d.get("change")))

    # Crypto
    body += [_section_header("CRYPTO"), _separator()]
    for key, label in [("btc", "BTC"), ("eth", "ETH")]:
        d = prices.get(key, {})
        body.append(_price_row(label, f"${d.get('price', 0):,.2f}", d.get("change")))

    # Mag 7
    if prices.get("mag7"):
        body += [_section_header("MAGNIFICENT 7"), _separator()]
        for symbol, d in prices["mag7"].items():
            body.append(_price_row(symbol, f"${d.get('price', 0):,.2f}", d.get("change")))

    # Watchlist
    if prices.get("watchlist"):
        body += [_section_header("WATCHLIST"), _separator()]
        for symbol, d in prices["watchlist"].items():
            body.append(_price_row(symbol, f"${d.get('price', 0):,.2f}", d.get("change")))

    body.append(_footer_note("⚠️ AI-generated · Not financial advice"))

    return {
        "type": "bubble",
        "size": "giga",
        "header": _header("📊 Market Briefing", f"{date_str}  ·  {time_str} Bangkok"),
        "body": {"type": "box", "layout": "vertical", "spacing": "none", "contents": body},
    }


def build_portfolio_bubble(pnl: dict, allocation: dict, calendar: dict,
                            goals: dict, date_str: str, time_str: str) -> dict:
    """Portfolio dashboard: P&L summary + holdings + allocation + goal + calendar."""
    body = []
    total = pnl.get("__total__") if pnl else None

    # Summary
    if total and isinstance(total.get("value"), float):
        body += [
            _section_header("PORTFOLIO P&L"),
            _separator(),
            _kv_row("Total Value", f"${total['value']:,.2f}"),
            _kv_row("Cost Basis", f"${total.get('cost', 0):,.2f}"),
            _kv_row(
                "Unrealized",
                f"{_sign(total['gain'])}${abs(total['gain']):,.2f} ({total.get('gain_pct', 0):+.2f}%)",
                _color(total["gain"]),
            ),
        ]

    # Per-holding
    holdings = [(s, d) for s, d in (pnl or {}).items()
                if s != "__total__" and isinstance(d.get("gain"), float)]
    if holdings:
        body += [_section_header("HOLDINGS"), _separator()]
        for symbol, d in holdings:
            today = d.get("today_change")
            change = today if isinstance(today, float) else d.get("gain_pct")
            body.append(_price_row(symbol, f"${d['current_price']:,.2f}", change))
            # second line: P&L
            body.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": "  P&L", "size": "xxs", "color": GREY, "flex": 5},
                    {"type": "text",
                     "text": f"{_sign(d['gain'])}${abs(d['gain']):,.2f} ({d['gain_pct']:+.2f}%)",
                     "size": "xxs", "color": _color(d["gain"]),
                     "align": "end", "flex": 5},
                ],
            })

    # Allocation
    if allocation and "__total__" in allocation:
        body += [_section_header("ALLOCATION VS TARGET"), _separator()]
        label_map = {"mag7": "Mag 7", "watchlist": "Watchlist", "crypto": "Crypto", "gold": "Gold"}
        for cls in ["mag7", "watchlist", "crypto", "gold"]:
            d = allocation.get(cls)
            if not d:
                continue
            diff = d.get("diff", 0)
            diff_col = GREY if abs(diff) < 2 else (RED if diff > 0 else "#F59E0B")
            body.append({
                "type": "box",
                "layout": "horizontal",
                "margin": "sm",
                "contents": [
                    {"type": "text", "text": label_map.get(cls, cls), "size": "sm",
                     "color": DARK, "flex": 4, "weight": "bold"},
                    {"type": "text", "text": f"{d['current_pct']:.1f}%",
                     "size": "sm", "color": DARK, "flex": 3, "align": "end"},
                    {"type": "text", "text": f"/ {d['target_pct']}%",
                     "size": "sm", "color": GREY, "flex": 3, "align": "end"},
                    {"type": "text", "text": f"{_sign(diff)}{diff:.1f}",
                     "size": "sm", "color": diff_col, "flex": 3, "align": "end"},
                ],
            })

    # Goal progress
    if goals and total and isinstance(total.get("value"), float):
        target = goals.get("target_portfolio_value", 0)
        if target > 0:
            progress = total["value"] / target * 100
            filled = min(int(progress / 5), 20)
            bar = "█" * filled + "░" * (20 - filled)
            body += [
                _section_header("GOAL PROGRESS"),
                _separator(),
                _kv_row("Target", f"${target:,.0f} by {goals.get('target_date', '—')}"),
                _kv_row("Current", f"${total['value']:,.0f}"),
                {"type": "text", "text": bar, "size": "xs", "color": GREEN, "margin": "sm", "align": "center"},
                _kv_row("Progress", f"{progress:.1f}%", GREEN if progress >= 50 else DARK),
                _kv_row("Monthly DCA",
                        f"${goals.get('monthly_investment', 0)} · {goals.get('risk_profile', '—')}"),
            ]

    # Economic Calendar
    today_events = (calendar or {}).get("today", [])
    upcoming = (calendar or {}).get("upcoming", [])
    if today_events or upcoming:
        body += [_section_header("ECONOMIC CALENDAR"), _separator()]
        for e in today_events[:5]:
            body.append({
                "type": "text",
                "size": "xs",
                "wrap": True,
                "color": DARK,
                "margin": "sm",
                "text": f"⏰ [{e.get('country', '?')}] {e.get('time', '?')} · {e.get('title', '?')}",
            })
        if upcoming:
            body.append({"type": "text", "text": "Upcoming USD (3d):",
                         "size": "xs", "color": GREY, "margin": "md"})
            for e in upcoming[:5]:
                body.append({
                    "type": "text", "size": "xs", "wrap": True, "color": DARK,
                    "text": f"• {str(e.get('date', '?'))[:10]} — {e.get('title', '?')}",
                })

    body.append(_footer_note("⚠️ AI-generated · Not financial advice"))

    return {
        "type": "bubble",
        "size": "giga",
        "header": _header("💼 Portfolio Report", f"{date_str}  ·  {time_str} Bangkok"),
        "body": {"type": "box", "layout": "vertical", "spacing": "none", "contents": body},
    }


def build_alert_bubble(alerts: list, date_str: str, time_str: str) -> dict:
    """alerts: list of dicts {label, price, prefix, change_pct, threshold}."""
    body = [_section_header("TRIGGERED"), _separator()]
    for a in alerts:
        change = a["change_pct"]
        body.append({
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {"type": "text", "text": a["label"], "size": "sm", "color": DARK,
                 "flex": 5, "weight": "bold"},
                {"type": "text", "text": f"{a['prefix']}{a['price']:,.2f}", "size": "sm",
                 "color": DARK, "flex": 4, "align": "end"},
                {"type": "text", "text": f"{_sign(change)}{change:.2f}%", "size": "sm",
                 "color": _color(change), "flex": 3, "align": "end", "weight": "bold"},
            ],
        })
        body.append({
            "type": "text",
            "text": f"  threshold ±{a['threshold']}%",
            "size": "xxs", "color": GREY,
        })
    body.append(_footer_note("⚠️ Not financial advice"))

    return {
        "type": "bubble",
        "size": "mega",
        "header": _header("🚨 Price Alert", f"{date_str}  ·  {time_str} Bangkok"),
        "body": {"type": "box", "layout": "vertical", "spacing": "none", "contents": body},
    }


# ── Sender ───────────────────────────────────────────────────────────────────

def _post(payload: dict) -> bool:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    if not token or not user_id:
        print("  Error: LINE credentials not set")
        return False
    payload["to"] = user_id
    try:
        resp = requests.post(
            LINE_PUSH_URL,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        print(f"  LINE HTTPError: {e} — {resp.text}")
    except Exception as e:
        print(f"  LINE error: {e}")
    return False


def send_flex(alt_text: str, bubble: dict) -> bool:
    """Send a single Flex bubble."""
    ok = _post({"messages": [{"type": "flex", "altText": alt_text[:400], "contents": bubble}]})
    if ok:
        print(f"  LINE flex sent: {alt_text[:60]}")
    return ok


def send_text(text: str) -> bool:
    """Send long text, chunked to LINE's 5000-char limit. Splits on blank lines."""
    if not text:
        return False
    max_len = 4800
    chunks = []
    remaining = text
    while len(remaining) > max_len:
        # try to split on double-newline near the limit
        split = remaining.rfind("\n\n", 0, max_len)
        if split < max_len // 2:
            split = remaining.rfind("\n", 0, max_len)
        if split < max_len // 2:
            split = max_len
        chunks.append(remaining[:split])
        remaining = remaining[split:].lstrip()
    if remaining:
        chunks.append(remaining)

    all_ok = True
    for i, chunk in enumerate(chunks):
        ok = _post({"messages": [{"type": "text", "text": chunk}]})
        all_ok = all_ok and ok
        if ok:
            print(f"  LINE text chunk {i + 1}/{len(chunks)} sent")
        if i < len(chunks) - 1:
            time.sleep(1)
    return all_ok
