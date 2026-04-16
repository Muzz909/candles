"""
signal_engine.py  —  Nifty Options Signal Engine v2
Full candle pattern library based on candle_options_framework.html
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, date
import requests
import warnings
warnings.filterwarnings("ignore")

IST_OFFSET = 5.5  # hours ahead of UTC


# ──────────────────────────────────────────────────────────────
# 1. DATA FETCHING
# ──────────────────────────────────────────────────────────────

def fetch_nifty_data(interval="5m", period="1d"):
    """
    Fetch OHLCV for Nifty 50.
    interval: '1m', '2m', '3m', '5m', '15m'
    Most accurate free source: yfinance ^NSEI
    1m data available for last 7 days, 5m for last 60 days.
    """
    ticker = yf.Ticker("^NSEI")
    df = ticker.history(period=period, interval=interval, auto_adjust=True)
    if df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index)
    # Convert to IST if timezone-aware
    try:
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        if df.index.tz is not None:
            df.index = df.index.tz_convert(ist)
        else:
            df.index = df.index.tz_localize("UTC").tz_convert(ist)
    except Exception:
        pass
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.dropna()
    # Filter market hours 9:15–15:30
    try:
        df = df.between_time("09:15", "15:35")
    except Exception:
        pass
    return df


def fetch_nifty_both_timeframes():
    """Fetch both 1m and 5m data in one call."""
    df1 = fetch_nifty_data(interval="1m", period="1d")
    df5 = fetch_nifty_data(interval="5m", period="2d")
    return df1, df5


def fetch_vix():
    try:
        v = yf.Ticker("^INDIAVIX")
        hist = v.history(period="1d", interval="5m")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return None


def fetch_advance_decline():
    """
    Fetch Nifty 50 constituent data to compute advance/decline ratio.
    Uses a subset of Nifty 50 tickers available on yfinance.
    """
    nifty50 = [
        "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
        "HINDUNILVR.NS","ITC.NS","SBIN.NS","BHARTIARTL.NS","KOTAKBANK.NS",
        "LT.NS","AXISBANK.NS","ASIANPAINT.NS","HCLTECH.NS","MARUTI.NS",
        "SUNPHARMA.NS","TITAN.NS","BAJFINANCE.NS","ULTRACEMCO.NS","WIPRO.NS",
        "NTPC.NS","POWERGRID.NS","NESTLEIND.NS","TECHM.NS","ONGC.NS",
        "JSWSTEEL.NS","TATAMOTORS.NS","TATASTEEL.NS","ADANIENT.NS","M&M.NS",
        "BAJAJFINSV.NS","DRREDDY.NS","DIVISLAB.NS","GRASIM.NS","CIPLA.NS",
        "EICHERMOT.NS","HEROMOTOCO.NS","APOLLOHOSP.NS","TATACONSUM.NS","COALINDIA.NS",
        "BRITANNIA.NS","BPCL.NS","INDUSINDBK.NS","HINDALCO.NS","SBILIFE.NS",
        "HDFCLIFE.NS","UPL.NS","BAJAJ-AUTO.NS","ADANIPORTS.NS","VEDL.NS"
    ]
    try:
        data = yf.download(nifty50, period="2d", interval="1d",
                           progress=False, auto_adjust=True)["Close"]
        if data.shape[0] < 2:
            return None, None, None
        today = data.iloc[-1]
        yesterday = data.iloc[-2]
        pct_change = ((today - yesterday) / yesterday * 100).dropna()
        advances = int((pct_change > 0).sum())
        declines = int((pct_change < 0).sum())
        unchanged = int((pct_change == 0).sum())
        return advances, declines, unchanged
    except Exception:
        return None, None, None


def fetch_option_chain():
    """Fetch Nifty option chain from NSE."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com",
        "Accept-Language": "en-US,en;q=0.9",
    }
    s = requests.Session()
    try:
        s.get("https://www.nseindia.com", headers=headers, timeout=6)
        r = s.get(
            "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
            headers=headers, timeout=8
        )
        data = r.json()
        spot = float(data["records"]["underlyingValue"])
        records = data["records"]["data"]

        call_oi_total = put_oi_total = 0
        strike_data = {}
        for rec in records:
            sp = rec.get("strikePrice", 0)
            ce = rec.get("CE", {})
            pe = rec.get("PE", {})
            c_oi = ce.get("openInterest", 0) or 0
            p_oi = pe.get("openInterest", 0) or 0
            c_chg = ce.get("changeinOpenInterest", 0) or 0
            p_chg = pe.get("changeinOpenInterest", 0) or 0
            call_oi_total += c_oi
            put_oi_total += p_oi
            strike_data[sp] = {
                "call_oi": c_oi, "put_oi": p_oi,
                "call_ltp": ce.get("lastPrice", 0) or 0,
                "put_ltp": pe.get("lastPrice", 0) or 0,
                "call_iv": ce.get("impliedVolatility", 0) or 0,
                "put_iv": pe.get("impliedVolatility", 0) or 0,
                "call_oi_chg": c_chg, "put_oi_chg": p_chg,
            }

        pcr = round(put_oi_total / call_oi_total, 3) if call_oi_total > 0 else None
        atm = min(strike_data.keys(), key=lambda x: abs(x - spot))
        return pcr, atm, call_oi_total, put_oi_total, spot, strike_data
    except Exception:
        return None, None, None, None, None, {}


