"""
app.py  —  Nifty Options Signal Dashboard v2
Deep candle signal card · 1m/5m zoom tabs · A/D ratio · Auto-refresh (market hours only)
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, time as dtime
import time
import pytz

from signal_engine import (
    fetch_nifty_data, fetch_nifty_both_timeframes,
    fetch_vix, fetch_option_chain, fetch_advance_decline,
    add_indicators, find_sr_levels, generate_signal
)

# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NIFTY Signal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN  = dtime(9, 0)
MARKET_CLOSE = dtime(15, 40)

# ──────────────────────────────────────────────────────────────
# STYLES
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }

/* ── Signal banner ── */
.signal-banner {
    border-radius: 12px;
    padding: 18px 24px;
    text-align: center;
    margin-bottom: 4px;
}
.banner-call  { background: linear-gradient(135deg,#0a2e14 0%,#0d3d1e 100%); border: 1px solid #1a9e5c; }
.banner-put   { background: linear-gradient(135deg,#2e0a0a 0%,#3d0d0d 100%); border: 1px solid #d94040; }
.banner-weak  { background: linear-gradient(135deg,#2e2a00 0%,#3d3800 100%); border: 1px solid #c8a600; }
.banner-wait  { background: linear-gradient(135deg,#111 0%,#1a1a1a 100%);   border: 1px solid #333; }
.banner-title { font-family: 'JetBrains Mono', monospace; font-size: 2rem; font-weight: 700; letter-spacing: 0.05em; margin: 0; }
.banner-call  .banner-title { color: #3ddc84; }
.banner-put   .banner-title { color: #ff6b6b; }
.banner-weak  .banner-title { color: #ffd060; }
.banner-wait  .banner-title { color: #888; }
.banner-sub   { font-size: 0.8rem; color: #666; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }

/* ── Score bar ── */
.score-track {
    background: #1a1a1a;
    border-radius: 8px;
    height: 12px;
    width: 100%;
    overflow: hidden;
    margin: 8px 0;
    position: relative;
    border: 0.5px solid #333;
}
.score-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.4s ease;
}

/* ── Candle card ── */
.candle-card {
    background: #0d0d0d;
    border: 0.5px solid #222;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 10px;
    position: relative;
}
.candle-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
}
.candle-badge {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.05em;
    font-family: 'JetBrains Mono', monospace;
}
.badge-call    { background: #0d3d1e; color: #3ddc84; border: 0.5px solid #1a9e5c; }
.badge-put     { background: #3d0d0d; color: #ff6b6b; border: 0.5px solid #d94040; }
.badge-avoid   { background: #1a1a2e; color: #a0a0c0; border: 0.5px solid #444; }
.badge-wait    { background: #1a1a1a; color: #888;    border: 0.5px solid #333; }
.badge-caution { background: #2a1a00; color: #f0a030; border: 0.5px solid #c06000; }
.candle-pattern-name {
    font-size: 1rem;
    font-weight: 600;
    color: #e0e0e0;
}
.candle-timeframe {
    font-size: 10px;
    color: #555;
    font-family: 'JetBrains Mono', monospace;
    margin-left: auto;
}
.candle-rule {
    font-size: 0.8rem;
    color: #999;
    line-height: 1.6;
    background: #111;
    border-left: 3px solid #333;
    padding: 8px 12px;
    border-radius: 0 6px 6px 0;
    margin-top: 6px;
}
.candle-rule.rule-call   { border-left-color: #1a9e5c; }
.candle-rule.rule-put    { border-left-color: #d94040; }
.candle-rule.rule-avoid  { border-left-color: #6060c0; }
.candle-rule.rule-wait   { border-left-color: #555; }
.candle-rule.rule-caution{ border-left-color: #c06000; }
.conf-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 4px;
}
.conf-high   { background: #3ddc84; }
.conf-medium { background: #ffd060; }
.conf-low    { background: #888; }

/* ── Metric tiles ── */
.metric-tile {
    background: #0d0d0d;
    border: 0.5px solid #1e1e1e;
    border-radius: 10px;
    padding: 12px 14px;
    text-align: center;
}
.metric-tile .lbl { font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: .07em; font-family: 'JetBrains Mono', monospace; }
.metric-tile .val { font-size: 1.25rem; font-weight: 600; color: #ddd; font-family: 'JetBrains Mono', monospace; margin-top: 2px; }
.metric-tile .sub { font-size: 10px; color: #555; margin-top: 2px; }

/* ── Reason pills ── */
.reason-row {
    display: flex;
    gap: 6px;
    margin: 3px 0;
    align-items: flex-start;
}
.reason-dot {
    width: 6px; height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
    margin-top: 7px;
}
.reason-text { font-size: 0.78rem; color: #bbb; line-height: 1.5; }

/* ── A/D ratio bar ── */
.ad-bar-wrap { display: flex; align-items: center; gap: 8px; }
.ad-label    { font-size: 11px; color: #666; font-family: 'JetBrains Mono', monospace; min-width: 38px; }
.ad-track    { flex: 1; height: 8px; background: #1a1a1a; border-radius: 4px; overflow: hidden; }
.ad-adv      { height: 100%; background: #1a9e5c; border-radius: 4px; }

/* ── Option chain table ── */
.oc-table { width: 100%; border-collapse: collapse; font-size: 12px; font-family: 'JetBrains Mono', monospace; }
.oc-table th { color: #555; font-weight: 500; padding: 6px 8px; border-bottom: 0.5px solid #222; font-size: 10px; text-transform: uppercase; }
.oc-table td { padding: 5px 8px; color: #ccc; border-bottom: 0.5px solid #1a1a1a; }
.oc-table tr.atm td { background: #111e14; color: #3ddc84; font-weight: 600; }
.oc-table .call-oi { color: #3ddc84; }
.oc-table .put-oi  { color: #ff6b6b; }

/* ── Status bar ── */
.status-bar {
    background: #0a0a0a;
    border: 0.5px solid #1a1a1a;
    border-radius: 8px;
    padding: 8px 14px;
    display: flex;
    align-items: center;
    gap: 14px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    color: #555;
    margin-bottom: 14px;
}
.status-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 5px;
}
.dot-green  { background: #3ddc84; box-shadow: 0 0 6px #3ddc84; }
.dot-red    { background: #d94040; }
.dot-yellow { background: #ffd060; }

/* ── Separator ── */
.sep { border-top: 0.5px solid #1a1a1a; margin: 14px 0; }

/* ── Refresh indicator ── */
.refresh-pulse {
    display: inline-block;
    width: 7px; height: 7px;
    border-radius: 50%;
    background: #3ddc84;
    animation: pulse 1.5s infinite;
    margin-right: 5px;
}
@keyframes pulse {
    0%,100% { opacity: 1; }
    50%      { opacity: 0.2; }
}

div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def ist_now():
    return datetime.now(IST)


def is_market_open():
    now = ist_now()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def banner_class(sig):
    if "BUY CALL" in sig and "WEAK" not in sig: return "banner-call"
    if "BUY PUT"  in sig and "WEAK" not in sig: return "banner-put"
    if "WEAK"     in sig: return "banner-weak"
    return "banner-wait"


def score_bar_html(score, max_score=10):
    clamped = max(-max_score, min(max_score, score))
    pct = (clamped / max_score) * 50 + 50  # 0..100
    if clamped >= 0:
        # green bar from centre to right
        left  = 50
        width = pct - 50
        color = "#1a9e5c" if clamped >= 5 else "#c8a600"
    else:
        left  = pct
        width = 50 - pct
        color = "#d94040" if clamped <= -5 else "#c86000"
    return f"""
