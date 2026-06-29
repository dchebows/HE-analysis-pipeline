# scripts/debt_market.py
# Fetches debt-market data, computes analytics, writes JSON + CSV for Streamlit.
import os, json
import pandas as pd, numpy as np
import yfinance as yf
from fredapi import Fred
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

FRED_KEY = os.environ["FRED_KEY"]
fred = Fred(api_key=FRED_KEY)
LOOKBACK_MONTHS = 20

START = (datetime.now().date() - relativedelta(months=LOOKBACK_MONTHS)).strftime('%Y-%m-%d')
TOMORROW = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')

def get_fred(code):
    s = fred.get_series(code, observation_start=START).dropna()
    s.index = pd.to_datetime(s.index)
    return s

def get_yahoo(ticker):
    d = yf.download(ticker, start=START, end=TOMORROW, progress=False)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    s = d['Close'].dropna(); s.index = pd.to_datetime(s.index)
    return s

# ---------- analytics (same logic as the notebook) ----------
def compute_metrics(s):
    s = s.dropna(); last_dt = s.index[-1]
    last, d1 = s.iloc[-1], s.iloc[-2]
    w1 = s.asof(last_dt - pd.Timedelta(days=7))
    m1 = s.asof(last_dt - pd.Timedelta(days=30))
    f = lambda c, p: [(c-p)*100, (c/p-1)*100 if p else None]
    return dict(last=float(last), d1=float(d1), w1=float(w1), m1=float(m1),
                last_dt=last_dt.strftime('%Y-%m-%d'),
                dod=f(last,d1), wow=f(last,w1), mom=f(last,m1))

def detect_trend_change(s, fast=20, slow=50, z_win=60):
    s = s.dropna()
    fma, sma = s.rolling(fast).mean(), s.rolling(slow).mean()
    above = fma > sma
    ma_cross = bool(above.iloc[-1] != above.iloc[-min(6,len(above))])
    slope = s.rolling(fast).mean().diff()
    sn, sp = np.sign(slope.iloc[-1]), np.sign(slope.iloc[-min(6,len(slope))])
    slope_flip = bool(sn != sp and sn != 0)
    mu, sd = s.rolling(z_win).mean(), s.rolling(z_win).std()
    z = (s-mu)/sd; z_now = float(z.iloc[-1]) if not np.isnan(z.iloc[-1]) else 0.0
    z_break = abs(z_now) > 1.5
    score = (40 if ma_cross else 0) + (35 if slope_flip else 0) + \
            (min(25, abs(z_now)/3*25) if z_break else 0)
    score = round(min(100, score))
    trend = 'Rising' if sn>0 else 'Falling' if sn<0 else 'Flat'
    fired = ma_cross or slope_flip or z_break
    strength = 'Strong' if score>=70 else 'Moderate' if score>=40 else 'Weak' if score>0 else '-'
    return dict(trend=trend, change=fired, score=score, strength=strength, z=z_now)

def classify_steepener(d2, d10):
    if d10 > d2:
        regime = 'Bear Steepener' if d10>0 else 'Bull Steepener'
        interp = 'Long-end selling off faster' if d10>0 else 'Front-end rallying faster'
    else:
        regime = 'Bear Flattener' if d2>0 else 'Bull Flattener'
        interp = 'Front-end selling off faster' if d2>0 else 'Long-end rallying faster'
    return regime, interp

def pct_rank(s, v): return float((s.dropna() <= v).mean()*100)

# ---------- fetch ----------
print("Fetching...")
MOVE = get_yahoo('^MOVE')
HY   = get_fred('BAMLH0A0HYM2')
BBB  = get_fred('BAMLC0A4CBBB')
HYG  = get_yahoo('HYG')
Y2   = get_fred('DGS2')
Y10  = get_fred('DGS10')
spread = (Y10 - Y2).dropna()

# ---------- metrics + trends ----------
panels = {}
panels['MOVE']   = dict(metrics=compute_metrics(MOVE), trend=detect_trend_change(MOVE), kind='vol',  name='MOVE')
panels['HY_OAS'] = dict(metrics=compute_metrics(HY),   trend=detect_trend_change(HY),   kind='credit', name='HY OAS')
panels['BBB_OAS']= dict(metrics=compute_metrics(BBB),  trend=detect_trend_change(BBB),  kind='credit', name='BBB OAS')

m2, m10, msp = compute_metrics(Y2), compute_metrics(Y10), compute_metrics(spread)
regime, interp = classify_steepener(m2['mom'][0], m10['mom'][0])
panels['CURVE'] = dict(metrics=msp, trend=detect_trend_change(spread), kind='curve',
                       name='2-10 Spread', regime=regime, interp=interp,
                       spread_level=float(spread.iloc[-1]),
                       m2=m2, m10=m10)

