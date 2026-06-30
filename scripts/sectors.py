# ============================================================
# scripts/sectors.py — Sector Performance + RRG data generator
# 11 SPDR sectors + SPY benchmark | Yahoo Finance
# Writes: sectors.json (perf table) + sectors_prices.csv (price history)
# (Run in Colab first to validate, then commit to GitHub)
# ============================================================
!pip install yfinance --quiet   # <-- remove this line in the GitHub version

import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta, timezone

# ----- Tickers -----
SECTORS = {
    'XLY':  'Consumer Discretionary',
    'XLF':  'Financial Select Sector',
    'XLV':  'Health Care Select Sector',
    'XLK':  'Technology Select Sector',
    'XLP':  'Consumer Staples Select Sector',
    'XLI':  'Industrial Select Sector',
    'XLB':  'Materials Select Sector',
    'XLE':  'The Energy Select Sector',
    'XLU':  'Utilities Select Sector',
    'XLRE': 'Real Estate Select Sector',
    'XLC':  'Communications Services Sector',
}
BENCHMARK = 'SPY'
ALL_TICKERS = list(SECTORS.keys()) + [BENCHMARK]

# ----- Fetch ~2 years of daily prices -----
start = (datetime.now().date() - timedelta(days=760)).strftime('%Y-%m-%d')
tomorrow = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')

raw = yf.download(ALL_TICKERS, start=start, end=tomorrow,
                  progress=False, auto_adjust=True)['Close']
raw = raw.dropna(how='all').ffill()
print(f"Price data: {raw.index.min().date()} → {raw.index.max().date()}, {len(raw)} rows")