<div class="score-track">
  <div style="position:absolute;left:50%;top:0;width:1px;height:100%;background:#333;z-index:1"></div>
  <div class="score-fill" style="position:absolute;left:{left}%;width:{width}%;background:{color};"></div>
</div>
<div style="display:flex;justify-content:space-between;font-size:10px;color:#444;font-family:'JetBrains Mono',monospace">
  <span>−10 PUT</span><span>0 WAIT</span><span>CALL +10</span>
</div>"""

def get_zoomed_df(df, timeframe):
    """
    Returns only the recent window based on timeframe selection.
    """
    if df is None or df.empty:
        return df

    try:
        if timeframe == "1m":
            return df.tail(20)   # last ~20 minutes (good visual context)
        elif timeframe == "3m":
            return df.tail(20)   # ~60 mins
        elif timeframe == "5m":
            return df.tail(15)   # last ~75 mins but visually tight
        elif timeframe == "15m":
            return df.tail(10)   # last ~150 mins
    except Exception:
        pass

    return df



def candle_card_html(candle, timeframe="5m"):
    if not candle:
        return ""
    st_map = {
        "CALL": ("badge-call", "rule-call", "🟢"),
        "PUT":  ("badge-put",  "rule-put",  "🔴"),
        "AVOID":("badge-avoid","rule-avoid","🚫"),
        "WAIT": ("badge-wait", "rule-wait", "⚪"),
        "CAUTION":("badge-caution","rule-caution","🟡"),
    }
    st_type = candle.get("signal_type", "WAIT")
    badge_cls, rule_cls, icon = st_map.get(st_type, st_map["WAIT"])
    conf = candle.get("confidence", "LOW")
    conf_dot = {"HIGH": "conf-high", "MEDIUM": "conf-medium"}.get(conf, "conf-low")
    desc = candle.get("description", "").replace("<", "&lt;").replace(">", "&gt;")
    pattern = candle.get("pattern", "")
    return f"""
