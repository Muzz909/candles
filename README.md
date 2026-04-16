# NIFTY Options Signal Dashboard v2

A deep-signal intraday tool for NIFTY 50 options (CALL/PUT) built on Streamlit.

---

## Files

```
nifty-signal/
├── app.py              ← Streamlit dashboard
├── signal_engine.py    ← Signal engine (candles + indicators + A/D)
├── requirements.txt    ← Dependencies
└── README.md
```

---

## Setup (local)

```bash
# 1. Clone / create repo
git clone https://github.com/YOUR_USERNAME/nifty-signal.git
cd nifty-signal

# 2. Virtual environment
python -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Install
pip install -r requirements.txt

# 4. Run
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Deploy to Streamlit Cloud (free, 1 click)

1. Push to GitHub: `git add . && git commit -m "init" && git push`
2. Go to https://streamlit.io/cloud → New App
3. Select your repo, set **Main file: `app.py`**
4. Click Deploy

---

## Data sources

| Source | What | Lag | Key |
|--------|------|-----|-----|
| yfinance `^NSEI` | Nifty OHLCV 1m/5m | ~1–2 min | None |
| yfinance `^INDIAVIX` | India VIX | ~5 min | None |
| NSE public API | Option chain, PCR | ~5 min | None |
| yfinance Nifty50 stocks | Advance/Decline | ~15 min | None |

All free. No API key needed.

> **Note on 1m data:** yfinance provides 1m data for the last 7 days only. During live market hours it works perfectly for intraday use.

---

## Signal scoring system

Each of the 10 indicators contributes a weighted score:

| Indicator | Max contribution |
|-----------|-----------------|
| 5m candle pattern | ±2 |
| 1m candle pattern | ±1 (half weight) |
| RSI | ±2 |
| MACD | ±2 |
| VWAP position | ±1 |
| EMA9/20/50 trend | ±2 |
| Volume ratio | ±2 |
| Support/Resistance | ±1 |
| Bollinger Bands | ±1 |
| PCR | ±1 |
| Advance/Decline | ±1 |

**Decision thresholds:**

| Score | Signal |
|-------|--------|
| ≥ 6 | 🟢 BUY CALL (High confidence) |
| 3.5 to 5.9 | 🟡 WEAK CALL (Medium) |
| −3.4 to 3.4 | ⚪ WAIT |
| −3.5 to −5.9 | 🟡 WEAK PUT (Medium) |
| ≤ −6 | 🔴 BUY PUT (High confidence) |

---

## Candle patterns detected (from framework)

**CALL setups:** Hammer at VWAP, Bullish Engulfing at support, Breakout above 20-bar high, Three White Soldiers, Big green above VWAP, Morning Star

**PUT setups:** Shooting Star, Bearish Engulfing at resistance, Breakdown below 20-bar low, Gravestone / long-upper-wick green, Three Black Crows, Big red below VWAP

**AVOID:** Doji, opening candles 9:15–9:25, choppy small bodies, long-wick-both-sides, green below VWAP

---

## Auto-refresh behaviour

- Refreshes every **30 seconds** when market is open (9:00 AM – 3:40 PM IST, Mon–Fri)
- Pauses automatically outside market hours
- Toggle button in the UI to turn off anytime
- "Force Refresh" button for manual data pull anytime

---

## IMPORTANT TRADING NOTES

- **Never trade the first 15 minutes** (9:15–9:30): Opening candles are erratic (framework rule)
- **High VIX (>22)**: Options are expensive, reduce position size by 50%
- **Low ATR (<25 points)**: Premium may not justify the risk (framework rule 5)
- **Candle alone is not a signal** — framework rule 1: Candle + Location = Signal
- **Wait for candle close** — framework rule 2: Never anticipate mid-candle
- **Lunch hours 12:30–13:30**: High theta bleed risk in choppy conditions
- **Expiry day after 14:00**: Pin risk creates fake moves, avoid

**This is a signal tool, not financial advice. Always use stop-losses.**
