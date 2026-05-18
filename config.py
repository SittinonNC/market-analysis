"""
Loads runtime config from portfolio.json so the dashboard (docs/) can edit it
without touching code. Re-exports the same names the rest of the codebase imports:
PORTFOLIO, FINANCIAL_GOALS, TARGET_ALLOCATION,
ALERT_THRESHOLD_STOCKS, ALERT_THRESHOLD_GOLD, ALERT_THRESHOLD_CRYPTO.
"""
import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "portfolio.json"

with _CONFIG_PATH.open("r", encoding="utf-8") as f:
    _data = json.load(f)

PORTFOLIO         = _data["portfolio"]
FINANCIAL_GOALS   = _data["financial_goals"]
TARGET_ALLOCATION = _data["target_allocation"]

_t = _data["alert_thresholds"]
ALERT_THRESHOLD_STOCKS = float(_t["stocks"])
ALERT_THRESHOLD_GOLD   = float(_t["gold"])
ALERT_THRESHOLD_CRYPTO = float(_t["crypto"])
