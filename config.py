# ─────────────────────────────────────────────────────────────
# Portfolio Holdings — แก้ตัวเลขให้ตรงกับพอร์ตจริงของคุณ
# shares = จำนวนหุ้น | avg_cost = ราคาทุนเฉลี่ยต่อหุ้น (USD)
# ถ้าไม่ได้ถือหุ้นตัวไหน ให้ปล่อย shares: 0 ไว้
# ─────────────────────────────────────────────────────────────

PORTFOLIO = {
    # Magnificent 7
    "AAPL":  {"shares": 0, "avg_cost": 0.0},
    "MSFT":  {"shares": 0, "avg_cost": 0.0},
    "NVDA":  {"shares": 0, "avg_cost": 0.0},
    "AMZN":  {"shares": 0, "avg_cost": 0.0},
    "META":  {"shares": 0, "avg_cost": 0.0},
    "GOOGL": {"shares": 0, "avg_cost": 0.0},
    "TSLA":  {"shares": 0, "avg_cost": 0.0},

    # Watchlist
    "ASTS":  {"shares": 0, "avg_cost": 0.0},
    "UNH":   {"shares": 0, "avg_cost": 0.0},
    "EOSE":  {"shares": 0, "avg_cost": 0.0},
    "RKLB":  {"shares": 0, "avg_cost": 0.0},
    "OKLO":  {"shares": 0, "avg_cost": 0.0},
    "ONDS":  {"shares": 0, "avg_cost": 0.0},

    # ทองคำ (ออนซ์)
    "GOLD_OZ": {"oz": 0, "avg_cost": 0.0},
}

# ─────────────────────────────────────────────────────────────
# Alert Thresholds — % การเคลื่อนไหวที่จะกระตุ้นแจ้งเตือน
# ─────────────────────────────────────────────────────────────

ALERT_THRESHOLD_STOCKS = 2.0   # หุ้น: แจ้งเตือนถ้าเคลื่อนเกิน 2%
ALERT_THRESHOLD_GOLD   = 1.0   # ทอง: แจ้งเตือนถ้าเคลื่อนเกิน 1%
ALERT_THRESHOLD_CRYPTO = 3.0   # Crypto: แจ้งเตือนถ้าเคลื่อนเกิน 3%
