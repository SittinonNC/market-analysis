# 📊 Automated Stock & Gold Market Analysis Bot

A fully automated Python bot that runs every weekday morning at **09:00 AM Bangkok time** via GitHub Actions. It fetches live Gold (XAU/USD) and S&P 500 prices, scrapes financial news, generates a Thai-language AI analysis via Groq, and sends everything to your Telegram.

---

## What This Project Does

1. **Fetches real-time prices** for Gold (XAU/USD) and S&P 500 using `yfinance`
2. **Scrapes financial news** from Reuters, CNBC, MarketWatch, and Investing.com RSS feeds
3. **Sends data to Groq AI** (llama-3.3-70b-versatile) for a structured Thai-language market analysis
4. **Delivers a formatted briefing** to your Telegram chat every weekday morning

---

## Setup Guide

### 1. Get a Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up or log in
3. Navigate to **API Keys** → **Create API Key**
4. Copy your key — you'll add it as a GitHub Secret

---

### 2. Create a Telegram Bot & Get Your Chat ID

**Create the bot:**
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the **Bot Token** (looks like `123456789:ABCdef...`)

**Get your Chat ID:**
1. Start a chat with your new bot (send it any message)
2. Visit this URL in your browser (replace `YOUR_BOT_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
3. Look for `"chat":{"id":XXXXXXXXX}` — that number is your **Chat ID**

---

### 3. Fork This Repository

1. Click **Fork** on the top-right of this GitHub repository
2. This creates your own copy where you can add secrets and enable Actions

---

### 4. Add GitHub Secrets

In your forked repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each of the following:

| Secret Name | Value |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID |

---

### 5. Enable GitHub Actions

1. Go to the **Actions** tab in your forked repository
2. Click **"I understand my workflows, go ahead and enable them"**
3. The bot will now run automatically at **02:00 UTC (09:00 AM Bangkok)** on weekdays

---

### 6. Trigger Manually for Testing

1. Go to **Actions** → **Daily Market Analysis**
2. Click **Run workflow** → **Run workflow**
3. Watch the logs in real time — you should receive a Telegram message within ~30 seconds

---

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GROQ_API_KEY="your_groq_api_key"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

# Run the bot
python main.py
```

---

## Schedule

The bot runs on this cron: `0 2 * * 1-5`
- **UTC:** 02:00 AM, Monday–Friday
- **Bangkok:** 09:00 AM, Monday–Friday

---

## Tech Stack

- Python 3.11+
- [yfinance](https://github.com/ranaroussi/yfinance) — price data
- [feedparser](https://feedparser.readthedocs.io/) — RSS news
- [Groq](https://groq.com/) — AI analysis (llama-3.3-70b-versatile)
- [Telegram Bot API](https://core.telegram.org/bots/api) — notifications
- GitHub Actions — scheduling

---

> ⚠️ This bot provides AI-generated market analysis for informational purposes only. It is **not financial advice**. Always do your own research before making any investment decisions.
