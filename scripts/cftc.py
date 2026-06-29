# scripts/cftc.py
# CFTC Commitments of Traders — Legacy / Futures-Only / Non-Commercial Net positioning
# Source: CFTC Socrata Public Reporting API (free, no key)
# Writes: cftc.json (full analytics) + cftc.csv (latest snapshot)
import json
import pandas as pd
import numpy as np
import requests
from io import StringIO
from datetime import datetime

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.csv"

# ----- Instrument universe: section -> [(label, code), ...] -----
UNIVERSE = {
    'EQUITIES': [
        ('SPX (E-mini)',      '13874A'),
        ('VIX',               '1170E1'),
        ('Russell 2000 mini', '239742'),
        ('Dow Jones mini',    '12460+'),
        ('Nasdaq mini',       '209742'),
    ],
    'RATES': [
        ('10Y UST',     '043602'),
        ('2Y UST',      '042601'),
        ('5Y UST',      '044601'),
        ('UST Bonds',   '020601'),
        ('30D Fed Funds','045601'),
    ],
    'CURRENCIES': [
        ('USD (DXY)', '098662'),
        ('JPY',       '097741'),
        ('EUR',       '099741'),
        ('GBP',       '096742'),
        ('AUD',       '232741'),
        ('CAD',       '090741'),
        ('MXN',       '095741'),
        ('NZD',       '112741'),
        ('CHF',       '092741'),
    ],
    'COMMODITIES': [
        ('Crude Oil',       '067651'),
        ('Gold',            '088691'),
        ('Copper',          '085692'),
        ('Natural Gas',     '023651'),
        ('RBOB Gasoline',   '111659'),
        ('ULSD Heating Oil','022651'),
        ('Silver',          '084691'),
        ('Platinum',        '076651'),
        ('Corn',            '002602'),
        ('Soybeans',        '005602'),
        ('Wheat',           '001602'),
        ('Live Cattle',     '057642'),
        ('Lean Hogs',       '054642'),
        ('Sugar',           '080732'),
        ('Cotton',          '033661'),
        ('Coffee',          '083731'),
        ('Cocoa',           '073732'),
        ('Orange Juice',    '040701'),
    ],
}

LONG_COL  = 'noncomm_positions_long_all'
SHORT_COL = 'noncomm_positions_short_all'
# Add to scripts/cftc.py — interpretation map + callout builder

INTERP = {
    # label: (asset_class, net_long_means, long_read, short_read)
    'SPX (E-mini)':      ('equity', 'bullish equities', 'extended long — squeeze/reversal risk', 'bearish bet — contrarian bounce risk'),
    'Dow Jones mini':    ('equity', 'bullish equities', 'extended long — reversal risk', 'bearish bet — bounce risk'),
    'Nasdaq mini':       ('equity', 'bullish tech', 'extended long — reversal risk', 'bearish tech bet — bounce risk'),
    'Russell 2000 mini': ('equity', 'bullish small caps', 'extended long — reversal risk', 'bearish small caps — bounce risk'),
    'VIX':               ('vol', 'expecting vol up', 'fear positioning building', 'complacency — hedges cheap, watch for vol spike'),
    '10Y UST':           ('rates', 'bullish bonds (lower yields)', 'crowded bet on falling rates', 'crowded bet on rising rates'),
    '2Y UST':            ('rates', 'bullish front-end', 'crowded bet on cuts', 'crowded bet on higher short rates'),
    '5Y UST':            ('rates', 'bullish belly', 'crowded bet on falling rates', 'crowded bet on rising rates'),
    'UST Bonds':         ('rates', 'bullish long bonds', 'crowded duration long', 'crowded bet on rising long yields'),
    '30D Fed Funds':     ('rates', 'expecting cuts', 'dovish positioning crowded', 'hawkish positioning crowded'),
    'USD (DXY)':         ('fx', 'bullish USD', 'crowded long USD', 'crowded short USD'),
    'JPY':               ('fx', 'bullish JPY (USD-bearish)', 'crowded long yen', 'crowded short yen (USD-bullish)'),
    'EUR':               ('fx', 'bullish EUR (USD-bearish)', 'crowded long euro', 'crowded short euro (USD-bullish)'),
    'GBP':               ('fx', 'bullish GBP', 'crowded long pound', 'crowded short pound'),
    'AUD':               ('fx', 'bullish AUD (risk-on proxy)', 'crowded long Aussie', 'crowded short Aussie (risk-off lean)'),
    'CAD':               ('fx', 'bullish CAD', 'crowded long loonie', 'crowded short loonie'),
    'MXN':               ('fx', 'bullish peso (carry trade)', 'crowded carry long', 'crowded short peso'),
    'NZD':               ('fx', 'bullish kiwi', 'crowded long kiwi', 'crowded short kiwi'),
    'CHF':               ('fx', 'bullish franc', 'crowded long franc', 'crowded short franc (risk-on lean)'),
    'Crude Oil':         ('commodity', 'bullish oil', 'crowded long crude — reversal risk', 'crowded short crude — squeeze risk'),
    'Gold':              ('commodity', 'bullish gold', 'crowded long gold', 'crowded short gold'),
    'Copper':            ('commodity', 'bullish copper (growth proxy)', 'crowded long copper — reflation bet', 'crowded short copper — growth pessimism'),
    'Natural Gas':       ('commodity', 'bullish nat gas', 'crowded long — reversal risk', 'crowded short — squeeze risk'),
    'RBOB Gasoline':     ('commodity', 'bullish gasoline', 'crowded long gasoline', 'crowded short gasoline'),
    'ULSD Heating Oil':  ('commodity', 'bullish distillates', 'crowded long heating oil', 'crowded short heating oil'),
    'Silver':            ('commodity', 'bullish silver', 'crowded long silver', 'crowded short silver'),
    'Platinum':          ('commodity', 'bullish platinum', 'crowded long platinum', 'crowded short platinum'),
    'Corn':              ('commodity', 'bullish corn', 'crowded long corn', 'crowded short corn'),
    'Soybeans':          ('commodity', 'bullish beans', 'crowded long soybeans', 'crowded short soybeans'),
    'Wheat':             ('commodity', 'bullish wheat', 'crowded long wheat', 'crowded short wheat'),
    'Live Cattle':       ('commodity', 'bullish cattle', 'crowded long cattle', 'crowded short cattle'),
    'Lean Hogs':         ('commodity', 'bullish hogs', 'crowded long hogs', 'crowded short hogs'),
    'Sugar':             ('commodity', 'bullish sugar', 'crowded long sugar', 'crowded short sugar'),
    'Cotton':            ('commodity', 'bullish cotton', 'crowded long cotton', 'crowded short cotton'),
    'Coffee':            ('commodity', 'bullish coffee', 'crowded long coffee', 'crowded short coffee'),
    'Cocoa':             ('commodity', 'bullish cocoa', 'crowded long cocoa', 'crowded short cocoa'),
    'Orange Juice':      ('commodity', 'bullish OJ', 'crowded long OJ', 'crowded short OJ'),
}


