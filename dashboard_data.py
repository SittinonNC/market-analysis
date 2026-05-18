"""
Writes per-run snapshots to data/ so the dashboard (docs/) can render
the latest analysis, prices, and news without re-fetching everything.

Layout written:
  data/latest_market.json    — daily market workflow (main.py)
  data/latest_portfolio.json — portfolio workflow (portfolio.py)
  data/history/<ts>-<kind>.json — append-only history
  data/index.json            — list of {ts, kind, file} for the dashboard
"""
import json
import os
import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
HISTORY_DIR = DATA_DIR / "history"
INDEX_FILE = DATA_DIR / "index.json"
MAX_HISTORY = 60  # keep last N snapshots; older ones get pruned


def _ts_now_utc() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")


def _ensure_dirs():
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, payload: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _update_index(ts: str, kind: str, file_rel: str):
    entries = []
    if INDEX_FILE.exists():
        try:
            entries = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entries.append({"ts": ts, "kind": kind, "file": file_rel})
    entries.sort(key=lambda e: e["ts"], reverse=True)

    if len(entries) > MAX_HISTORY:
        for stale in entries[MAX_HISTORY:]:
            stale_path = DATA_DIR / stale["file"]
            try:
                stale_path.unlink(missing_ok=True)
            except Exception:
                pass
        entries = entries[:MAX_HISTORY]

    _atomic_write(INDEX_FILE, entries)


def save_snapshot(kind: str, payload: dict):
    """
    kind: 'market' or 'portfolio'
    payload: any JSON-serializable dict (prices, news, analysis, pnl, …)
    """
    _ensure_dirs()
    ts = _ts_now_utc()
    payload = {"ts": ts, "kind": kind, **payload}

    history_path = HISTORY_DIR / f"{ts}-{kind}.json"
    _atomic_write(history_path, payload)

    latest_path = DATA_DIR / f"latest_{kind}.json"
    _atomic_write(latest_path, payload)

    file_rel = str(history_path.relative_to(DATA_DIR))
    _update_index(ts, kind, file_rel)
    print(f"  snapshot saved: {history_path.name}")