<div class="candle-card">
  <div class="candle-card-header">
    <span class="candle-badge {badge_cls}">{icon} {st_type}</span>
    <span class="candle-pattern-name">{pattern}</span>
    <span class="candle-timeframe">{timeframe} candle</span>
  </div>
  <div style="font-size:11px;color:#555;margin-bottom:6px;">
    <span class="conf-dot {conf_dot}"></span>Confidence: <strong style="color:#888">{conf}</strong>
  </div>
  <div class="candle-rule {rule_cls}">{desc}</div>
</div>"""


def reason_rows_html(reasons):
    html = ""
    for r in reasons:
        if "(+" in r:  color = "#3ddc84"
        elif "(-" in r: color = "#d94040"
        else:           color = "#555"
        html += f'<div class="reason-row"><div class="reason-dot" style="background:{color}"></div><div class="reason-text">{r}</div></div>'
    return html


def ad_bar_html(advances, declines):
    if advances is None:
        return "<div style='font-size:11px;color:#555'>A/D data loading...</div>"
    total = (advances + declines) or 1
    adv_pct = advances / total * 100
    dec_pct = declines / total * 100
    adv_col = "#1a9e5c" if adv_pct >= 50 else "#555"
    dec_col = "#d94040" if dec_pct >= 50 else "#555"
    return f"""
<div style="margin-bottom:6px;font-size:11px;color:#666">Nifty 50 Advance / Decline</div>
<div class="ad-bar-wrap">
  <span class="ad-label" style="color:{adv_col}">{advances}↑</span>
  <div class="ad-track">
    <div class="ad-adv" style="width:{adv_pct:.0f}%;background:{adv_col}"></div>
  </div>
  <span class="ad-label" style="color:{dec_col};text-align:right">{declines}↓</span>
</div>
<div style="margin-top:4px;font-size:10px;color:#444;font-family:'JetBrains Mono',monospace">
  {"🟢 Breadth bullish" if adv_pct > 60 else ("🔴 Breadth bearish" if adv_pct < 40 else "⚪ Mixed breadth")}
  — {adv_pct:.0f}% advancing