def build_callouts(results, z_threshold=2.0):
    extremes, shifts, flips, sector = [], [], [], {}

    # 1. EXTREMES (|Z-1Y| >= threshold)
    for r in results:
        z = r['z_1y']
        if z is None:
            continue
        if abs(z) >= z_threshold:
            info = INTERP.get(r['label'])
            read = (info[2] if z > 0 else info[3]) if info else \
                   ('crowded long' if z > 0 else 'crowded short')
            arrow = '🟢 LONG' if z > 0 else '🔴 SHORT'
            extremes.append({
                'label': r['label'], 'z': z, 'dir': arrow, 'read': read,
                'text': f"{arrow} **{r['label']}** (Z {z:+.2f}) — {read}"
            })
    extremes.sort(key=lambda x: -abs(x['z']))

    # 2. BIGGEST WEEKLY SHIFTS (normalized by typical weekly move)
    #    Use |W/W| vs 1Y average |net| as a rough scale
    shift_scored = []
    for r in results:
        scale = max(abs(r['ave_1y']), 1)
        rel = abs(r['wow']) / scale
        shift_scored.append((rel, r))
    shift_scored.sort(key=lambda t: -t[0])
    for rel, r in shift_scored[:5]:
        direction = 'added longs' if r['wow'] > 0 else 'added shorts'
        info = INTERP.get(r['label'])
        cls = info[0] if info else ''
        shifts.append({
            'label': r['label'], 'wow': r['wow'],
            'text': f"**{r['label']}**: {r['wow']:+,} W/W — {direction}"
        })

    # 3. POSITIONING FLIPS (sign change vs prior week)
    #    We need prior-week net; recompute quickly isn't stored, so flag near-zero crossers
    #    (approx: latest and (latest - wow) have opposite signs)
    for r in results:
        prev = r['latest'] - r['wow']
        if (r['latest'] > 0) != (prev > 0) and abs(r['latest']) > 0:
            to = 'net LONG' if r['latest'] > 0 else 'net SHORT'
            frm = 'net short' if r['latest'] > 0 else 'net long'
            info = INTERP.get(r['label'])
            note = ''
            if info:
                note = f" — now {info[1]}"
            flips.append({
                'label': r['label'],
                'text': f"**{r['label']}** flipped from {frm} → {to}{note}"
            })

    # 4. SECTOR TILT
    for r in results:
        sec = r['section']
        sector.setdefault(sec, {'long': 0, 'short': 0, 'net': 0})
        if r['latest'] > 0:
            sector[sec]['long'] += 1
        else:
            sector[sec]['short'] += 1
        sector[sec]['net'] += r['latest']
    sector_notes = []
    for sec, d in sector.items():
        total = d['long'] + d['short']
        if d['long'] > d['short']:
            tilt = f"broadly LONG ({d['long']} of {total})"
        elif d['short'] > d['long']:
            tilt = f"broadly SHORT ({d['short']} of {total})"
        else:
            tilt = f"mixed ({d['long']} long / {d['short']} short)"
        # USD interpretation for currencies
        extra = ''
        if sec == 'CURRENCIES':
            extra = " — USD-bullish tilt" if d['short'] > d['long'] else \
                    (" — USD-bearish tilt" if d['long'] > d['short'] else "")
        sector_notes.append({'section': sec, 'text': f"**{sec.title()}**: {tilt}{extra}"})

    return dict(
        extremes=extremes,
        shifts=shifts,
        flips=flips,
        sector=sector_notes,
    )

