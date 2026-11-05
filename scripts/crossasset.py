# ============================================================
# scripts/crossasset.py — Cross-Asset Volatility + USD Correlations
# Free from Yahoo Finance
# Writes: crossasset.json (metrics/correlations/callouts) + crossasset_series.csv (vol history)
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone

# ----- Tickers -----
VOL_TICKERS = {
    '^VIX': 'VIX (S&P 500)',
    '^VXN': 'VXN (Nasdaq)',
    '^GVZ': 'GVZ (Gold)',
    '^OVX': 'OVX (Oil)',
}

# Same tickers as the validated correlation script.
# Each entry: key -> list of tickers (first = primary, rest = fallbacks)
CORR_TICKERS = {
    'DXY':  ['^NYICDX'],
    'SPX':  ['^GSPC'],
    'OIL':  ['BZ=F', 'CL=F'],
    'GOLD': ['GC=F', 'GLD'],
    'BTC':  ['BTC-USD'],
}

# Correlation method. The validated script correlates PRICE LEVELS.
# Set to 'returns' for daily % change correlations instead.
CORR_MODE = 'levels'

start = (datetime.now().date() - timedelta(days=760)).strftime('%Y-%m-%d')
tomorrow = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')


# ============================================================
# FETCH
# ============================================================
def download_close(ticker):
    """Download one ticker's Close series (handles MultiIndex columns)."""
    try:
        data = yf.download(ticker, start=start, end=tomorrow,
                           progress=False, auto_adjust=True)
        if data is None or data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'].iloc[:, 0] if 'Close' in data.columns.get_level_values(0) else data.iloc[:, 0]
        else:
            close = data['Close'] if 'Close' in data.columns else data.iloc[:, 0]
        return close.dropna()
    except Exception as e:
        print(f"  download error for {ticker}: {e}")
        return None


vol_raw = yf.download(list(VOL_TICKERS.keys()), start=start, end=tomorrow,
                      progress=False, auto_adjust=True)['Close']
vol_raw = vol_raw.dropna(how='all').ffill()

# Download each correlation asset separately, with fallbacks
corr_series = {}
for key, candidates in CORR_TICKERS.items():
    for tk in candidates:
        s = download_close(tk)
        if s is not None and len(s):
            corr_series[key] = s
            print(f"✓ {key}: {len(s)} rows (ticker: {tk})")
            break
    else:
        print(f"❌ {key}: failed to download")

# KEY FIX: inner-join on common dates (dropna), NOT ffill.
# Forward-filling mixed calendars (BTC trades 7 days/week, others don't)
# injects fake flat prices / zero returns and distorts correlations.
corr_raw = pd.DataFrame(corr_series).dropna()

print(f"Vol rows: {len(vol_raw)} | cols: {list(vol_raw.columns)}")
print(f"Corr rows: {len(corr_raw)} | cols: {list(corr_raw.columns)}")


# ============================================================
# PART 1: VOL METRICS
# ============================================================
def metrics(s):
    s = s.dropna()
    if len(s) < 2:
        return None
    last_dt = s.index[-1]
    last, d1 = float(s.iloc[-1]), float(s.iloc[-2])
    w1 = float(s.asof(last_dt - pd.Timedelta(days=7)))
    m1 = float(s.asof(last_dt - pd.Timedelta(days=30)))
    def d(c, p): return [c - p, (c/p - 1)*100 if p else None]
    return dict(last=last, d1=d1, w1=w1, m1=m1,
                dod=d(last, d1), wow=d(last, w1), mom=d(last, m1))

vol_metrics = {}
for tk, name in VOL_TICKERS.items():
    if tk in vol_raw.columns:
        m = metrics(vol_raw[tk])
        if m:
            m['name'] = name
            vol_metrics[tk] = m


# ============================================================
# PART 2: USD CORRELATIONS
# ============================================================
WINDOWS = [15, 30, 90, 120, 180]
CORR_ASSETS = ['SPX', 'OIL', 'GOLD', 'BTC']
LOOKBACK_52W = 260  # trading rows, matches validated script

data = corr_raw if CORR_MODE == 'levels' else corr_raw.pct_change().dropna()

