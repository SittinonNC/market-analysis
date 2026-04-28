# 📊 Automated Market Analysis & Alert Bot

ระบบวิเคราะห์ตลาดอัตโนมัติครบวงจร ส่งรายงานผ่าน **LINE** ทุกวันจันทร์–ศุกร์ พร้อม Technical Analysis จริง, วิเคราะห์ข่าว, ติดตามพอร์ต และวางแผนการเงิน

---

## Workflows (3 ระบบ)

| Workflow | Script | เวลา Bangkok | หน้าที่ |
|---|---|---|---|
| **Daily Market Analysis** | `main.py` | 09:00 / 21:30 / 03:30 | ข่าว + ราคา + Technical Analysis + ภาพรวมพอร์ต |
| **Portfolio Analysis** | `portfolio.py` | 20:00 | วิเคราะห์พอร์ตเชิงลึก + ข่าว + วางแผนการเงิน |
| **Price Alert** | `alert.py` | ทุกชั่วโมง (Asia + US session) | แจ้งเตือนทันทีถ้าราคาขยับเกิน threshold |

---

## สิ่งที่ระบบทำ

### 1. Daily Market Analysis (main.py) — 3 รอบ/วัน

1. ดึงราคา real-time: **ทอง, S&P 500, DXY, VIX, BTC, ETH, Magnificent 7, Watchlist**
2. ดึง **Fear & Greed Index** จาก CNN
3. คำนวณ **Technical Indicators** จากข้อมูลย้อนหลัง 1 ปี (ทุก symbol):
   - RSI(14) — Overbought/Oversold
   - MACD(12,26,9) — Momentum & Crossover signal
   - Bollinger Bands(20,2) — Support/Resistance แบบ dynamic
   - EMA 20/50/200 — Trend direction
   - ATR(14) — Volatility ใช้คำนวณ Stop Loss
4. ดึง **ForexFactory Calendar** — High-impact events วันนี้ (USD/EUR/GBP/JPY/CNY/AUD/CAD) + upcoming 3 วัน USD
5. ดึง **ForexFactory Flash News** (best-effort HTML scraping)
6. ดึงข่าวจาก RSS: **BBC Business, CNBC, MarketWatch, Yahoo Finance, Investing.com**
7. ดึงโพสต์ล่าสุดจาก **Trump Truth Social** — วิเคราะห์ sentiment ผลต่อตลาด
8. ส่งทุกอย่างให้ **Groq AI** วิเคราะห์เป็นภาษาไทย พร้อม:
   - สัญญาณ BUY / SELL พร้อม Entry Zone, Stop Loss (ATR), Take Profit
   - วิเคราะห์ข่าวทุกแหล่ง ระบุว่าข่าวดี/ร้าย กระทบหุ้นตัวไหน
   - วิเคราะห์ Trump posts ผลต่อตลาด
   - Allocation พอร์ต vs Target + Rebalancing แนะนำ
9. คำนวณ **Portfolio P&L** รายหุ้น + รวม
10. ส่งทั้งหมดมาที่ **LINE**

---

### 2. Portfolio Analysis (portfolio.py) — 1 รอบ/วัน (20:00 Bangkok)

1. ดึงราคาเฉพาะหุ้นที่ถือในพอร์ต
2. คำนวณ **P&L รายหุ้น** พร้อม % กำไร/ขาดทุน และ % เปลี่ยนแปลงวันนี้
3. คำนวณ **Asset Allocation** ปัจจุบัน vs Target (mag7/watchlist/crypto/gold)
4. ดึงข่าว RSS — วิเคราะห์ว่าข่าวกระทบหุ้นในพอร์ตอย่างไร
5. ส่งให้ **Groq AI** วิเคราะห์เชิงลึก:
   - แนะนำ ถือ / ซื้อเพิ่ม / ลดความเสี่ยง รายหุ้น
   - Rebalancing ที่ควรทำ
   - สรุปข่าวที่กระทบพอร์ตโดยตรง
   - ความคืบหน้าสู่เป้าหมายการเงิน + ประมาณกี่ปีถึงเป้า

---

### 3. Price Alert (alert.py) — ทุกชั่วโมง