# ============================================================
# PERFORMANCE TABLE
# ============================================================
def period_start_price(s, kind):
    last_dt = s.index[-1]
    if kind == '1D':
        return s.iloc[-2]
    elif kind == 'MTD':
        boundary = last_dt.replace(day=1)
    elif kind == 'QTD':
        q_month = ((last_dt.month - 1) // 3) * 3 + 1
        boundary = last_dt.replace(month=q_month, day=1)
    elif kind == 'YTD':
        boundary = last_dt.replace(month=1, day=1)
    prior = s[s.index < boundary]
    return prior.iloc[-1] if len(prior) else s.iloc[0]

def perf(s, kind):
    return (s.iloc[-1] / period_start_price(s, kind) - 1) * 100

perf_rows = []
for tk in list(SECTORS.keys()) + ['SPY']:
    s = raw[tk].dropna()
    perf_rows.append({
        'sector': SECTORS.get(tk, 'S&P 500 (SPY)'),
        'ticker': tk,
        'price':  float(s.iloc[-1]),
        'd1':  float(perf(s, '1D')),
        'mtd': float(perf(s, 'MTD')),
        'qtd': float(perf(s, 'QTD')),
        'ytd': float(perf(s, 'YTD')),
    })

# ============================================================
# RRG (compute a FIXED WEEKLY read for the summary callouts)
# ============================================================
def compute_rrg(prices, benchmark, tickers, freq='W',
                rs_win=12, mom_win=10, smooth=4):
    if freq != 'D':
        px = prices.resample(freq).last().dropna(how='all')
    else:
        px = prices.copy()
    bench = px[benchmark]
    out = {}
    for tk in tickers:
        rs = (px[tk] / bench) * 100
        rs_mean = rs.rolling(rs_win).mean()
        rs_std  = rs.rolling(rs_win).std()
        rs_ratio = 100 + ((rs - rs_mean) / rs_std)
        rs_ratio = rs_ratio.rolling(smooth).mean()
        roc = (rs_ratio / rs_ratio.shift(mom_win) - 1) * 100
        roc = roc.rolling(smooth).mean()
        mom_mean = roc.rolling(rs_win).mean()
        mom_std  = roc.rolling(rs_win).std()
        rs_mom = 100 + ((roc - mom_mean) / mom_std)
        rs_mom = rs_mom.rolling(smooth).mean()
        out[tk] = pd.DataFrame({'rs_ratio': rs_ratio,
                                'rs_momentum': rs_mom}).dropna()
    return out

def quadrant(r, m):
    if   r >= 100 and m >= 100: return 'Leading'
    elif r >= 100 and m <  100: return 'Weakening'
    elif r <  100 and m <  100: return 'Lagging'
    else:                       return 'Improving'

# Fixed weekly for callouts
rrg_w = compute_rrg(raw, BENCHMARK, list(SECTORS.keys()), freq='W')

# ============================================================
# BUILD SUMMARY CALLOUTS (fixed weekly)
# ============================================================
QUAD_ACTION = {
    'Leading':   ('🟢', 'strong & gaining momentum', 'showing leadership — overweight candidate'),
    'Weakening': ('🟡', 'strong but momentum fading', 'losing steam — consider trimming'),
    'Lagging':   ('🔴', 'weak & losing momentum',     'underperforming — underweight/avoid'),
    'Improving': ('🔵', 'weak but gaining momentum',  'early turnaround — accumulate/watch'),
}

quad_now, quad_prev, mom_change = {}, {}, {}
for tk, df in rrg_w.items():
    if len(df) < 3:
        continue
    last = df.iloc[-1]
    prev = df.iloc[-3]   # 2 periods ago
    quad_now[tk]  = quadrant(last['rs_ratio'], last['rs_momentum'])
    quad_prev[tk] = quadrant(prev['rs_ratio'], prev['rs_momentum'])
    mom_change[tk] = last['rs_momentum'] - prev['rs_momentum']

# 1. Rotation alerts (crossed quadrant in last 2 periods)
rotations = []
for tk in quad_now:
    if quad_now[tk] != quad_prev[tk]:
        ic, _, action = QUAD_ACTION[quad_now[tk]]
        rotations.append({
            'ticker': tk,
            'from': quad_prev[tk], 'to': quad_now[tk],
            'text': f"{ic} **{tk}** rotated {quad_prev[tk]} → **{quad_now[tk]}** — {action}"
        })

# 2. Leaders & laggards
leaders  = [tk for tk, q in quad_now.items() if q == 'Leading']
laggards = [tk for tk, q in quad_now.items() if q == 'Lagging']

# 3. Momentum shifts (biggest accel / decel)
mom_sorted = sorted(mom_change.items(), key=lambda x: x[1])
decel = mom_sorted[:3]   # most negative
accel = mom_sorted[-3:][::-1]  # most positive

# 4. Performance snapshot
sec_only = [r for r in perf_rows if r['ticker'] != 'SPY']
best_ytd  = max(sec_only, key=lambda r: r['ytd'])
worst_ytd = min(sec_only, key=lambda r: r['ytd'])
best_1d   = max(sec_only, key=lambda r: r['d1'])

# 5. Quadrant summary
quad_counts = {q: sum(1 for v in quad_now.values() if v == q)
               for q in ['Leading','Weakening','Lagging','Improving']}

callouts = dict(
    rotations=rotations,
    leaders=leaders,
    laggards=laggards,
    accel=[{'ticker': tk, 'delta': round(d, 2)} for tk, d in accel],
    decel=[{'ticker': tk, 'delta': round(d, 2)} for tk, d in decel],
    perf_snapshot=dict(
        best_ytd=dict(ticker=best_ytd['ticker'], val=round(best_ytd['ytd'], 2)),
        worst_ytd=dict(ticker=worst_ytd['ticker'], val=round(worst_ytd['ytd'], 2)),
        best_1d=dict(ticker=best_1d['ticker'], val=round(best_1d['d1'], 2)),
    ),
    quad_counts=quad_counts,
    quad_now=quad_now,
)

# ============================================================
# WRITE OUTPUTS
# ============================================================
payload = dict(
    as_of=raw.index[-1].strftime('%Y-%m-%d'),
    generated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    benchmark=BENCHMARK,
    performance=perf_rows,
    callouts=callouts,
)
with open('sectors.json', 'w') as f:
    json.dump(payload, f, indent=2)

# Price history for in-app RRG (so slider/timeframe is interactive)
prices_out = raw[ALL_TICKERS].copy()
prices_out.index.name = 'date'
prices_out.to_csv('sectors_prices.csv')

print(f"\n✅ Wrote sectors.json + sectors_prices.csv (as_of {payload['as_of']})")

# ============================================================
# VALIDATION PRINTOUT
# ============================================================
print("\n=== QUADRANT SUMMARY (weekly) ===")
for q, n in quad_counts.items():
    members = [tk for tk, v in quad_now.items() if v == q]
    print(f"  {q:10s}: {n}  {members}")

print(f"\n=== ROTATION ALERTS ({len(rotations)}) ===")
for r in rotations:
    print(f"  {r['ticker']}: {r['from']} → {r['to']}")
if not rotations:
    print("  (none this week)")

print(f"\n=== MOMENTUM ===")
print(f"  Accelerating: {[(tk, round(d,2)) for tk,d in accel]}")
print(f"  Decelerating: {[(tk, round(d,2)) for tk,d in decel]}")

print(f"\n=== PERF SNAPSHOT ===")
print(f"  Best YTD:  {best_ytd['ticker']} {best_ytd['ytd']:+.1f}%")
print(f"  Worst YTD: {worst_ytd['ticker']} {worst_ytd['ytd']:+.1f}%")
print(f"  Best 1D:   {best_1d['ticker']} {best_1d['d1']:+.1f}%")