# ──────────────────────────────────────────────────────────────
# 2. TECHNICAL INDICATORS
# ──────────────────────────────────────────────────────────────

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    return 100 - (100 / (1 + rs))


def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    return macd, sig, macd - sig


def compute_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    return (tp * df["volume"]).cumsum() / df["volume"].cumsum()


def compute_bollinger(series, period=20, std=2):
    sma = series.rolling(period).mean()
    s = series.rolling(period).std()
    return sma + std * s, sma, sma - std * s


def compute_atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def add_indicators(df):
    if df.empty or len(df) < 5:
        return df
    df = df.copy()
    df["rsi"] = compute_rsi(df["close"])
    df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["macd"], df["macd_sig"], df["macd_hist"] = compute_macd(df["close"])
    df["vwap"] = compute_vwap(df)
    df["bb_upper"], df["bb_mid"], df["bb_lower"] = compute_bollinger(df["close"])
    df["atr"] = compute_atr(df)
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / (df["vol_avg20"] + 1e-10)
    # Candle geometry
    df["body"]        = df["close"] - df["open"]
    df["body_size"]   = df["body"].abs()
    df["upper_wick"]  = df["high"] - df[["open","close"]].max(axis=1)
    df["lower_wick"]  = df[["open","close"]].min(axis=1) - df["low"]
    df["candle_range"]= df["high"] - df["low"]
    df["body_ratio"]  = df["body_size"] / (df["candle_range"] + 1e-10)
    # 20-bar rolling high/low for breakout detection
    df["high20"] = df["high"].rolling(20).max()
    df["low20"]  = df["low"].rolling(20).min()
    return df


# ──────────────────────────────────────────────────────────────
# 3. DEEP CANDLE ANALYSIS  (framework rules + advanced patterns)
# ──────────────────────────────────────────────────────────────

