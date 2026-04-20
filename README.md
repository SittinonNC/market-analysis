# 📊 Automated Market Analysis & Alert Bot

ระบบวิเคราะห์ตลาดอัตโนมัติที่ส่งรายงานพร้อม **Technical Analysis จริง** และแจ้งเตือนราคาผ่าน LINE ทุกวันจันทร์–ศุกร์

---

## สิ่งที่ระบบทำ

### รายงานเช้า (3 รอบต่อวัน)
1. ดึงราคา real-time: **ทอง, S&P 500, DXY, VIX, BTC, ETH, Magnificent 7, Watchlist**
2. ดึง **Fear & Greed Index** จาก CNN
3. คำนวณ **Technical Indicators** จากข้อมูลย้อนหลัง 1 ปี:
   - RSI(14) — Overbought/Oversold
   - MACD(12,26,9) — Momentum และ Crossover signal
   - Bollinger Bands(20,2) — Support/Resistance แบบ dynamic
   - EMA 20/50/200 — Trend direction
   - ATR(14) — ความผันผวน ใช้คำนวณ Stop Loss
4. ดึง **Economic Calendar** — high-impact USD events วันนั้น
5. ดึงข่าวจาก BBC, CNBC, MarketWatch, Yahoo Finance, Investing.com
6. ส่งทุกอย่างให้ **Groq AI (llama-3.3-70b-versatile)** วิเคราะห์เป็นภาษาไทย พร้อม:
   - สัญญาณ **BUY / SELL** ชัดเจน
   - จุดเข้าซื้อ (Entry Zone) อิงจาก Bollinger Bands + EMA
   - Stop Loss อิงจาก ATR
   - Take Profit target
7. คำนวณ **Portfolio P&L** ตาม `config.py`
8. ส่งทั้งหมดมาที่ **LINE**

### แจ้งเตือนราคา (ทุกชั่วโมงช่วง market hours)
- ตรวจสอบทุกสินทรัพย์ทุกชั่วโมง
- แจ้งเตือน LINE ทันทีถ้าราคาเคลื่อนไหวเกิน threshold
- ปรับ threshold ได้ใน `config.py`

---

## Technical Indicators ที่ใช้

| Indicator | วิธีใช้ใน Analysis |
|---|---|
| RSI(14) | ≥70 = Overbought, ≤30 = Oversold |
| MACD(12,26,9) | Crossover = สัญญาณ BUY/SELL |
| Bollinger Bands | Upper/Lower = แนวต้าน/แนวรับ |
| EMA 20/50/200 | Alignment = ทิศทาง trend |
| ATR(14) | Stop loss = entry ± ATR |

---

## ตารางเวลา

| รอบ | Bangkok | ช่วงตลาด |
|---|---|---|
| เช้า | 09:00 | Asia session เปิด |
| เย็น | 21:30 | US market เปิด (9:30 AM ET) |
| ดึก | 03:30 | US market ปิด (4:00 PM ET) |
| Alert | ทุกชั่วโมง | ช่วง Asia + US session |

---

## File Structure

```
market-analysis/
├── .github/
│   └── workflows/
│       ├── daily_analysis.yml   # รายงานเช้า 3 รอบ/วัน
│       └── price_alert.yml      # แจ้งเตือนราคาทุกชั่วโมง
├── main.py                      # สคริปต์หลัก
├── technicals.py                # คำนวณ RSI, MACD, BB, EMA, ATR
├── alert.py                     # สคริปต์แจ้งเตือนราคา
├── config.py                    # ⚙️ Portfolio + Alert threshold
├── requirements.txt
└── README.md
```

---

## Setup Guide

### 1. Fork Repository
กด **Fork** บน GitHub แล้ว clone มาที่เครื่อง

---

### 2. ได้ Groq API Key
1. ไปที่ [console.groq.com](https://console.groq.com)
2. สมัครหรือ login → **API Keys** → **Create API Key**
3. Copy key

---

### 3. สร้าง LINE Messaging API Channel

**สร้าง Channel:**
1. ไปที่ [developers.line.biz](https://developers.line.biz) → Login
2. สร้าง Provider → สร้าง **Messaging API** channel
3. เข้า channel → แท็บ **Messaging API**
4. **Channel access token** → **Issue** → Copy

**ได้ User ID:**
1. อยู่ในหน้าเดิม → เลื่อนลงสุด → หา **Your user ID** (ขึ้นต้น `U...`)

---

### 4. เพิ่ม GitHub Secrets

**Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | ค่า |
|---|---|
| `GROQ_API_KEY` | จาก console.groq.com |
| `LINE_CHANNEL_ACCESS_TOKEN` | จาก LINE Developers |
| `LINE_USER_ID` | จาก LINE Developers (ขึ้นต้น U...) |

---

### 5. ตั้งค่า Portfolio

แก้ `config.py` ใส่จำนวนหุ้นและราคาทุนจริง:

```python
PORTFOLIO = {
    "NVDA": {"shares": 10, "avg_cost": 450.00},
    "ASTS": {"shares": 100, "avg_cost": 15.50},
    "GOLD_OZ": {"oz": 2, "avg_cost": 3200.00},
    # ตัวที่ไม่ได้ถือ ปล่อย shares: 0 ไว้
}
```

ปรับ alert threshold:
```python
ALERT_THRESHOLD_STOCKS = 2.0   # % ที่จะแจ้งเตือนหุ้น
ALERT_THRESHOLD_GOLD   = 1.0   # % ที่จะแจ้งเตือนทอง
ALERT_THRESHOLD_CRYPTO = 3.0   # % ที่จะแจ้งเตือน Crypto
```

---

### 6. เปิด GitHub Actions

1. แท็บ **Actions** → **"I understand my workflows, go ahead and enable them"**
2. เปิดทั้ง **Daily Market Analysis** และ **Price Alert (Hourly)**

---

### 7. ทดสอบ

**Actions → Daily Market Analysis → Run workflow → Run workflow**

รอ ~60 วินาที (มี technical analysis เพิ่มขึ้นจึงใช้เวลาเพิ่มขึ้นเล็กน้อย)

---

## สินทรัพย์ที่ติดตาม

| กลุ่ม | Ticker |
|---|---|
| Commodity | GC=F (Gold) |
| Index | ^GSPC (S&P 500) |
| Macro | DX-Y.NYB (DXY), ^VIX |
| Crypto | BTC-USD, ETH-USD |
| Magnificent 7 | AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA |
| Watchlist | ASTS, UNH, EOSE, RKLB, OKLO, ONDS |

---

## Tech Stack

- Python 3.11+
- [yfinance](https://github.com/ranaroussi/yfinance) — ราคาและข้อมูลย้อนหลัง
- [ta](https://technical-analysis-library-in-python.readthedocs.io/) — Technical Analysis (RSI, MACD, BB, EMA, ATR)
- [feedparser](https://feedparser.readthedocs.io/) — RSS news
- [Groq](https://groq.com/) — AI analysis (llama-3.3-70b-versatile)
- LINE Messaging API — การแจ้งเตือน
- GitHub Actions — scheduler

---

> ⚠️ ระบบนี้ให้ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำทางการเงิน การตัดสินใจลงทุนเป็นความรับผิดชอบของคุณเอง
