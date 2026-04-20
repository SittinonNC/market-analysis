# 📊 Automated Market Analysis & Alert Bot

ระบบวิเคราะห์ตลาดอัตโนมัติที่ส่งรายงานเช้าและแจ้งเตือนราคาผ่าน LINE ทุกวันจันทร์–ศุกร์

---

## สิ่งที่ระบบทำ

### รายงานเช้า (3 รอบต่อวัน)
- ดึงราคาแบบ real-time: **ทอง (XAU/USD), S&P 500, DXY, VIX, BTC, ETH, Magnificent 7, และ Watchlist**
- ดึง **Fear & Greed Index** จาก CNN
- ดึง **Economic Calendar** — high-impact USD events ของวันนั้น
- ดึงข่าวจาก BBC, CNBC, MarketWatch, Yahoo Finance, Investing.com
- ส่งข้อมูลทั้งหมดให้ **Groq AI** วิเคราะห์เป็นภาษาไทย พร้อมสัญญาณ BUY/SELL และจุดเข้าซื้อรายตัว
- คำนวณ **Portfolio P&L** ตามที่กำหนดใน `config.py`
- ส่งทุกอย่างมาที่ **LINE**

### แจ้งเตือนราคา (ทุกชั่วโมงช่วง market hours)
- ตรวจสอบทุกสินทรัพย์ทุกชั่วโมง
- ถ้าราคาเคลื่อนไหวเกิน threshold ที่กำหนด → แจ้งเตือน LINE ทันที
- threshold ปรับได้ใน `config.py`

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
├── main.py                      # สคริปต์หลัก — ดึงข้อมูล + AI + LINE
├── alert.py                     # สคริปต์แจ้งเตือนราคา
├── config.py                    # ⚙️ กำหนด portfolio และ alert threshold
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
2. สมัครหรือ login
3. ไปที่ **API Keys** → **Create API Key**
4. Copy key

---

### 3. สร้าง LINE Messaging API Channel และได้ Credentials

**สร้าง Channel:**
1. ไปที่ [developers.line.biz](https://developers.line.biz) → Login
2. สร้าง Provider → สร้าง **Messaging API** channel
3. เข้าไปใน channel → แท็บ **Messaging API**
4. เลื่อนหา **Channel access token** → กด **Issue** → Copy token

**ได้ User ID:**
1. อยู่ในหน้าเดิม → เลื่อนลงสุด หา **Your user ID** (ขึ้นต้น `U...`)
2. Copy ตัวนั้น

---

### 4. เพิ่ม GitHub Secrets

ไปที่ repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | ค่า |
|---|---|
| `GROQ_API_KEY` | จาก console.groq.com |
| `LINE_CHANNEL_ACCESS_TOKEN` | จาก LINE Developers |
| `LINE_USER_ID` | จาก LINE Developers (ขึ้นต้น U...) |

---

### 5. ตั้งค่า Portfolio (ไม่บังคับ)

แก้ไฟล์ `config.py` ใส่จำนวนหุ้นและราคาทุนจริง:

```python
PORTFOLIO = {
    "NVDA": {"shares": 10, "avg_cost": 450.00},
    "ASTS": {"shares": 100, "avg_cost": 15.50},
    "GOLD_OZ": {"oz": 2, "avg_cost": 3200.00},
    # ตัวที่ไม่ได้ถือ ปล่อย shares: 0 ไว้
}
```

ปรับ alert threshold ได้ที่ด้านล่างของ `config.py`:
```python
ALERT_THRESHOLD_STOCKS = 2.0   # % ที่จะกระตุ้นแจ้งเตือนหุ้น
ALERT_THRESHOLD_GOLD   = 1.0   # % ที่จะกระตุ้นแจ้งเตือนทอง
ALERT_THRESHOLD_CRYPTO = 3.0   # % ที่จะกระตุ้นแจ้งเตือน Crypto
```

---

### 6. เปิด GitHub Actions

1. ไปที่แท็บ **Actions** ใน repo
2. กด **"I understand my workflows, go ahead and enable them"**
3. เปิดทั้ง **Daily Market Analysis** และ **Price Alert (Hourly)**

---

### 7. ทดสอบ

**Actions → Daily Market Analysis → Run workflow → Run workflow**

รอ ~30 วินาที จะมีข้อความเข้า LINE ครับ

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
- [yfinance](https://github.com/ranaroussi/yfinance) — ราคาหุ้นและ commodity
- [feedparser](https://feedparser.readthedocs.io/) — RSS news
- [Groq](https://groq.com/) — AI analysis (llama-3.3-70b-versatile)
- LINE Messaging API — การแจ้งเตือน
- GitHub Actions — scheduler

---

> ⚠️ ระบบนี้ให้ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำทางการเงิน การตัดสินใจลงทุนเป็นความรับผิดชอบของคุณเอง