</div>"""


# ──────────────────────────────────────────────────────────────
# CHART BUILDER
# ──────────────────────────────────────────────────────────────

def build_chart(df, timeframe="5m", support=None, resistance=None):
    if df is None or df.empty:
        return go.Figure()

    df = add_indicators(df)
    if support is None:  support  = []
    if resistance is None: resistance = []

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.02,
        subplot_titles=(f"NIFTY 50 — {timeframe}", "Volume", "RSI", "MACD"),
    )

    # Candles
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="NIFTY",
        increasing=dict(fillcolor="#22c55e", line=dict(color="#22c55e", width=1)),
        decreasing=dict(fillcolor="#ef4444", line=dict(color="#ef4444", width=1)),
    ), row=1, col=1)

    # VWAP
    if "vwap" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["vwap"],
            name="VWAP", line=dict(color="#facc15", width=2)), row=1, col=1)

    # EMAs
    for col, color, name in [("ema9","#60aaff","EMA9"), ("ema20","#c084fc","EMA20"), ("ema50","#f472b6","EMA50")]:
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col],
                name=name, line=dict(color=color, width=1)), row=1, col=1)

    # Bollinger Bands
    if "bb_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_upper"],
            name="BB+", line=dict(color="#444", width=0.8, dash="dash"), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["bb_lower"],
            name="BB−", line=dict(color="#444", width=0.8, dash="dash"),
            fill="tonexty", fillcolor="rgba(80,80,80,0.04)", showlegend=False), row=1, col=1)

    # Support / Resistance lines
    price_range = df["high"].max() - df["low"].min()
    for s in support[:2]:
        fig.add_hline(y=s, line_color="#1a9e5c", line_width=0.8, line_dash="dot",
                      annotation_text=f"S {s:.0f}", annotation_font_color="#1a9e5c",
                      annotation_font_size=10, row=1, col=1)
    for r in resistance[:2]:
        fig.add_hline(y=r, line_color="#d94040", line_width=0.8, line_dash="dot",
                      annotation_text=f"R {r:.0f}", annotation_font_color="#d94040",
                      annotation_font_size=10, row=1, col=1)

    # Volume
    vol_colors = ["#0d3d1e" if c >= o else "#3d0d0d"
                  for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["volume"],
        name="Vol", marker_color=vol_colors, opacity=0.8), row=2, col=1)
    if "vol_avg20" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["vol_avg20"],
            name="Vol Avg", line=dict(color="#f0a500", width=1, dash="dot")), row=2, col=1)

    # RSI
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"],
            name="RSI", line=dict(color="#a78bfa", width=1.4)), row=3, col=1)
        for lvl, col in [(70,"#d94040"),(50,"#444"),(30,"#1a9e5c")]:
            fig.add_hline(y=lvl, line_color=col, line_width=0.7, line_dash="dot", row=3, col=1)

    # MACD histogram
    if "macd_hist" in df.columns:
        macd_colors = ["#1a9e5c" if v >= 0 else "#d94040" for v in df["macd_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"],
            name="MACD Hist", marker_color=macd_colors, opacity=0.8), row=4, col=1)
        if "macd" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["macd"],
                name="MACD", line=dict(color="#60aaff", width=1)), row=4, col=1)
        if "macd_sig" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df["macd_sig"],
                name="Signal", line=dict(color="#f472b6", width=1)), row=4, col=1)

    BG = "#0a0a0a"
    fig.update_layout(
        height=620,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="JetBrains Mono, monospace", size=11, color="#666"),
        margin=dict(l=0, r=0, t=26, b=0),
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h", y=1.04, x=0,
            font=dict(size=10),
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x",
        hoverlabel=dict(bgcolor="#111", font_size=11, font_family="JetBrains Mono"),
    )
    for i in range(1, 5):
        fig.update_xaxes(showgrid=True, gridcolor="#111", zeroline=False, row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor="#111", zeroline=False, row=i, col=1)

    return fig


# ──────────────────────────────────────────────────────────────
# OPTION CHAIN TABLE
# ──────────────────────────────────────────────────────────────

def option_chain_html(strike_data, spot, atm, n=5):
    if not strike_data:
        return "<div style='color:#555;font-size:12px'>Option chain unavailable</div>"
    strikes = sorted(strike_data.keys())
    if atm not in strikes:
        return "<div style='color:#555;font-size:12px'>Option chain unavailable</div>"
    idx = strikes.index(atm)
    sel = strikes[max(0, idx - n): idx + n + 1]
    rows = ""
    for s in sel:
        d = strike_data[s]
        atm_cls = "atm" if s == atm else ""
        oi_ratio = d["put_oi"] / (d["call_oi"] + 1)
        bar_w = min(100, int(oi_ratio * 30))
        rows += f"""<tr class="{atm_cls}">
  <td class="call-oi" style="text-align:right">{int(d['call_oi']):,}</td>
  <td class="call-oi" style="text-align:right">₹{d['call_ltp']:.1f}</td>
  <td style="text-align:center;font-weight:600">{'➤ ' if s==atm else ''}{int(s)}</td>
  <td class="put-oi">₹{d['put_ltp']:.1f}</td>
  <td class="put-oi">{int(d['put_oi']):,}</td>