- ตรวจสอบราคาทุกสินทรัพย์ทุกชั่วโมงในช่วง Asia + US session
- แจ้งเตือน LINE ทันทีถ้าราคาขยับเกิน threshold ที่ตั้งไว้
- ปรับ threshold ได้ใน `config.py`

---

## Groq AI Output Sections

### Daily Market Analysis ส่ง LINE มี:
```
📊 ภาพรวมตลาด          — Bullish/Bearish/Neutral + เหตุผล
💰 ทองคำ (XAU/USD)     — Signal BUY/SELL + Entry/SL/TP
📈 S&P 500              — Signal + Entry/SL
₿  Crypto               — BTC/ETH Signal
🏆 Magnificent 7        — RSI/MACD/Entry ทุกตัว
👁  Watchlist            — RSI/MACD/Entry ทุกตัว
🏦 ForexFactory Calendar — วันนี้ + Upcoming 3 วัน
🐦 Trump Truth Social   — สรุปโพสต์ + Bullish/Bearish/Neutral
📰 วิเคราะห์ข่าวทุกแหล่ง — ข่าวดี/ร้าย กระทบหุ้นอะไร
💼 วิเคราะห์พอร์ต       — Allocation + Rebalancing + Goal
⚡ สรุปคำแนะนำ
```

### Portfolio Analysis ส่ง LINE มี:
```
💼 สรุป Portfolio วันนี้  — มูลค่ารวม, P&L, สถานะ
📊 วิเคราะห์รายหุ้น       — ถือ/ซื้อเพิ่ม/ลด พร้อมเหตุผล
⚖️ Rebalancing แนะนำ     — Allocation ปัจจุบัน vs Target
📰 สรุปข่าวกระทบพอร์ต    — ข่าวเชื่อมกับหุ้นในพอร์ตโดยตรง
🏆 ความคืบหน้าสู่เป้าหมาย — % คืบหน้า + ประมาณกี่ปีถึงเป้า
```

---

## Technical Indicators

| Indicator | วิธีใช้ใน Analysis |
|---|---|
| RSI(14) | ≥70 = Overbought, ≤30 = Oversold |
| MACD(12,26,9) | Crossover = สัญญาณ BUY/SELL |
| Bollinger Bands(20,2) | Upper/Lower = แนวต้าน/แนวรับ |
| EMA 20/50/200 | Alignment = ทิศทาง trend |
| ATR(14) | Stop loss = entry ± ATR |

---

## ตารางเวลา

| Workflow | Bangkok | UTC | หมายเหตุ |
|---|---|---|---|
| Daily Market Analysis | 09:00 | 02:00 | Asia session เปิด |
| Daily Market Analysis | 21:30 | 14:30 | US market เปิด (9:30 AM ET) |
| Daily Market Analysis | 03:30 | 20:30 | US market ปิด (4:00 PM ET) |
| Portfolio Analysis | 20:00 | 13:00 | ก่อน US market เปิด |
| Price Alert | ทุกชั่วโมง | 02–09, 13–21 UTC | Asia + US session |

---

## File Structure

```
market-analysis/
├── .github/
│   └── workflows/
│       ├── daily_analysis.yml      # รายงานตลาด 3 รอบ/วัน
│       ├── portfolio_analysis.yml  # วิเคราะห์พอร์ต 1 รอบ/วัน
│       └── price_alert.yml         # แจ้งเตือนราคาทุกชั่วโมง
├── main.py                         # Daily market analysis
├── portfolio.py                    # Portfolio analysis & financial planning
├── technicals.py                   # RSI, MACD, BB, EMA, ATR
├── alert.py                        # Price alert
├── config.py                       # ⚙️ Portfolio + Goals + Allocation + Thresholds
├── requirements.txt
└── README.md
```

---

## Setup Guide

### 1. Fork Repository
กด **Fork** บน GitHub แล้ว clone มาที่เครื่อง

---

