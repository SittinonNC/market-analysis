"""
Technical Analysis module — computes RSI, MACD, Bollinger Bands, EMA, ATR
for all tracked symbols using batch yfinance download.
"""
import yfinance as yf
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange


def _rsi_signal(rsi: float) -> str:
    if rsi >= 70:
        return "Overbought ⚠️"
    if rsi <= 30:
        return "Oversold 🟢"
    if rsi >= 60:
        return "Bullish"
    if rsi <= 40:
        return "Bearish"
    return "Neutral"


def _ema_trend(price: float, ema20: float, ema50: float, ema200: float) -> str:
    if price > ema20 > ema50 > ema200:
        return "Strong Bullish (above all EMAs)"
    if price < ema20 < ema50 < ema200:
        return "Strong Bearish (below all EMAs)"
    if price > ema200 and ema20 > ema50:
        return "Bullish (above EMA200, short-term up)"
    if price < ema200 and ema20 < ema50:
        return "Bearish (below EMA200, short-term down)"
    if price > ema200:
        return "Cautious Bullish (above EMA200 but mixed short-term)"
    return "Bearish (below EMA200)"


def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators from a price DataFrame (needs Close, High, Low columns)."""
    if df is None or len(df) < 30:
        return {}

    close = df["Close"].dropna()
    high = df["High"].dropna()
    low = df["Low"].dropna()

    result = {}

    try:
        rsi_val = round(RSIIndicator(close=close, window=14).rsi().iloc[-1], 2)
        result["rsi"] = {"value": rsi_val, "signal": _rsi_signal(rsi_val)}
    except Exception:
        pass

    try:
        macd_ind = MACD(close=close, window_fast=12, window_slow=26, window_sign=9)
        macd_val = round(macd_ind.macd().iloc[-1], 4)
        signal_val = round(macd_ind.macd_signal().iloc[-1], 4)
        hist_val = round(macd_ind.macd_diff().iloc[-1], 4)
        # Check crossover (last 2 bars)
        hist_prev = macd_ind.macd_diff().iloc[-2]
        if hist_prev <= 0 and hist_val > 0:
            crossover = "Bullish Crossover 🟢"
        elif hist_prev >= 0 and hist_val < 0:
            crossover = "Bearish Crossover 🔴"
        else:
            crossover = "Bullish" if hist_val > 0 else "Bearish"
        result["macd"] = {
            "macd": macd_val,
            "signal": signal_val,
            "histogram": hist_val,
            "trend": crossover,
        }
    except Exception:
        pass

    try:
        bb = BollingerBands(close=close, window=20, window_dev=2)
        bbu = round(bb.bollinger_hband().iloc[-1], 2)
        bbm = round(bb.bollinger_mavg().iloc[-1], 2)
        bbl = round(bb.bollinger_lband().iloc[-1], 2)
        price = close.iloc[-1]
        pct_b = round(bb.bollinger_pband().iloc[-1] * 100, 1)
        if price >= bbu:
            bb_pos = "At Upper Band (Overbought zone)"
        elif price <= bbl:
            bb_pos = "At Lower Band (Oversold zone)"
        elif price > bbm:
            bb_pos = "Above Middle Band (Bullish)"
        else:
            bb_pos = "Below Middle Band (Bearish)"
        result["bbands"] = {
            "upper": bbu, "middle": bbm, "lower": bbl,
            "position": bb_pos, "pct_b": pct_b,
        }
    except Exception:
        pass

    try:
        ema20 = round(EMAIndicator(close=close, window=20).ema_indicator().iloc[-1], 2)
        ema50 = round(EMAIndicator(close=close, window=50).ema_indicator().iloc[-1], 2)
        ema200 = round(EMAIndicator(close=close, window=200).ema_indicator().iloc[-1], 2)
        price = close.iloc[-1]
        result["ema"] = {
            "ema20": ema20, "ema50": ema50, "ema200": ema200,
            "trend": _ema_trend(price, ema20, ema50, ema200),
        }
    except Exception:
        pass

    try:
        atr = round(AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1], 2)
        result["atr"] = atr
    except Exception:
        pass

    return result


def fetch_all_indicators(symbols: list, period: str = "1y") -> dict:
    """Batch-download history for all symbols and compute indicators."""
    print(f"  Downloading {len(symbols)} symbols for technical analysis...")
    results = {}

    try:
        raw = yf.download(
            symbols,
            period=period,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
        )
    except Exception as e:
        print(f"  Warning: Batch download failed: {e}")
        return {}

    for symbol in symbols:
        try:
            if len(symbols) == 1:
                df = raw
            else:
                df = raw[symbol] if symbol in raw.columns.get_level_values(0) else None

            if df is None or df.empty:
                continue

            indicators = compute_indicators(df)
            if indicators:
                results[symbol] = indicators
                print(f"  TA computed: {symbol}")
        except Exception as e:
            print(f"  Warning: TA failed for {symbol}: {e}")

    return results


def format_indicators(symbol: str, ind: dict, current_price: float) -> str:
    """Format indicators into a compact string for the Groq prompt."""
    if not ind:
        return f"{symbol}: Technical data unavailable"

    lines = [f"{symbol} Technical Analysis:"]

    if "rsi" in ind:
        r = ind["rsi"]
        lines.append(f"  RSI(14): {r['value']} → {r['signal']}")

    if "macd" in ind:
        m = ind["macd"]
        lines.append(f"  MACD: {m['trend']} | Histogram: {m['histogram']:+.3f}")

    if "bbands" in ind:
        b = ind["bbands"]
        lines.append(
            f"  Bollinger Bands: Upper={b['upper']} | Mid={b['middle']} | Lower={b['lower']}"
        )
        lines.append(f"  BB Position: {b['position']} (%B={b['pct_b']}%)")

    if "ema" in ind:
        e = ind["ema"]
        lines.append(
            f"  EMA20={e['ema20']} | EMA50={e['ema50']} | EMA200={e['ema200']}"
        )
        lines.append(f"  EMA Trend: {e['trend']}")

    if "atr" in ind:
        lines.append(
            f"  ATR(14): {ind['atr']} → Stop loss suggestion: ±{ind['atr']} from entry"
        )

    return "\n".join(lines)