def analyze_candle(df):
    """
    Returns a full candle analysis dict:
      pattern, direction (+2 to -2), description,
      framework_rule (from HTML), confidence, action_hint
    """
    if len(df) < 5:
        return _candle_result("No data", 0, "Insufficient candles")

    c  = df.iloc[-1]  # current (closed)
    p  = df.iloc[-2]
    p2 = df.iloc[-3]
    p3 = df.iloc[-4]

    body       = c["body"]
    body_size  = c["body_size"]
    body_ratio = c["body_ratio"]
    candle_rng = c["candle_range"]
    upper_wick = c["upper_wick"]
    lower_wick = c["lower_wick"]
    vwap       = c.get("vwap", None)
    price      = c["close"]
    vol_ratio  = c.get("vol_ratio", 1.0)
    ema20      = c.get("ema20", price)
    ema50      = c.get("ema50", price)

    above_vwap = (price > vwap) if pd.notna(vwap) else None
    ema_bull   = (ema20 > ema50) if pd.notna(ema20) and pd.notna(ema50) else None

    # ── FRAMEWORK RULE: Avoid first candles (9:15–9:25) ──
    try:
        candle_time = c.name.time() if hasattr(c.name, 'time') else None
        from datetime import time as dtime
        if candle_time and dtime(9,15) <= candle_time <= dtime(9,25):
            return _candle_result(
                "Opening noise (9:15–9:25)", 0,
                "Framework Rule: First 2–3 candles are erratic. Market makers adjusting, gap fills in progress. AVOID all trades.",
                "AVOID", confidence="LOW", avoid=True
            )
    except Exception:
        pass

    # ── AVOID: Both-side wicks > 2× body ──
    if upper_wick > 2 * body_size and lower_wick > 2 * body_size and body_size > 0:
        return _candle_result(
            "Long-wick indecision (both sides)", 0,
            "Framework Rule: Wicks longer than 2× body on BOTH sides — complete indecision. Market spiked both ways. No directional signal. AVOID.",
            "AVOID", confidence="LOW", avoid=True
        )

    # ── DOJI ──
    if body_ratio < 0.1:
        after_trend = "uptrend" if p["body"] > 0 and p2["body"] > 0 else ("downtrend" if p["body"] < 0 and p2["body"] < 0 else "range")
        return _candle_result(
            f"Doji ({after_trend})", 0,
            f"Framework Rule: Doji after {after_trend} — market pausing to decide. Buying options here means paying theta while waiting. Sit on hands. Wait for the next resolution candle.",
            "AVOID", confidence="LOW", avoid=True
        )

    # ── HAMMER ──
    if lower_wick > 2 * body_size and upper_wick < 0.4 * body_size and candle_rng > 0:
        if p["body"] < 0 or p2["body"] < 0:  # after decline
            vwap_note = "at/below VWAP — institutions defended this level" if above_vwap is False or abs(price - vwap) < candle_rng * 0.5 else "confirm VWAP hold"
            vol_note  = f"Volume {vol_ratio:.1f}× avg — {'strong conviction' if vol_ratio > 1.5 else 'moderate'}"
            return _candle_result(
                "Hammer", +2,
                f"Framework Rule (CALL): Buyers rejected lower prices aggressively. Long lower wick = demand. {vwap_note}. {vol_note}. WAIT for next candle to close GREEN before entering. ATM or slightly ITM CALL after confirmation.",
                "CALL", confidence="HIGH" if vol_ratio > 1.5 else "MEDIUM"
            )
        return _candle_result(
            "Hanging Man", -1,
            "Hanging Man: Long lower wick after uptrend. Potential exhaustion. Not a strong PUT setup alone — wait for confirmation red candle.",
            "CAUTION", confidence="LOW"
        )

    # ── SHOOTING STAR / GRAVESTONE ──
    if upper_wick > 2 * body_size and lower_wick < 0.4 * body_size and candle_rng > 0:
        if p["body"] > 0 or p2["body"] > 0:  # after advance
            vwap_note = "at/above VWAP — sellers stepped in at the average" if above_vwap else "price already below VWAP"
            return _candle_result(
                "Shooting Star", -2,
                f"Framework Rule (PUT): Bulls pushed higher, got rejected hard. {vwap_note}. Long upper wick = sellers aggressive. WAIT for next candle to be RED before entering PUTs.",
                "PUT", confidence="HIGH" if vol_ratio > 1.2 else "MEDIUM"
            )

    # ── GRAVESTONE DOJI (green candle with very long upper wick) ──
    if upper_wick > 2.5 * body_size and body > 0 and lower_wick < 0.3 * body_size:
        return _candle_result(
            "Gravestone / Bearish disguise", -2,
            "Framework Rule (PUT): Green candle with very long upper wick — bearish candle in disguise. Tried to rally, got rejected, closed near open. Near day's high? Strong PUT signal.",
            "PUT", confidence="MEDIUM"
        )

    # ── BULLISH ENGULFING ──
    if p["body"] < 0 and body > 0:
        if c["open"] <= p["close"] and c["close"] >= p["open"]:
            at_support = _near_support(price, df)
            return _candle_result(
                "Bullish Engulfing", +2,
                f"Framework Rule (CALL): Red candle followed by larger green candle. Sellers overwhelmed. {'At support level — high-conviction setup.' if at_support else 'Stronger if at support/VWAP.'} ATM or slightly ITM CALL. Green body must be ≥ red body size.",
                "CALL", confidence="HIGH" if at_support else "MEDIUM"
            )

    # ── BEARISH ENGULFING ──
    if p["body"] > 0 and body < 0:
        if c["open"] >= p["close"] and c["close"] <= p["open"]:
            at_resistance = _near_resistance(price, df)
            return _candle_result(
                "Bearish Engulfing", -2,
                f"Framework Rule (PUT): Green candle followed by larger red candle. Buyers overwhelmed. {'At resistance — one of the strongest PUT setups in index options.' if at_resistance else 'Stronger if at resistance/VWAP.'} ATM or 1-strike ITM PUT.",
                "PUT", confidence="HIGH" if at_resistance else "MEDIUM"
            )

    # ── MORNING STAR ──
    if (p2["body"] < 0 and abs(p["body_size"]) < 0.35 * p2["body_size"]
            and body > 0 and c["close"] > (p2["open"] + p2["close"]) / 2):
        return _candle_result(
            "Morning Star", +2,
            "Morning Star: 3-candle bullish reversal. Big red → small indecision → big green. Sellers exhausted, buyers taking control. Strong CALL setup.",
            "CALL", confidence="HIGH"
        )

    # ── EVENING STAR ──
    if (p2["body"] > 0 and abs(p["body_size"]) < 0.35 * p2["body_size"]
            and body < 0 and c["close"] < (p2["open"] + p2["close"]) / 2):
        return _candle_result(
            "Evening Star", -2,
            "Evening Star: 3-candle bearish reversal. Big green → small indecision → big red. Buyers exhausted, sellers taking control. Strong PUT setup.",
            "PUT", confidence="HIGH"
        )

    # ── BREAKOUT CANDLE (above 20-bar high) ──
    high20 = df["high"].rolling(20).max().iloc[-2]  # use previous bar's 20-high
    low20  = df["low"].rolling(20).min().iloc[-2]
    if body > 0 and body_ratio > 0.6 and c["close"] > high20:
        return _candle_result(
            "Breakout candle (above 20-bar high)", +2,
            f"Framework Rule (CALL): Big green body closing above the 20-bar high — price broke resistance with conviction. Not a doji, not small — a real candle. Dashboard: STRONG BUY. OTM CALL buying works here because momentum can carry quickly. Vol {vol_ratio:.1f}× avg.",
            "CALL", confidence="HIGH" if vol_ratio > 1.5 else "MEDIUM"
        )

    # ── BREAKDOWN CANDLE (below 20-bar low) ──
    if body < 0 and body_ratio > 0.6 and c["close"] < low20:
        return _candle_result(
            "Breakdown candle (below 20-bar low)", -2,
            f"Framework Rule (PUT): Big red body closing below the 20-bar low — price broke support convincingly. Dashboard: STRONG SELL. OTM PUT buying works if ATR is high enough. Vol {vol_ratio:.1f}× avg.",
            "PUT", confidence="HIGH" if vol_ratio > 1.5 else "MEDIUM"
        )

    # ── THREE WHITE SOLDIERS ──
    prev3 = df.iloc[-3:]
    if all(prev3["body"] > 0) and len(prev3) == 3:
        sizes_increasing = prev3["body_size"].is_monotonic_increasing
        if (prev3["close"].is_monotonic_increasing):
            return _candle_result(
                "Three White Soldiers", +2,
                f"Framework Rule (CALL): 2–3 consecutive green candles of increasing size, each closing higher. {'Bodies growing — buyers adding, not hesitating.' if sizes_increasing else 'Momentum building.'} Ride with CALLs but set a stop.",
                "CALL", confidence="HIGH" if sizes_increasing else "MEDIUM"
            )

    # ── THREE BLACK CROWS ──
    if all(prev3["body"] < 0) and len(prev3) == 3:
        if (prev3["close"].is_monotonic_decreasing):
            return _candle_result(
                "Three Black Crows", -2,
                "Three Black Crows: 3 consecutive red candles, each closing lower. Sellers in full control. Strong PUT continuation setup.",
                "PUT", confidence="HIGH"
            )

    # ── BIG GREEN ABOVE VWAP ──
    if body > 0 and body_ratio > 0.65 and above_vwap:
        ema_note = "EMA20 > EMA50 — trend aligned" if ema_bull else "check EMA alignment"
        return _candle_result(
            "Big green body above VWAP", +1,
            f"Framework Rule (CALL): Price opened and closed well above the intraday average. Institutions net buyers. {ema_note}. Strong CALL setup.",
            "CALL", confidence="MEDIUM"
        )

    # ── BIG RED BELOW VWAP ──
    if body < 0 and body_ratio > 0.65 and above_vwap is False:
        ema_note = "EMA20 < EMA50 — trend aligned" if ema_bull is False else "check EMA alignment"
        return _candle_result(
            "Big red body below VWAP", -1,
            f"Framework Rule (PUT): Selling pressure dominant, price below intraday average. Institutions net sellers. {ema_note}. Clean PUT setup.",
            "PUT", confidence="MEDIUM"
        )

    # ── GREEN BELOW VWAP (trap) ──
    if body > 0 and above_vwap is False and body_ratio > 0.5:
        return _candle_result(
            "Green candle below VWAP (trap)", 0,
            "Framework Rule (AVOID): Green candle but closing below VWAP — don't be fooled by the colour. Price still below institutional average. Context > colour.",
            "CAUTION", confidence="LOW"
        )

    # ── CHOPPY / SMALL BODIES (lunch-hour pattern) ──
    recent_bodies = df["body_size"].iloc[-4:]
    avg_body = df["body_size"].iloc[-20:].mean()
    if (recent_bodies < 0.3 * avg_body).all() and avg_body > 0:
        return _candle_result(
            "Multiple small bodies (choppy)", 0,
            "Framework Rule (AVOID): Multiple small-bodied candles in a row — NIFTY is chopping sideways. Option premium bleeds from theta decay. Likely lunch-hour trap (12:30–13:30 IST). Wait for expansion.",
            "AVOID", confidence="LOW", avoid=True
        )

    # ── GENERIC STRONG CANDLES ──
    if body > 0 and body_ratio > 0.7:
        return _candle_result(
            "Strong bullish candle", +1,
            f"Strong green body ({body_ratio*100:.0f}% of range). Vol {vol_ratio:.1f}× avg. Bullish momentum. Confirm with VWAP and trend before entering CALL.",
            "CALL", confidence="LOW"
        )
    if body < 0 and body_ratio > 0.7:
        return _candle_result(
            "Strong bearish candle", -1,
            f"Strong red body ({body_ratio*100:.0f}% of range). Vol {vol_ratio:.1f}× avg. Bearish momentum. Confirm with VWAP and trend before entering PUT.",
            "PUT", confidence="LOW"
        )

    return _candle_result("Neutral / unclear candle", 0,
                          "No dominant pattern detected. Framework Rule 4: Look at 3–5 candles together — read the conversation, not just one sentence.",
                          "WAIT", confidence="LOW")