</tr>"""
    return f"""
<table class="oc-table">
  <thead><tr>
    <th style="text-align:right">Call OI</th>
    <th style="text-align:right">Call LTP</th>
    <th style="text-align:center">Strike</th>
    <th>Put LTP</th>
    <th>Put OI</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


# ──────────────────────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────────────────────

def main():
    # ── Session state ──
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = 0
    if "result" not in st.session_state:
        st.session_state.result = None
    if "df1" not in st.session_state:
        st.session_state.df1 = None
    if "df5" not in st.session_state:
        st.session_state.df5 = None
    if "strike_data" not in st.session_state:
        st.session_state.strike_data = {}
    if "atm" not in st.session_state:
        st.session_state.atm = None
    if "spot" not in st.session_state:
        st.session_state.spot = None
    if "advances" not in st.session_state:
        st.session_state.advances = None
    if "declines" not in st.session_state:
        st.session_state.declines = None
    if "chart_tf" not in st.session_state:
        st.session_state.chart_tf = "5m"

    # ── Top status bar ──
    market_open = is_market_open()
    now_ist = ist_now()
    dot_cls = "dot-green" if market_open else "dot-red"
    mkt_txt = "MARKET OPEN" if market_open else "MARKET CLOSED"
    ar_txt  = "AUTO-REFRESH ON" if st.session_state.auto_refresh else "AUTO-REFRESH OFF"
    ar_dot  = "dot-green" if st.session_state.auto_refresh and market_open else "dot-yellow"

    st.markdown(f"""
<div class="status-bar">
  <span><span class="status-dot {dot_cls}"></span>{mkt_txt}</span>
  <span>IST {now_ist.strftime('%H:%M:%S')}</span>
  <span>{now_ist.strftime('%a %d %b %Y')}</span>
  <span><span class="status-dot {ar_dot}"></span>{ar_txt}</span>
  {"<span><span class='refresh-pulse'></span>Refreshing every 30s</span>" if st.session_state.auto_refresh and market_open else ""}
</div>""", unsafe_allow_html=True)

    # ── Header row ──
    hc1, hc2, hc3, hc4 = st.columns([3, 1, 1, 1])
    with hc1:
        st.markdown("<h2 style='margin:0;font-size:1.3rem;color:#ddd'>📊 NIFTY Options Signal</h2>", unsafe_allow_html=True)
    with hc2:
        if st.button("⟳ Force Refresh", use_container_width=True):
            st.session_state.last_refresh = 0
            st.rerun()
    with hc3:
        ar_label = "🟢 Auto ON" if st.session_state.auto_refresh else "🔴 Auto OFF"
        if st.button(ar_label, use_container_width=True):
            st.session_state.auto_refresh = not st.session_state.auto_refresh
            st.rerun()
    with hc4:
        tf_choice = st.selectbox("Chart", ["1m", "3m", "5m", "15m"],
                                  index=["1m","3m","5m","15m"].index(st.session_state.chart_tf),
                                  label_visibility="collapsed")
        if tf_choice != st.session_state.chart_tf:
            st.session_state.chart_tf = tf_choice

    # ── Candle tab selector (prominent) ──
    st.markdown('<div style="margin:10px 0 6px;font-size:11px;color:#555;font-family:\'JetBrains Mono\',monospace">CANDLE ZOOM</div>', unsafe_allow_html=True)
    tab_cols = st.columns(4)
    tf_tabs = ["1m", "3m", "5m", "15m"]
    for i, tf in enumerate(tf_tabs):
        with tab_cols[i]:
            active_style = "background:#1a9e5c;color:#fff;border-color:#1a9e5c;" if tf == st.session_state.chart_tf else ""
            if st.button(f"{'⬤ ' if tf == st.session_state.chart_tf else ''}{tf} candle",
                         key=f"tf_{tf}", use_container_width=True):
                st.session_state.chart_tf = tf
                st.rerun()

    st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

    # ── DECIDE: should we fetch new data? ──
    now_ts = time.time()
    should_fetch = (
        st.session_state.result is None or
        (st.session_state.auto_refresh and market_open and
         (now_ts - st.session_state.last_refresh) >= 30)
    )

    if should_fetch:
        with st.spinner("Fetching live data..."):
            try:
                df1, df5 = fetch_nifty_both_timeframes()
                vix = fetch_vix()
                pcr, atm, c_oi, p_oi, spot, strike_data = fetch_option_chain()
                advances, declines, unchanged = fetch_advance_decline()

                # Use the selected timeframe for primary chart
                active_tf = st.session_state.chart_tf
                if active_tf in ["1m", "2m"]:
                    df_active = df1
                else:
                    df_active = fetch_nifty_data(interval=active_tf, period="1d")

                result = generate_signal(df5, df1=df1, pcr=pcr, vix=vix,
                                          advances=advances, declines=declines)

                st.session_state.df1 = df1
                st.session_state.df5 = df5
                st.session_state.df_active = df_active
                st.session_state.strike_data = strike_data
                st.session_state.atm = atm
                st.session_state.spot = spot
                st.session_state.result = result
                st.session_state.advances = advances
                st.session_state.declines = declines
                st.session_state.last_refresh = now_ts
            except Exception as e:
                st.error(f"Data error: {e}")
                if st.session_state.result is None:
                    st.stop()
    else:
        # Re-fetch chart data if timeframe changed
        if "last_chart_tf" not in st.session_state or st.session_state.last_chart_tf != st.session_state.chart_tf:
            try:
                active_tf = st.session_state.chart_tf
                if active_tf in ["1m"]:
                    st.session_state.df_active = st.session_state.df1
                else:
                    st.session_state.df_active = fetch_nifty_data(interval=active_tf, period="1d")
            except Exception:
                pass
        st.session_state.last_chart_tf = st.session_state.chart_tf

    result = st.session_state.result
    if result is None:
        st.warning("No data yet. Click Force Refresh.")
        st.stop()

    # ──────────────────────────────────────────────
    # MAIN LAYOUT: left col (signal) + right col (chart)
    # ──────────────────────────────────────────────
    left, right = st.columns([1, 2], gap="medium")

    # ══ LEFT PANEL ══════════════════════════════
    with left:

        # Signal banner
        bc = banner_class(result.get("signal", ""))
        sig_text = result.get("signal", "⚪ WAIT")
        score = result.get("score", 0)
        conf  = result.get("confidence", "—")
        ts    = result.get("timestamp", "")
        st.markdown(f"""
<div class="signal-banner {bc}">
  <div class="banner-title">{sig_text}</div>
  <div class="banner-sub">Score: {score:+.1f}  ·  Confidence: {conf}  ·  {ts}</div>
</div>""", unsafe_allow_html=True)

        # Score bar
        st.markdown(score_bar_html(score), unsafe_allow_html=True)

        # Trade guidance
        if result.get("stop_loss"):
            rr = result.get("rr_ratio", "—")
            st.markdown(f"""
<div style="background:#0d0d0d;border:0.5px solid #1a1a1a;border-radius:10px;padding:12px 14px;margin:10px 0">
  <div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;font-family:'JetBrains Mono',monospace">Trade guidance</div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-family:'JetBrains Mono',monospace">
    <div><div style="font-size:10px;color:#555">Strike</div><div style="font-size:12px;color:#c084fc">{result.get('strike','—')}</div></div>
    <div><div style="font-size:10px;color:#555">R:R ratio</div><div style="font-size:14px;color:#ddd">{rr}:1</div></div>
    <div><div style="font-size:10px;color:#1a9e5c">Target</div><div style="font-size:15px;color:#3ddc84">₹{result.get('target','—'):,}</div></div>
    <div><div style="font-size:10px;color:#d94040">Stop Loss</div><div style="font-size:15px;color:#ff6b6b">₹{result.get('stop_loss','—'):,}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # ── CANDLE SIGNAL CARD (Deep) ──
        st.markdown('<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-family:\'JetBrains Mono\',monospace">📊 Candle analysis</div>', unsafe_allow_html=True)

        c5 = result.get("candle5m")
        c1 = result.get("candle1m")
        st.markdown(candle_card_html(c5, "5m"), unsafe_allow_html=True)
        if c1:
            st.markdown(candle_card_html(c1, "1m"), unsafe_allow_html=True)

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # ── Advance / Decline ──
        st.markdown(ad_bar_html(result.get("advances"), result.get("declines")), unsafe_allow_html=True)

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # ── Live metrics ──
        st.markdown('<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;font-family:\'JetBrains Mono\',monospace">Live indicators</div>', unsafe_allow_html=True)

        mc = st.columns(3)
        def tile(label, val, sub=""):
            return f'<div class="metric-tile"><div class="lbl">{label}</div><div class="val">{val}</div><div class="sub">{sub}</div></div>'

        price = result.get("price", "—")
        rsi   = result.get("rsi", "—")
        vwap  = result.get("vwap", "—")
        atr   = result.get("atr", "—")
        vr    = result.get("vol_ratio", "—")
        pcr_v = result.get("pcr", "—")
        vix_v = result.get("vix", "—")
        macd_h= result.get("macd_hist", "—")
        e9    = result.get("ema9", "—")
        e20   = result.get("ema20", "—")

        rsi_color = "#3ddc84" if isinstance(rsi, float) and rsi < 40 else ("#d94040" if isinstance(rsi, float) and rsi > 65 else "#ddd")
        vr_color  = "#3ddc84" if isinstance(vr, float) and vr > 1.5 else "#ddd"

        tiles_data = [
            ("NIFTY", f"₹{price:,}" if isinstance(price, float) else price, ""),
            ("RSI", rsi, "oversold<40  overbought>70"),
            ("VWAP", f"₹{vwap:,}" if isinstance(vwap, float) else vwap, "intraday avg"),
            ("ATR", atr, "expected range"),
            ("VOL ×", f"{vr}×" if vr != "—" else "—", "vs 20-bar avg"),
            ("PCR", pcr_v, "<0.7 bull  >1.3 bear"),
            ("VIX", vix_v, "fear gauge"),
            ("MACD H", macd_h, "positive=bull"),
            ("EMA 9/20", f"{e9}/{e20}", ""),
        ]
        for i in range(0, len(tiles_data), 3):
            row = st.columns(3)
            for j, (lbl, val, sub) in enumerate(tiles_data[i:i+3]):
                with row[j]:
                    st.markdown(tile(lbl, val, sub), unsafe_allow_html=True)
            st.markdown("")

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # ── S/R levels ──
        sup = result.get("support", [])
        res = result.get("resistance", [])
        st.markdown('<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-family:\'JetBrains Mono\',monospace">Key levels</div>', unsafe_allow_html=True)
        if sup:
            st.markdown(f'<div style="font-size:12px;color:#3ddc84;margin-bottom:4px">🟢 Support: {" · ".join(f"₹{int(s):,}" for s in sup)}</div>', unsafe_allow_html=True)
        if res:
            st.markdown(f'<div style="font-size:12px;color:#ff6b6b">🔴 Resistance: {" · ".join(f"₹{int(r):,}" for r in res)}</div>', unsafe_allow_html=True)

        # Warnings
        for warn_key in ["vix_warning", "atr_warning"]:
            w = result.get(warn_key)
            if w:
                st.warning(w)

    # ══ RIGHT PANEL ══════════════════════════════
    with right:

        # Chart with current TF
        df_chart_full = getattr(st.session_state, "df_active", st.session_state.df5)
        df_chart = get_zoomed_df(df_chart_full, st.session_state.chart_tf)    
        sup  = result.get("support", [])
        res  = result.get("resistance", [])
        fig = build_chart(df_chart, timeframe=st.session_state.chart_tf,
                          support=sup, resistance=res)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # Signal reasons
        reasons = result.get("reasons", [])
        if reasons:
            st.markdown('<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;font-family:\'JetBrains Mono\',monospace">Signal breakdown</div>', unsafe_allow_html=True)
            rc1, rc2 = st.columns(2)
            half = len(reasons) // 2 + len(reasons) % 2
            with rc1:
                st.markdown(reason_rows_html(reasons[:half]), unsafe_allow_html=True)
            with rc2:
                st.markdown(reason_rows_html(reasons[half:]), unsafe_allow_html=True)

        st.markdown('<div class="sep"></div>', unsafe_allow_html=True)

        # Option chain
        st.markdown('<div style="font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;font-family:\'JetBrains Mono\',monospace">Option chain — ATM ± 5 strikes</div>', unsafe_allow_html=True)
        pcr_v = result.get("pcr")
        spot  = st.session_state.spot
        atm   = st.session_state.atm
        if pcr_v and spot:
            pcr_color = "#3ddc84" if pcr_v < 1.0 else "#ff6b6b"
            st.markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#555;margin-bottom:6px">PCR <span style="color:{pcr_color};font-weight:600">{pcr_v}</span>  ·  ATM Strike <strong style="color:#ddd">{int(atm) if atm else "—"}</strong>  ·  Spot ₹{spot:,.2f}</div>', unsafe_allow_html=True)
        st.markdown(option_chain_html(st.session_state.strike_data, spot, atm), unsafe_allow_html=True)

    # ──────────────────────────────────────────────
    # AUTO-REFRESH LOGIC
    # ──────────────────────────────────────────────
    if st.session_state.auto_refresh and market_open:
        elapsed = time.time() - st.session_state.last_refresh
        remaining = max(0, 30 - elapsed)
        st.markdown(
            f'<div style="text-align:right;font-size:10px;color:#333;font-family:\'JetBrains Mono\',monospace;margin-top:10px">'
            f'Next refresh in ~{int(remaining)}s</div>',
            unsafe_allow_html=True
        )
        time.sleep(max(1, remaining))
        st.rerun()
    elif st.session_state.auto_refresh and not market_open:
        st.markdown(
            '<div style="text-align:center;font-size:11px;color:#444;font-family:\'JetBrains Mono\',monospace;margin-top:16px">'
            '⏸ Auto-refresh paused — market closed (9:00 AM – 3:40 PM IST)</div>',
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
