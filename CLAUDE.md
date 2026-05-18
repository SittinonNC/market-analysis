# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An automated market analysis bot that runs on **GitHub Actions** (no local server), fetches market data + news, asks **Groq AI** (llama-3.3-70b-versatile) to produce a Thai-language analysis, and pushes the result to **LINE** via the Messaging API. All output is Thai; prompts to Groq are constructed in Thai.

## Running locally

```bash
pip install -r requirements.txt

# Required env vars for any script that sends to LINE / calls Groq:
export GROQ_API_KEY=...
export LINE_CHANNEL_ACCESS_TOKEN=...
export LINE_USER_ID=...

python main.py        # full daily market analysis (~90s, hits all symbols)
python portfolio.py   # portfolio-only deep dive (~30s)
python alert.py       # price threshold check (~15s)
```

There are no tests, lint config, or build step. Scheduling lives in `.github/workflows/*.yml` (cron in UTC; comments show Bangkok time). All three workflows also have `workflow_dispatch` for manual runs.

## Architecture

Three independent entry points share `config.py` and (for `main.py`) `technicals.py`. Each script is a self-contained pipeline: fetch → format → prompt Groq → POST to LINE. There is no shared framework, no DB, no state between runs.

- **`main.py`** — Daily market analysis. Pulls prices for gold/S&P/DXY/VIX/BTC/ETH/Mag7/watchlist via yfinance, CNN Fear & Greed, ForexFactory calendar (JSON from nfs.faireconomy.media) + flash news (HTML scrape), RSS news, Trump Truth Social RSS. Calls `technicals.fetch_all_indicators` for RSI/MACD/BB/EMA/ATR on every symbol. Sends one large Thai prompt to Groq, splits the response into LINE messages (LINE has a 5000-char limit per message — splitting logic lives here).
- **`portfolio.py`** — Portfolio-only flow. Same shape but scoped to symbols actually held (`shares > 0` / `oz > 0` in `PORTFOLIO`). Computes per-position P&L, current vs `TARGET_ALLOCATION`, and progress vs `FINANCIAL_GOALS`. Reuses RSS feed list but does not call `technicals.py`.
- **`alert.py`** — Threshold-only check; no Groq, no news. Reads `ALERT_THRESHOLD_*` from config and posts to LINE only when a symbol moves beyond its threshold since previous close.
- **`technicals.py`** — Pure computation using `ta` library. `fetch_all_indicators(symbols)` batch-downloads 1Y of daily bars via `yf.download(..., group_by='ticker')` and returns a dict keyed by symbol; `format_indicators` renders the dict into the Thai text block that gets embedded in the Groq prompt.
- **`portfolio.json`** — Single source of truth for portfolio, goals, target allocation, and alert thresholds. Edited via the dashboard or directly. `portfolio` uses `{"shares", "avg_cost"}` for equities/crypto and `{"oz", "avg_cost"}` for `GOLD_OZ` (note the different key). `target_allocation` percentages must sum to 100. Symbols with `shares: 0` are still valid — `main.py` tracks them for analysis; `portfolio.py` filters them out.
- **`config.py`** — Thin loader that reads `portfolio.json` and re-exports the legacy names (`PORTFOLIO`, `FINANCIAL_GOALS`, `TARGET_ALLOCATION`, `ALERT_THRESHOLD_*`). Don't put data here.
- **`dashboard_data.py`** — `save_snapshot(kind, payload)` writes `data/latest_<kind>.json` + `data/history/<ts>-<kind>.json` and updates `data/index.json`. Workflows commit the `data/` dir back via `permissions: contents: write`.

## Dashboard (`docs/`)

Static GitHub Pages app (`docs/index.html` + `style.css` + `app.js`) that reads and writes the same `portfolio.json` the workflows use. Reads via GitHub Contents API; writes require a fine-grained PAT (Contents: Read & Write) stored in browser localStorage. Workflows commit `data/latest_*.json` + `data/history/*.json` snapshots back to the repo via `permissions: contents: write` so the dashboard can render P&L, news, calendar, Truth Social, and the full Groq analysis without re-fetching anything.

Snapshot rotation lives in `dashboard_data.py` (`MAX_HISTORY=60`). LINE sending and snapshot writing are independent: a LINE failure does not block snapshot save (or vice-versa) — they're sequential calls in `main()` / `portfolio()`.

## Things to know before editing

- **Symbol conventions** are not arbitrary: gold is `GC=F`, S&P is `^GSPC`, DXY is `DX-Y.NYB`, VIX is `^VIX`, crypto is `BTC-USD` / `ETH-USD`. Gold-in-portfolio is tracked under the special key `GOLD_OZ` (ounces, not shares) and must be priced off `GC=F`.
- **Mag7 and Watchlist sets are duplicated** across `main.py`, `portfolio.py`, and `config.py` comments. If you add/remove a ticker, update all of them plus `TARGET_ALLOCATION` buckets in `portfolio.py`'s allocation logic.
- **External fetches are best-effort.** ForexFactory flash-news scraping and Truth Social RSS both have fallback paths and may silently return empty — don't assume the prompt always contains them.
- **LINE message splitting** in `main.py` is content-aware (splits on section headers, not mid-sentence). Changing the Groq output format may break the splitter — keep the section emoji/header structure if you modify the prompt.
- **Groq model**: `llama-3.3-70b-versatile` on the free tier. ~5 calls/day total across all workflows is well under the limit; if you add more calls or larger contexts, recheck the free-tier quota.
- All times in workflow YAML are **UTC**; the in-line comments give Bangkok time. Don't "fix" the offset.