### 2. ได้ Groq API Key (ฟรี)
1. ไปที่ [console.groq.com](https://console.groq.com)
2. สมัครหรือ login → **API Keys** → **Create API Key**
3. Copy key

> Free tier ใช้ได้ฟรีตลอด — ระบบนี้ใช้แค่ ~5 calls/วัน ห่างจาก limit มาก

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

### 5. ตั้งค่าใน config.py

**Portfolio Holdings** — ใส่หุ้นที่ถือจริง:
```python
PORTFOLIO = {
    "MSFT":     {"shares": 1.05, "avg_cost": 470.59},
    "NVDA":     {"shares": 0.88, "avg_cost": 181.98},
    "ASTS":     {"shares": 0.69, "avg_cost": 86.69},
    "EOSE":     {"shares": 14.4, "avg_cost": 8.76},
    "OKLO":     {"shares": 4.04, "avg_cost": 96.92},
    "ONDS":     {"shares": 6.13, "avg_cost": 11.38},
    "GOLD_OZ":  {"oz": 0, "avg_cost": 0.0},
    # ตัวที่ไม่ได้ถือ ปล่อย shares: 0
}
```

**Financial Goals** — เป้าหมายการเงิน:
```python
FINANCIAL_GOALS = {
    "target_portfolio_value": 50000,  # เป้าหมายมูลค่าพอร์ต (USD)
    "target_date": "2030-01-01",      # วันที่อยากถึงเป้า
    "monthly_investment": 500,        # เงินลงทุนเพิ่มต่อเดือน (USD)
    "risk_profile": "moderate",       # conservative / moderate / aggressive
}
```

**Target Allocation** — สัดส่วนที่ต้องการ (รวมกันต้องได้ 100):
```python
TARGET_ALLOCATION = {
    "mag7":      40,   # % — Magnificent 7
    "watchlist": 35,   # % — Watchlist
    "crypto":    15,   # % — BTC + ETH
    "gold":      10,   # % — ทองคำ
}
```

**Alert Threshold** — % ที่จะแจ้งเตือน:
```python
ALERT_THRESHOLD_STOCKS = 2.0
ALERT_THRESHOLD_GOLD   = 1.0
ALERT_THRESHOLD_CRYPTO = 3.0
```

---

### 6. เปิด GitHub Actions

1. แท็บ **Actions** → **"I understand my workflows, go ahead and enable them"**
2. เปิดทั้ง 3 workflow: **Daily Market Analysis**, **Portfolio Analysis**, **Price Alert**

---

### 7. ทดสอบ

**Actions → เลือก workflow → Run workflow → Run workflow**

| Workflow | เวลารอโดยประมาณ |
|---|---|
| Daily Market Analysis | ~90 วินาที (มี technical analysis ทุก symbol) |
| Portfolio Analysis | ~30 วินาที |
| Price Alert | ~15 วินาที |

---

## สินทรัพย์ที่ติดตาม

| กลุ่ม | Ticker | หมายเหตุ |
|---|---|---|
| Commodity | GC=F | Gold (XAU/USD) |
| Index | ^GSPC | S&P 500 |
| Macro | DX-Y.NYB, ^VIX | DXY Dollar Index, Volatility Index |
| Crypto | BTC-USD, ETH-USD | Bitcoin, Ethereum |
| Magnificent 7 | AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA | |
| Watchlist | ASTS, UNH, EOSE, RKLB, OKLO, ONDS | |

---

## แหล่งข้อมูล

| ประเภท | แหล่ง |
|---|---|
| ราคาหุ้น/crypto | Yahoo Finance (yfinance) |
| Fear & Greed Index | CNN Business |
| Economic Calendar | ForexFactory (nfs.faireconomy.media) |
| Flash News | ForexFactory.com (scraping) |
| ข่าว RSS | BBC Business, CNBC, MarketWatch, Yahoo Finance, Investing.com |
| Social Media | Trump Truth Social RSS |

---

## Tech Stack

- **Python 3.11+**
- [yfinance](https://github.com/ranaroussi/yfinance) — ราคาและข้อมูลย้อนหลัง
- [ta](https://technical-analysis-library-in-python.readthedocs.io/) — Technical Analysis (RSI, MACD, BB, EMA, ATR)
- [feedparser](https://feedparser.readthedocs.io/) — RSS news & Truth Social
- [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML scraping
- [Groq](https://groq.com/) — AI analysis (llama-3.3-70b-versatile) — **ฟรี**
- LINE Messaging API — การแจ้งเตือน
- GitHub Actions — scheduler อัตโนมัติ

---

> ⚠️ ระบบนี้ให้ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำทางการเงิน การตัดสินใจลงทุนเป็นความรับผิดชอบของคุณเอง
