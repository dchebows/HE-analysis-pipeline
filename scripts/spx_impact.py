"""
SPX Constituents Relative Impact By Market Cap
Run after the close (GitHub Actions). Writes spx_impact.json.
"""
import json
import time
import warnings
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import io

warnings.filterwarnings("ignore")

OUTPUT_JSON = "spx_impact.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


# ------------------------------------------------------------
# STEP 1: Constituents
# ------------------------------------------------------------
def get_tickers():
    print("Step 1: Fetching S&P 500 constituents from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    table = pd.read_html(io.StringIO(r.text))[0]
    tickers = [t.replace(".", "-") for t in table["Symbol"].tolist()]
    print(f"  Found {len(tickers)} tickers")
    return tickers


# ------------------------------------------------------------
# STEP 2: Daily returns
# ------------------------------------------------------------
def get_daily_returns(tickers):
    print("\nStep 2: Downloading price data from Yahoo Finance...")
    px = yf.download(tickers, period="5d", auto_adjust=True,
                     progress=False, threads=True)["Close"]
    px = px.dropna(how="all").iloc[-2:]
    if px.shape[0] < 2:
        raise ValueError("Not enough trading days in data.")
    ret = ((px.iloc[-1] - px.iloc[-2]) / px.iloc[-2] * 100).dropna()
    trading_date = px.index[-1].strftime("%Y-%m-%d")
    print(f"  Got returns for {len(ret)} tickers | Trading date: {trading_date}")
    return ret, trading_date


# ------------------------------------------------------------
# STEP 3: Market caps (Yahoo primary, Finviz fallback)
# ------------------------------------------------------------
def fetch_yahoo_cap(tk):
    for attempt in range(2):
        try:
            mc = yf.Ticker(tk).fast_info["market_cap"]
            if mc and mc > 0:
                return tk, float(mc)
        except Exception:
            time.sleep(0.5)
    return tk, None


def scrape_finviz_caps():
    print("  Falling back to Finviz for missing market caps...")
    hdrs = {"User-Agent": UA}
    base = "https://finviz.com/screener.ashx?v=152&f=idx_sp500&c=0,1,6"
    mult = {"T": 1e12, "B": 1e9, "M": 1e6}
    caps, row_start = {}, 1

    while row_start <= 520:
        try:
            r = requests.get(f"{base}&r={row_start}", headers=hdrs, timeout=15)
            r.raise_for_status()

            tbl = None
            for d in pd.read_html(io.StringIO(r.text)):
                if len(d) > 5 and "Ticker" in d.columns:
                    tbl = d
                    break
                if len(d) > 5 and d.shape[1] >= 3:
                    d.columns = d.iloc[0]
                    d = d.iloc[1:]
                    if "Ticker" in d.columns:
                        tbl = d
                        break
            if tbl is None or len(tbl) == 0:
                break

            for _, row in tbl.iterrows():
                try:
                    s = str(row["Market Cap"]).strip()
                    if s in ("-", "nan", ""):
                        continue
                    m = mult.get(s[-1], 1)
                    if s[-1] in mult:
                        s = s[:-1]
                    tk = str(row["Ticker"]).strip().replace(".", "-")
                    caps[tk] = float(s.replace(",", "")) * m
                except Exception:
                    continue

            row_start += 20
            time.sleep(0.3)
        except Exception as e:
            print(f"    Finviz error at row {row_start}: {e}")
            break

    print(f"  Finviz: got {len(caps)} market caps")
    return caps


def get_market_caps(symbols):
    print("\nStep 3: Fetching market caps...")
    start = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_yahoo_cap, symbols))
    caps = {tk: mc for tk, mc in results if mc}
    print(f"  Yahoo: {len(caps)} caps in {time.time() - start:.1f}s")

    missing = [t for t in symbols if t not in caps]
    print(f"  Missing: {len(missing)}")
    if len(missing) > 20:
        fv = scrape_finviz_caps()
        for t in missing:
            if t in fv:
                caps[t] = fv[t]
    return caps


# ------------------------------------------------------------
# STEP 4-5: Weights, impact, rankings
# ------------------------------------------------------------
def build_records(sub):
    return [
        {
            "ticker": tk,
            "ret": round(float(r["ret"]), 4),
            "impact": round(float(r["impact"]), 4),
            "weight": round(float(r["weight"]), 4),
        }
        for tk, r in sub.iterrows()
    ]


def main():
    tickers = get_tickers()
    daily_return, trading_date = get_daily_returns(tickers)
    market_caps = get_market_caps(list(daily_return.index))

    print("\nStep 4: Calculating weights and impact...")
    df = pd.DataFrame({"ret": daily_return, "cap": pd.Series(market_caps)}).dropna()
    if df.empty:
        raise RuntimeError("No stocks with both return and market cap.")
    print(f"  Working with {len(df)} stocks")

    df["weight"] = df["cap"] / df["cap"].sum() * 100
    df["impact"] = df["ret"] * df["weight"] / 100

    print("\nStep 5: Ranking...")
    top_pos = df.nlargest(10, "impact")
    top_neg = df.nsmallest(10, "impact")

    out = {
        "trading_date": trading_date,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_stocks": int(len(df)),
        "n_total": int(len(tickers)),
        "spx_est_move": round(float(df["impact"].sum()), 4),
        "top_positive": build_records(top_pos),
        "top_negative": build_records(top_neg),
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n✅ Wrote {OUTPUT_JSON}")
    print(f"  Trading date: {trading_date}")
    print(f"  Est. SPX move: {out['spx_est_move']:+.2f}%")
    print(f"  Top contributor: {out['top_positive'][0]['ticker']} "
          f"({out['top_positive'][0]['impact']:+.2f})")
    print(f"  Top detractor:   {out['top_negative'][0]['ticker']} "
          f"({out['top_negative'][0]['impact']:+.2f})")


if __name__ == "__main__":
    main()