def _candle_result(pattern, direction, description, signal_type="WAIT",
                   confidence="MEDIUM", avoid=False):
    return {
        "pattern": pattern,
        "direction": direction,
        "description": description,
        "signal_type": signal_type,  # CALL / PUT / AVOID / WAIT / CAUTION
        "confidence": confidence,
        "avoid": avoid,
    }


def _near_support(price, df, pct=0.003):
    lows = df["low"].rolling(20).min().dropna()
    for s in lows.tail(5):
        if abs(price - s) / price < pct:
            return True
    return False


def _near_resistance(price, df, pct=0.003):
    highs = df["high"].rolling(20).max().dropna()
    for r in highs.tail(5):
        if abs(price - r) / price < pct:
            return True
    return False


def find_sr_levels(df, n=3):
    if len(df) < 20:
        return [], []
    highs_series = df["high"].rolling(20).max()
    lows_series  = df["low"].rolling(20).min()
    res = sorted(df.loc[df["high"] == highs_series, "high"]
                 .drop_duplicates().nlargest(n).tolist(), reverse=True)
    sup = sorted(df.loc[df["low"] == lows_series, "low"]
                 .drop_duplicates().nsmallest(n).tolist())
    return sup, res


# ──────────────────────────────────────────────────────────────
# 4. MASTER SIGNAL GENERATOR
# ──────────────────────────────────────────────────────────────