corr_table = {}
for a in CORR_ASSETS:
    if a not in data.columns or 'DXY' not in data.columns:
        continue
    row = {}

    # Windowed correlation over the last N rows
    for w in WINDOWS:
        if len(data) >= w:
            c = data['DXY'].tail(w).corr(data[a].tail(w))
            row[f'{w}d'] = round(float(c), 2) if pd.notna(c) else None
        else:
            row[f'{w}d'] = None

    # 52-week stats: rolling 30-day corr computed ONLY inside the last 260 rows
    lookback = data.tail(LOOKBACK_52W)
    roll30 = lookback['DXY'].rolling(30).corr(lookback[a]).dropna()
    if len(roll30):
        row['hi_52w'] = round(float(roll30.max()), 2)
        row['lo_52w'] = round(float(roll30.min()), 2)
        row['pct_neg'] = int(round(float((roll30 < 0).mean() * 100)))
        row['pct_pos'] = int(round(float((roll30 > 0).mean() * 100)))
        # sign-flip detection: did 30D corr cross zero recently?
        recent = roll30.tail(10)
        row['flipped'] = bool((recent.iloc[0] > 0) != (recent.iloc[-1] > 0))
    corr_table[a] = row


# ============================================================
# PART 3: CALLOUTS
# ============================================================
# --- Vol callouts ---
vol_callouts = []
rising = [v['name'] for v in vol_metrics.values() if v['wow'][1] and v['wow'][1] > 0]
n = len(vol_metrics)
nr = len(rising)
if nr >= max(1, int(n * 0.75)):
    vol_callouts.append(f"⚠️ Cross-asset vol BROADLY RISING ({nr}/{n} up WoW) — risk-off building across assets.")
elif nr <= 1:
    vol_callouts.append(f"🟢 Cross-asset vol BROADLY CALM ({nr}/{n} up WoW) — risk-on / complacent backdrop.")
else:
    vol_callouts.append(f"Mixed vol picture ({nr}/{n} rising WoW).")

# Biggest MoM mover (divergence highlight)
mom_sorted = sorted(vol_metrics.values(),
                    key=lambda v: abs(v['mom'][1]) if v['mom'][1] else 0, reverse=True)
if len(mom_sorted) >= 2:
    top, bot = mom_sorted[0], mom_sorted[-1]
    if top['mom'][1] and bot['mom'][1] and (top['mom'][1] * bot['mom'][1] < 0):
        vol_callouts.append(
            f"Divergence: {top['name']} {top['mom'][1]:+.0f}% MoM vs "
            f"{bot['name']} {bot['mom'][1]:+.0f}% MoM — stress concentrated, not broad.")

# --- Correlation callouts ---
corr_callouts = []
for a, row in corr_table.items():
    c30 = row.get('30d')
    if c30 is None:
        continue
    if row.get('flipped'):
        newsign = 'POSITIVE' if c30 > 0 else 'NEGATIVE'
        corr_callouts.append(
            f"🔄 **{a}-USD correlation flipped {newsign}** (30D {c30:+.2f}) — possible regime shift.")
    elif abs(c30) > 0.7:
        kind = 'inverse' if c30 < 0 else 'positive'
        corr_callouts.append(
            f"**{a}-USD strongly {kind}** (30D {c30:+.2f}, {row.get('pct_neg')}% time negative) — relationship intact.")

# Always note gold (the key tell)
g = corr_table.get('GOLD')
if g and g.get('30d') is not None and g.get('lo_52w') is not None:
    corr_callouts.append(
        f"Gold-USD: 30D {g['30d']:+.2f} (52wk range {g['lo_52w']:+.2f} to {g['hi_52w']:+.2f}, "
        f"{g['pct_neg']}% negative) — the classic dollar barometer.")


# ============================================================
# WRITE OUTPUTS
# ============================================================
payload = dict(
    as_of=vol_raw.index[-1].strftime('%Y-%m-%d'),
    corr_as_of=corr_raw.index[-1].strftime('%Y-%m-%d'),
    corr_mode=CORR_MODE,
    generated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    vol_metrics=vol_metrics,
    correlations=corr_table,
    corr_windows=WINDOWS,
    callouts=dict(vol=vol_callouts, corr=corr_callouts,
                  vol_breadth=dict(rising=nr, total=n)),
)
with open('crossasset.json', 'w') as f:
    json.dump(payload, f, indent=2)

# Vol time series for charting
vol_series = vol_raw[[c for c in VOL_TICKERS if c in vol_raw.columns]].copy()
vol_series.columns = [VOL_TICKERS[c].split(' ')[0] for c in vol_series.columns]  # VIX/VXN/GVZ/OVX
vol_series.index.name = 'date'
vol_series.to_csv('crossasset_series.csv')

print(f"\n✅ Wrote crossasset.json + crossasset_series.csv (as_of {payload['as_of']})")


# ============================================================
# VALIDATION PRINTOUT
# ============================================================
print("\n=== CORRELATION TABLE ===")
print(pd.DataFrame(corr_table).T.to_string())
print("\n=== VOL CALLOUTS ===")
for c in vol_callouts:
    print(f"  • {c}")
print("\n=== CORRELATION CALLOUTS ===")
for c in corr_callouts:
    print(f"  • {c}")
