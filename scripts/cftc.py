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
    )
    with open('cftc.json', 'w') as f:
        json.dump(payload, f, indent=2)
    out.to_csv('cftc.csv', index=False)
    print(f"\n✅ Wrote cftc.json + cftc.csv  (report_date {report_date})")
else:
    print("No results — check codes above.")