# ---------- risk score ----------
components = {
    'Rate Vol (MOVE)':   dict(pct=pct_rank(MOVE, MOVE.iloc[-1]), weight=0.25),
    'HY Credit':         dict(pct=pct_rank(HY,   HY.iloc[-1]),   weight=0.30),
    'IG Credit (BBB)':   dict(pct=pct_rank(BBB,  BBB.iloc[-1]),  weight=0.20),
    'Yield Curve (2-10)':dict(pct=100-pct_rank(spread, spread.iloc[-1]), weight=0.25),
}
score = round(sum(c['pct']*c['weight'] for c in components.values()))
regime_lbl = ('HIGH STRESS' if score>=70 else 'ELEVATED' if score>=45
              else 'NEUTRAL' if score>=30 else 'CALM')

# ---------- build highlights (action-oriented) ----------
def build_highlights(panels):
    risk_off, risk_on, curve, trend = [], [], [], []
    for key, r in panels.items():
        m, name, kind = r['metrics'], r['name'], r['kind']
        wow_pct = m['wow'][1]; mom_bps = m['mom'][0]
        if kind=='vol':
            if wow_pct and wow_pct>3:
                risk_off.append(f"Bond volatility (MOVE) +{wow_pct:.0f}% WoW — rate markets jumpier. → Choppier Treasuries; hedging costs rising.")
            elif wow_pct and wow_pct<-3:
                risk_on.append(f"Bond volatility (MOVE) {wow_pct:.0f}% WoW — rates calming. → Supportive for risk assets.")
        elif kind=='credit':
            tier = "junk-rated borrowers" if 'HY' in name else "lowest investment-grade borrowers"
            if mom_bps>5:
                risk_off.append(f"{name} +{mom_bps:.0f} bps MoM — investors demanding MORE yield for {tier} (spreads widening = rising credit fear). → Watch equity weakness; refinancing pricier.")
            elif mom_bps<-5:
                risk_on.append(f"{name} {mom_bps:.0f} bps MoM — spreads tightening (confidence in {tier}). → Credit conditions easing.")
        elif kind=='curve':
            lvl = r['spread_level']*100; reg = r['regime']
            help_ = {
                'Bull Steepener':"short rates falling faster than long — 'Fed easing' setup. → Often risk-ON.",
                'Bear Steepener':"long rates rising faster than short — growth/inflation/issuance. → Pressures long bonds & REITs/utilities.",
                'Bull Flattener':"long rates falling faster — flight-to-safety. → Defensive/risk-OFF tone.",
                'Bear Flattener':"short rates rising faster — Fed staying higher. → Squeezes bank margins.",
            }[reg]
            if lvl<0:
                shape=f"INVERTED at {lvl:+.0f} bps ⚠️ — short yields ABOVE long. Has preceded most recessions. → Defensive bias."
            elif lvl<25:
                shape=f"flat at {lvl:+.0f} bps — barely positive, nearly inverted. → Watch closely."
            else:
                shape=f"positive at {lvl:+.0f} bps — normal upward slope. → Healthy baseline."
            curve.append(f"2-10 spread {shape}")
            curve.append(f"Regime: {reg} — {help_}")
        tc = r['trend']
        if tc['change']:
            d = tc['trend']
            if kind=='credit': meaning = "spreads turning WIDER (credit risk building)" if d=='Rising' else "spreads turning TIGHTER (risk easing)"
            elif kind=='vol':  meaning = "volatility turning UP" if d=='Rising' else "volatility turning DOWN (calming)"
            elif kind=='curve':meaning = "curve steepening" if d=='Rising' else "curve flattening (watch for inversion)"
            else: meaning = d.lower()
            conv = {'Strong':'high-conviction','Moderate':'moderate','Weak':'early/low-conviction'}[tc['strength']]
            trend.append(f"{name}: possible reversal — {meaning} [{conv}, {tc['score']}/100]")
    return dict(risk_off=risk_off, risk_on=risk_on, curve=curve, trend=trend)

highlights = build_highlights(panels)

# ---------- write JSON ----------
out = dict(
    as_of = max(p['metrics']['last_dt'] for p in panels.values()),
    generated = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    risk = dict(score=score, regime=regime_lbl, components=components),
    panels = panels,
    highlights = highlights,
)
with open('debt_market.json','w') as f:
    json.dump(out, f, indent=2, default=str)

# ---------- write CSV (time series for plotting) ----------
series = pd.DataFrame({
    'MOVE': MOVE, 'HY_OAS': HY, 'BBB_OAS': BBB, 'HYG': HYG,
    'Y2': Y2, 'Y10': Y10, 'SPREAD': spread
})
series.index.name = 'date'
series.to_csv('debt_series.csv')

print(f"Wrote debt_market.json + debt_series.csv  (as_of {out['as_of']}, risk {score})")