def fetch_cot(code, limit=300):
    """Pull recent weekly reports for one contract code (~5.7 yrs at 300)."""
    params = {
        '$where': f"cftc_contract_market_code='{code}'",
        '$order': 'report_date_as_yyyy_mm_dd DESC',
        '$limit': limit,
    }
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    if not r.text.strip():
        return None
    df = pd.read_csv(StringIO(r.text))
    if df.empty:
        return None
    df['date'] = pd.to_datetime(df['report_date_as_yyyy_mm_dd'])
    return df.sort_values('date').reset_index(drop=True)


def analyze(df, label, section):
    if LONG_COL not in df.columns or SHORT_COL not in df.columns:
        return None, "missing position columns"
    df['net'] = df[LONG_COL] - df[SHORT_COL]
    net = df.set_index('date')['net'].astype(float)

    latest = net.iloc[-1]
    wow    = latest - net.iloc[-2]

    def ave(n):  return float(net.tail(n).mean()) if len(net) >= 5 else float(net.mean())
    def zscore(n):
        w = net.tail(n)
        if len(w) < 5 or w.std() == 0:
            return None
        return float((latest - w.mean()) / w.std())

    return dict(
        label=label, section=section,
        market=str(df['market_and_exchange_names'].iloc[-1]),
        report_date=net.index[-1].strftime('%Y-%m-%d'),
        latest=int(round(latest)),
        wow=int(round(wow)),
        ave_3m=int(round(ave(13))),
        ave_6m=int(round(ave(26))),
        ave_1y=int(round(ave(52))),
        max_3y=int(round(net.tail(156).max())),
        min_3y=int(round(net.tail(156).min())),
        z_1y=zscore(52),
        z_3y=zscore(156),
        n_weeks=int(len(net)),
    ), None


# ---------- RUN ----------
results = []
print("Fetching CFTC COT data (verify matched market names below)...")
print("=" * 78)

for section, items in UNIVERSE.items():
    print(f"\n--- {section} ---")
    for label, code in items:
        try:
            df = fetch_cot(code)
            if df is None:
                print(f"❌ {label:18s} code={code}: NO DATA")
                continue
            res, err = analyze(df, label, section)
            if err:
                print(f"⚠️  {label:18s} code={code}: {err}")
                continue
            results.append(res)
            print(f"✅ {label:18s} → '{res['market']}'  "
                  f"({res['n_weeks']} wks, {res['report_date']})")
        except Exception as e:
            print(f"❌ {label:18s} code={code}: ERROR {e}")

print("\n" + "=" * 78)
print(f"Matched {len(results)} instruments.\n")

# ---------- SUMMARY TABLE (for visual verification) ----------
if results:
    out = pd.DataFrame(results)
    show = out[['section','label','latest','wow','ave_3m','ave_6m','ave_1y',
                'max_3y','min_3y','z_1y','z_3y']].copy()
    show.columns = ['Section','Metric','Latest','W/W','3M Ave','6M Ave','1Y Ave',
                    '3Y Max','3Y Min','Z-1Y','Z-3Y']
    show['Z-1Y'] = show['Z-1Y'].map(lambda x: f"{x:+.2f}" if x is not None else "n/a")
    show['Z-3Y'] = show['Z-3Y'].map(lambda x: f"{x:+.2f}" if x is not None else "n/a")
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 220)
    pd.set_option('display.max_rows', None)
    print(show.to_string(index=False))

    # ---------- WRITE OUTPUTS ----------
    report_date = max(r['report_date'] for r in results)
    payload = dict(
        report_date=report_date,
        generated=datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M UTC'),
        instruments=results,
        callouts=build_callouts(results, z_threshold=2.0),
    )
    with open('cftc.json', 'w') as f:
        json.dump(payload, f, indent=2)
    out.to_csv('cftc.csv', index=False)
    print(f"\n✅ Wrote cftc.json + cftc.csv  (report_date {report_date})")
else:
    print("No results — check codes above.")