def generate_signal(df5, df1=None, pcr=None, vix=None, advances=None, declines=None):
    """Full signal computation on 5m data (with 1m candle read-through)."""
    if df5 is None or len(df5) < 30:
        return _empty_signal("Insufficient 5m data")

    df5 = add_indicators(df5)
    latest = df5.iloc[-1]
    price  = float(latest["close"])

    score   = 0
    reasons = []
    detail  = {}

    # ── Candle (5m) ──
    candle5 = analyze_candle(df5)
    cd = candle5["direction"]
    score += cd
    detail["candle5m"] = candle5
    reasons.append(f"5m candle: {candle5['pattern']} ({_fmt(cd)})")

    # ── Candle (1m) if available ──
    candle1 = None
    if df1 is not None and len(df1) >= 10:
        df1i = add_indicators(df1)
        candle1 = analyze_candle(df1i)
        # 1m candle has lower weight
        c1d = candle1["direction"] * 0.5
        score += c1d
        detail["candle1m"] = candle1
        reasons.append(f"1m candle: {candle1['pattern']} ({_fmt(c1d)})")

    # ── RSI ──
    rsi = float(latest["rsi"]) if pd.notna(latest["rsi"]) else 50
    if rsi < 30:       rs, rn = +2, "RSI oversold — bounce setup"
    elif rsi < 40:     rs, rn = +1, "RSI recovering"
    elif 40 <= rsi <= 60: rs, rn = 0, "RSI neutral"
    elif rsi <= 70:    rs, rn = -1, "RSI approaching overbought"
    else:              rs, rn = -2, "RSI overbought — pullback risk"
    score += rs
    detail["rsi"] = {"value": round(rsi, 1), "score": rs, "note": rn}
    reasons.append(f"{rn} ({round(rsi,1)}) ({_fmt(rs)})")

    # ── MACD ──
    mh  = float(latest["macd_hist"])   if pd.notna(latest["macd_hist"])  else 0
    pmh = float(df5.iloc[-2]["macd_hist"]) if pd.notna(df5.iloc[-2]["macd_hist"]) else 0
    if mh > 0 and pmh <= 0:   ms, mn = +2, "MACD bullish crossover"
    elif mh < 0 and pmh >= 0: ms, mn = -2, "MACD bearish crossover"
    elif mh > 0:               ms, mn = +1, "MACD positive"
    elif mh < 0:               ms, mn = -1, "MACD negative"
    else:                      ms, mn = 0,  "MACD flat"
    score += ms
    detail["macd"] = {"value": round(mh, 2), "score": ms, "note": mn}
    reasons.append(f"{mn} ({_fmt(ms)})")

    # ── VWAP ──
    vwap_val  = float(latest["vwap"]) if pd.notna(latest["vwap"]) else price
    vwap_diff = (price - vwap_val) / vwap_val * 100
    if vwap_diff > 0.2:      vs, vn = +1, f"Price above VWAP (+{vwap_diff:.2f}%)"
    elif vwap_diff < -0.2:   vs, vn = -1, f"Price below VWAP ({vwap_diff:.2f}%)"
    else:                    vs, vn = 0,  f"Price near VWAP ({vwap_diff:.2f}%)"
    score += vs
    detail["vwap"] = {"value": round(vwap_val, 2), "score": vs, "note": vn}
    reasons.append(f"{vn} ({_fmt(vs)})")

    # ── EMA trend ──
    e9  = float(latest["ema9"])
    e20 = float(latest["ema20"])
    e50 = float(latest["ema50"])
    if price > e9 > e20 > e50:         es, en = +2, "Price > EMA9 > EMA20 > EMA50 (strong uptrend)"
    elif price < e9 < e20 < e50:       es, en = -2, "Price < EMA9 < EMA20 < EMA50 (strong downtrend)"
    elif e9 > e20:                     es, en = +1, "EMA9 > EMA20 (bullish)"
    elif e9 < e20:                     es, en = -1, "EMA9 < EMA20 (bearish)"
    else:                              es, en = 0,  "EMAs flat"
    score += es
    detail["ema"] = {"e9": round(e9,2), "e20": round(e20,2), "e50": round(e50,2), "score": es, "note": en}
    reasons.append(f"{en} ({_fmt(es)})")

    # ── Volume ──
    vr = float(latest["vol_ratio"]) if pd.notna(latest["vol_ratio"]) else 1.0
    cb = float(latest["body"])
    if vr > 2.0 and cb > 0:    vols, voln = +2, f"High-vol green candle ({vr:.1f}×)"
    elif vr > 2.0 and cb < 0:  vols, voln = -2, f"High-vol red candle ({vr:.1f}×)"
    elif vr > 1.5 and cb > 0:  vols, voln = +1, f"Above-avg vol bullish ({vr:.1f}×)"
    elif vr > 1.5 and cb < 0:  vols, voln = -1, f"Above-avg vol bearish ({vr:.1f}×)"
    else:                       vols, voln = 0,  f"Normal volume ({vr:.1f}×)"
    score += vols
    detail["volume"] = {"value": round(vr, 2), "score": vols, "note": voln}
    reasons.append(f"{voln} ({_fmt(vols)})")

    # ── Support / Resistance ──
    sup, res = find_sr_levels(df5)
    srs = 0; srn = "Between S/R levels"
    thr = price * 0.003
    for s in sup:
        if abs(price - s) <= thr:
            srs, srn = +1, f"Near support {s:.0f}"; break
    for r in res:
        if abs(price - r) <= thr:
            srs, srn = -1, f"Near resistance {r:.0f}"; break
    score += srs
    detail["sr"] = {"support": [round(x) for x in sup], "resistance": [round(x) for x in res], "score": srs, "note": srn}
    reasons.append(f"S/R: {srn} ({_fmt(srs)})")

    # ── Bollinger Bands ──
    bbu = float(latest["bb_upper"]) if pd.notna(latest["bb_upper"]) else price * 1.01
    bbl = float(latest["bb_lower"]) if pd.notna(latest["bb_lower"]) else price * 0.99
    if price >= bbu:     bbs, bbn = -1, "At upper BB (overbought)"
    elif price <= bbl:   bbs, bbn = +1, "At lower BB (oversold)"
    else:                bbs, bbn = 0,  "Inside Bollinger Bands"
    score += bbs
    detail["bb"] = {"upper": round(bbu,2), "lower": round(bbl,2), "score": bbs, "note": bbn}
    reasons.append(f"BB: {bbn} ({_fmt(bbs)})")

    # ── PCR ──
    if pcr is not None:
        if pcr < 0.7:         ps, pn = +1, f"PCR {pcr} — call buyers dominant"
        elif pcr > 1.3:       ps, pn = -1, f"PCR {pcr} — put buyers dominant"
        elif pcr <= 1.0:      ps, pn = +1, f"PCR {pcr} — slightly bullish"
        else:                 ps, pn = 0,  f"PCR {pcr} — neutral"
        score += ps
        detail["pcr"] = {"value": pcr, "score": ps, "note": pn}
        reasons.append(f"{pn} ({_fmt(ps)})")

    # ── Advance / Decline ──
    if advances is not None and declines is not None:
        total_ad = (advances + declines) or 1
        ad_ratio = advances / total_ad
        if ad_ratio > 0.65:     ads, adn = +1, f"A/D bullish ({advances}↑ / {declines}↓)"
        elif ad_ratio < 0.35:   ads, adn = -1, f"A/D bearish ({advances}↑ / {declines}↓)"
        else:                   ads, adn = 0,  f"A/D mixed ({advances}↑ / {declines}↓)"
        score += ads
        detail["advance_decline"] = {"advances": advances, "declines": declines, "score": ads, "note": adn}
        reasons.append(f"{adn} ({_fmt(ads)})")

    # ── VIX ──
    vix_warn = None
    if vix:
        if vix > 22:   vix_warn = f"⚠ VIX {vix} — HIGH volatility, options expensive, cut size"
        elif vix < 12: vix_warn = f"ℹ VIX {vix} — LOW volatility, limited premium moves"

    # ── ATR ──
    atr_val = float(latest["atr"]) if pd.notna(latest["atr"]) else 30
    min_move_note = None
    if atr_val < 25:
        min_move_note = f"⚠ ATR {atr_val:.1f} — Framework Rule 5: Small ATR, option premium may not be worth the risk"

    # ── FINAL DECISION ──
    score = round(score, 1)
    if score >= 6:
        signal = "🟢 BUY CALL"
        sig_short = "BUY CALL"
        confidence = "HIGH"
        strike = "ATM or 1-strike ITM call"
        sl  = round(price - 1.5 * atr_val)
        tgt = round(price + 2.5 * atr_val)
    elif score >= 3.5:
        signal = "🟡 WEAK CALL"
        sig_short = "WEAK CALL"
        confidence = "MEDIUM"
        strike = "ATM call — small size"
        sl  = round(price - atr_val)
        tgt = round(price + 2.0 * atr_val)
    elif score <= -6:
        signal = "🔴 BUY PUT"
        sig_short = "BUY PUT"
        confidence = "HIGH"
        strike = "ATM or 1-strike ITM put"
        sl  = round(price + 1.5 * atr_val)
        tgt = round(price - 2.5 * atr_val)
    elif score <= -3.5:
        signal = "🟡 WEAK PUT"
        sig_short = "WEAK PUT"
        confidence = "MEDIUM"
        strike = "ATM put — small size"
        sl  = round(price + atr_val)
        tgt = round(price - 2.0 * atr_val)
    else:
        signal = "⚪ WAIT"
        sig_short = "WAIT"
        confidence = "—"
        strike = "No trade"
        sl = tgt = None

    rr = None
    if sl and tgt and sl != price:
        rr = round(abs(tgt - price) / abs(price - sl), 1)

    return {
        "signal": signal,
        "sig_short": sig_short,
        "score": score,
        "confidence": confidence,
        "price": round(price, 2),
        "vwap": round(vwap_val, 2),
        "rsi": round(rsi, 1),
        "atr": round(atr_val, 2),
        "ema9": round(e9, 2),
        "ema20": round(e20, 2),
        "ema50": round(e50, 2),
        "macd_hist": round(mh, 3),
        "bb_upper": round(bbu, 2),
        "bb_lower": round(bbl, 2),
        "vol_ratio": round(vr, 2),
        "candle5m": candle5,
        "candle1m": candle1,
        "support": detail.get("sr", {}).get("support", []),
        "resistance": detail.get("sr", {}).get("resistance", []),
        "strike": strike,
        "stop_loss": sl,
        "target": tgt,
        "rr_ratio": rr,
        "reasons": reasons,
        "detail": detail,
        "vix": vix,
        "vix_warning": vix_warn,
        "pcr": pcr,
        "advances": advances,
        "declines": declines,
        "atr_warning": min_move_note,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _empty_signal(reason):
    return {"signal": "⚪ WAIT", "sig_short": "WAIT", "score": 0,
            "confidence": "—", "price": None, "reasons": [reason],
            "candle5m": None, "candle1m": None, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}


def _fmt(v):
    return f"+{v}" if v > 0 else str(v)
