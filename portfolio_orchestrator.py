#!/usr/bin/env python3
"""
Portfolio Signal Orchestrator - GitHub Actions Version
Generates daily trading signals for multi-asset portfolio
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta
import logging
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

ASSETS_TO_RUN = ['SPX', 'GOLD', 'COMPQ', 'RUT', 'USD']

PORTFOLIO_VALUE = 100_000
INITIAL_INVESTMENT = 100_000
CASH_ANNUAL_RATE = 0.02
CASH_DAILY_RATE = (1 + CASH_ANNUAL_RATE) ** (1/252) - 1

BACKTEST_START = '2017-01-01'
ENRICHED_CSV_PATH = Path('Risk_Range_Data/04_enriched')

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-5s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('PortfolioOrchestrator')

# ============================================================
# ASSET REGISTRY
# ============================================================

ASSET_REGISTRY = {
    'SPX': {
        'name': 'S&P 500',
        'enriched_file': 'SPX_enriched.csv',
        'v5b_params': {
            'ath_bull_thresh': -1.0, 'ath_bear_thresh': -6.0,
            'rh_period': 63, 'rh_bull_thresh': -2.2, 'rh_bear_thresh': -4.0,
            'use_secondary_rh': False, 'secondary_rh_period': 252,
            'roc_period': 50, 'roc_bull_thresh': 2.0, 'roc_bear_thresh': -4.0,
            'vol_period': 21, 'confirm_days': 1, 'score_smooth': 4,
            'bull_score_thresh': 0.20, 'bear_score_thresh': -0.10,
            'ath_weight': 0.30, 'rh_weight': 0.15, 'roc_weight': 0.10,
            'vol_weight': 0.05, 'vix_weight': 0.10, 'level_slope_weight': 0.05,
            'level_slope_period': 10, 'hysteresis': 0.10, 'score_weak_zone': 0.03,
            'hysteresis_bull_exit_mult': 1.0, 'hysteresis_bear_exit_mult': 1.0,
            'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
        },
        'danger_params': {
            'vix_l1': 20, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
            'vix_l3': 25, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
            'vix_l5': 35, 'd_vix_l5': 15,
            'dd_l1': -0.03, 'd_dd_l1': 1, 'dd_l2': -0.05, 'd_dd_l2': 4,
            'dd_l3': -0.10, 'd_dd_l3': 7, 'dd_l4': -0.15, 'd_dd_l4': 10,
        },
    },
    'GOLD': {
        'name': 'Gold Futures',
        'enriched_file': 'GOLD_enriched.csv',
        'v5b_params': {
            'ath_bull_thresh': -5.0, 'ath_bear_thresh': -18.0,
            'rh_period': 90, 'rh_bull_thresh': -6.0, 'rh_bear_thresh': -12.0,
            'use_secondary_rh': True, 'secondary_rh_period': 180,
            'roc_period': 90, 'roc_bull_thresh': 1.5, 'roc_bear_thresh': -3.0,
            'vol_period': 21, 'confirm_days': 2, 'score_smooth': 4,
            'bull_score_thresh': 0.20, 'bear_score_thresh': -0.10,
            'ath_weight': 0.35, 'rh_weight': 0.15, 'roc_weight': 0.15,
            'vol_weight': 0.05, 'vix_weight': 0.00, 'level_slope_weight': 0.05,
            'level_slope_period': 10, 'hysteresis': 0.12, 'score_weak_zone': 0.03,
            'hysteresis_bull_exit_mult': 1.0, 'hysteresis_bear_exit_mult': 1.0,
            'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
        },
        'danger_params': {
            'vix_l1': 18, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
            'vix_l3': 26, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
            'vix_l5': 35, 'd_vix_l5': 15,
            'dd_l1': -0.05, 'd_dd_l1': 1, 'dd_l2': -0.10, 'd_dd_l2': 4,
            'dd_l3': -0.15, 'd_dd_l3': 7, 'dd_l4': -0.20, 'd_dd_l4': 10,
        },
    },
    'COMPQ': {
        'name': 'NASDAQ Composite',
        'enriched_file': 'COMPQ_enriched.csv',
        'v5b_params': {  # Same as SPX
            'ath_bull_thresh': -1.0, 'ath_bear_thresh': -6.0,
            'rh_period': 63, 'rh_bull_thresh': -2.2, 'rh_bear_thresh': -4.0,
            'use_secondary_rh': False, 'secondary_rh_period': 252,
            'roc_period': 50, 'roc_bull_thresh': 2.0, 'roc_bear_thresh': -4.0,
            'vol_period': 21, 'confirm_days': 1, 'score_smooth': 4,
            'bull_score_thresh': 0.20, 'bear_score_thresh': -0.10,
            'ath_weight': 0.30, 'rh_weight': 0.15, 'roc_weight': 0.10,
            'vol_weight': 0.05, 'vix_weight': 0.10, 'level_slope_weight': 0.05,
            'level_slope_period': 10, 'hysteresis': 0.10, 'score_weak_zone': 0.03,
            'hysteresis_bull_exit_mult': 1.0, 'hysteresis_bear_exit_mult': 1.0,
            'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
        },
        'danger_params': {
            'vix_l1': 20, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
            'vix_l3': 25, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
            'vix_l5': 35, 'd_vix_l5': 15,
            'dd_l1': -0.03, 'd_dd_l1': 1, 'dd_l2': -0.05, 'd_dd_l2': 4,
            'dd_l3': -0.10, 'd_dd_l3': 7, 'dd_l4': -0.15, 'd_dd_l4': 10,
        },
    },
    'RUT': {
        'name': 'Russell 2000',
        'enriched_file': 'RUT_enriched.csv',
        'v5b_params': {
            'ath_bull_thresh': -2.0, 'ath_bear_thresh': -15.0,
            'rh_period': 63, 'rh_bull_thresh': -3.0, 'rh_bear_thresh': -8.0,
            'use_secondary_rh': False, 'secondary_rh_period': 252,
            'roc_period': 50, 'roc_bull_thresh': 1.5, 'roc_bear_thresh': -5.0,
            'vol_period': 21, 'confirm_days': 1, 'score_smooth': 4,
            'bull_score_thresh': 0.10, 'bear_score_thresh': -0.20,
            'ath_weight': 0.30, 'rh_weight': 0.15, 'roc_weight': 0.10,
            'vol_weight': 0.05, 'vix_weight': 0.10, 'level_slope_weight': 0.05,
            'level_slope_period': 10, 'hysteresis': 0.15, 'score_weak_zone': 0.03,
            'hysteresis_bull_exit_mult': 1.0, 'hysteresis_bear_exit_mult': 1.0,
            'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
        },
        'danger_params': {
            'vix_l1': 23, 'd_vix_l1': 1, 'vix_l2': 25, 'd_vix_l2': 4,
            'vix_l3': 28, 'd_vix_l3': 8, 'vix_l4': 33, 'd_vix_l4': 12,
            'vix_l5': 38, 'd_vix_l5': 15,
            'dd_l1': -0.05, 'd_dd_l1': 1, 'dd_l2': -0.08, 'd_dd_l2': 4,
            'dd_l3': -0.12, 'd_dd_l3': 7, 'dd_l4': -0.18, 'd_dd_l4': 10,
        },
    },
    'USD': {
        'name': 'US Dollar Index',
        'enriched_file': 'USD_enriched.csv',
        'v5b_params': {  # Same as SPX
            'ath_bull_thresh': -1.0, 'ath_bear_thresh': -6.0,
            'rh_period': 63, 'rh_bull_thresh': -2.2, 'rh_bear_thresh': -4.0,
            'use_secondary_rh': False, 'secondary_rh_period': 252,
            'roc_period': 50, 'roc_bull_thresh': 2.0, 'roc_bear_thresh': -4.0,
            'vol_period': 21, 'confirm_days': 1, 'score_smooth': 4,
            'bull_score_thresh': 0.20, 'bear_score_thresh': -0.10,
            'ath_weight': 0.30, 'rh_weight': 0.15, 'roc_weight': 0.10,
            'vol_weight': 0.05, 'vix_weight': 0.10, 'level_slope_weight': 0.05,
            'level_slope_period': 10, 'hysteresis': 0.10, 'score_weak_zone': 0.03,
            'hysteresis_bull_exit_mult': 1.0, 'hysteresis_bear_exit_mult': 1.0,
            'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
        },
        'danger_params': {
            'vix_l1': 20, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
            'vix_l3': 25, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
            'vix_l5': 35, 'd_vix_l5': 15,
            'dd_l1': -0.03, 'd_dd_l1': 1, 'dd_l2': -0.05, 'd_dd_l2': 4,
            'dd_l3': -0.10, 'd_dd_l3': 7, 'dd_l4': -0.15, 'd_dd_l4': 10,
        },
    },
}

# ============================================================
# MODEL FUNCTIONS (SIMPLIFIED V5B)
# ============================================================

def trend_v5b_model(df_in, params):
    """
    Simplified V5B trend model for GitHub Actions
    Returns: (signal_series, score_series)
    """
    df_w = df_in.copy()
    n = len(df_w)
    p = params
    
    # Distance metrics
    expanding_high = df_w['close'].expanding().max()
    pct_from_ath = (df_w['close'] - expanding_high) / expanding_high * 100
    
    rolling_high = df_w['high'].rolling(p['rh_period'], min_periods=1).max()
    pct_from_rh = (df_w['close'] - rolling_high) / rolling_high * 100
    
    if p.get('use_secondary_rh', False):
        rh2 = df_w['high'].rolling(p['secondary_rh_period'], min_periods=1).max()
        pct_from_rh2 = (df_w['close'] - rh2) / rh2 * 100
    else:
        pct_from_rh2 = pct_from_rh.copy()
    
    # Momentum
    price_roc = df_w['close'].pct_change(p['roc_period']) * 100
    
    # Volatility
    daily_ret = df_w['close'].pct_change()
    rvol = daily_ret.rolling(p['vol_period']).std() * np.sqrt(252) * 100
    rvol_med = rvol.rolling(252, min_periods=63).median()
    rvol_ratio = rvol / (rvol_med + 1e-8)
    
    if 'vix_close' in df_w.columns:
        vix = df_w['vix_close']
        vix_med = vix.rolling(252, min_periods=63).median()
        vix_ratio = vix / (vix_med + 1e-8)
    else:
        vix_ratio = pd.Series(1.0, index=df_w.index)
    
    # Level slope
    buy_sell_mid = (df_w['buy_trade'] + df_w['sell_trade']) / 2
    level_slope = buy_sell_mid.pct_change(p['level_slope_period']) * 100
    ls_mean = level_slope.rolling(252, min_periods=63).mean()
    ls_std = level_slope.rolling(252, min_periods=63).std()
    ls_z = (level_slope - ls_mean) / (ls_std + 1e-8)
    
    # Normalization function
    def norm(s, bull_thresh, bear_thresh):
        mid = (bull_thresh + bear_thresh) / 2
        hr = (bull_thresh - bear_thresh) / 2
        if hr == 0:
            hr = 1
        return ((s - mid) / hr).clip(-1.5, 1.5)
    
    # Component scores
    ath_s = norm(pct_from_ath, p['ath_bull_thresh'], p['ath_bear_thresh'])
    rh_s = norm(pct_from_rh, p['rh_bull_thresh'], p['rh_bear_thresh'])
    rh2_s = norm(pct_from_rh2, p['rh_bull_thresh'] * 1.5, p['rh_bear_thresh'] * 1.5)
    roc_s = norm(price_roc, p['roc_bull_thresh'], p['roc_bear_thresh'])
    vol_s = -norm(rvol_ratio, 0.8, 1.3)
    vix_s = -norm(vix_ratio, 0.8, 1.3)
    ls_s = ls_z.clip(-2, 2) / 2
    
    # Composite score
    rh_each = p['rh_weight'] / 2
    tw = (p['ath_weight'] + p['rh_weight'] + p['roc_weight'] +
          p['vol_weight'] + p['vix_weight'] + p['level_slope_weight'])
    # Composite score (CONTINUING FROM WHERE IT CUT OFF)
    composite = (
        p['ath_weight'] * ath_s +
        rh_each * rh_s +
        rh_each * rh2_s +
        p['roc_weight'] * roc_s +
        p['vol_weight'] * vol_s +
        p['vix_weight'] * vix_s +
        p['level_slope_weight'] * ls_s
    ) / tw
    
    score = composite.rolling(p['score_smooth'], min_periods=1).mean()
    
    # Threshold to raw signal
    cs_arr = score.values
    raw = np.zeros(n)
    for i in range(n):
        cs = cs_arr[i]
        if np.isnan(cs):
            continue
        if cs > p['bull_score_thresh']:
            raw[i] = 1
        elif cs < p['bear_score_thresh']:
            raw[i] = -1
    
    # Confirmation
    confirmed = np.zeros(n)
    c_state, pending, pc = 0, None, 0
    cd = int(p.get('confirm_days', 2))
    for i in range(n):
        rs = int(raw[i])
        if rs != c_state:
            if pending == rs:
                pc += 1
            else:
                pending, pc = rs, 1
            if pc >= cd:
                c_state, pending, pc = rs, None, 0
        else:
            pending, pc = None, 0
        confirmed[i] = c_state
    
    # Hysteresis
    h = float(p.get('hysteresis', 0.10))
    h_bull_exit = h * float(p.get('hysteresis_bull_exit_mult', 1.0))
    h_bear_exit = h * float(p.get('hysteresis_bear_exit_mult', 1.0))
    weak_zone = float(p.get('score_weak_zone', 0.0))
    
    final = np.zeros(n)
    state = 0
    
    for i in range(n):
        cs = cs_arr[i]
        conf = int(confirmed[i])
        if np.isnan(cs):
            final[i] = state
            continue
        
        if state == 1:
            if conf == -1 or cs < p['bear_score_thresh'] + h_bull_exit:
                state = -1
            elif conf == 0 and cs < -h_bull_exit / 2:
                state = 0
        elif state == -1:
            if conf == 1 or cs > p['bull_score_thresh'] - h_bear_exit:
                state = 1
            elif conf == 0 and cs > h_bear_exit / 2:
                state = 0
        else:
            if conf == 1:
                state = 1
            elif conf == -1:
                state = -1
        
        final[i] = state
    
    sig_map = {1: 'BULLISH', -1: 'BEARISH', 0: 'NEUTRAL'}
    signal = pd.Series(final, index=df_in.index).map(sig_map)
    return signal, score

# ============================================================
# DANGER SCORE CALCULATION
# ============================================================

def compute_danger_score_row(score, score_vel, trend, vix, vix_5d, mkt_dd, danger_params):
    """Compute danger score for single row"""
    dp = danger_params
    d = 0.0
    
    # Signal 1: V5B Score
    if not np.isnan(score):
        if score < -0.30: d += 20
        elif score < -0.15: d += 15
        elif score < -0.05: d += 10
        elif score < 0.05: d += 5
        elif score < 0.15: d += 2
    
    # Signal 2: Score Velocity
    if not np.isnan(score_vel):
        if score_vel < -0.30: d += 15
        elif score_vel < -0.20: d += 10
        elif score_vel < -0.10: d += 5
        elif score_vel < -0.05: d += 2
    
    # Signal 3: TREND
    if isinstance(trend, str):
        if trend == 'BEARISH': d += 15
        elif trend == 'NEUTRAL': d += 5
    
    # Signal 4: VIX
    if not np.isnan(vix):
        if vix > dp['vix_l5']: d += dp['d_vix_l5']
        elif vix > dp['vix_l4']: d += dp['d_vix_l4']
        elif vix > dp['vix_l3']: d += dp['d_vix_l3']
        elif vix > dp['vix_l2']: d += dp['d_vix_l2']
        elif vix > dp['vix_l1']: d += dp['d_vix_l1']
    
    # Signal 5: VIX Accel
    if not np.isnan(vix_5d):
        if vix_5d > 0.50: d += 10
        elif vix_5d > 0.30: d += 7
        elif vix_5d > 0.15: d += 3
    
    # Signal 6: Market DD
    if not np.isnan(mkt_dd):
        if mkt_dd < dp['dd_l4']: d += dp['d_dd_l4']
        elif mkt_dd < dp['dd_l3']: d += dp['d_dd_l3']
        elif mkt_dd < dp['dd_l2']: d += dp['d_dd_l2']
        elif mkt_dd < dp['dd_l1']: d += dp['d_dd_l1']
    
    return min(d, 100)

def compute_danger_score(bt_df, danger_params):
    """Compute danger scores for all rows"""
    n = len(bt_df)
    danger = np.zeros(n)
    score = bt_df['score_prev'].values
    score_vel = bt_df['score_vel_prev'].values
    trend = bt_df['trend_prev'].values
    vix = bt_df['vix_prev'].values
    vix_5d = bt_df['vix_5d_chg'].values
    mkt_dd = bt_df['market_dd_prev'].values
    
    for i in range(n):
        danger[i] = compute_danger_score_row(
            score[i], score_vel[i], trend[i],
            vix[i], vix_5d[i], mkt_dd[i], danger_params
        )
    return danger

def raw_weight_from_danger(danger_score):
    """Map danger score to position size"""
    t1, t2, t3, t4 = 25, 45, 65, 80
    w1, w2, w3, w4 = 1.0, 0.70, 0.35, 0.15
    d = danger_score
    if d <= t1:
        return w1
    elif d <= t2:
        frac = (d - t1) / (t2 - t1)
        return w1 + (w2 - w1) * frac
    elif d <= t3:
        frac = (d - t2) / (t3 - t2)
        return w2 + (w3 - w2) * frac
    elif d <= t4:
        frac = (d - t3) / (t4 - t3)
        return w3 + (w4 - w3) * frac
    else:
        return w4

# ============================================================
# BACKTEST ENGINE
# ============================================================

def run_backtest(bt_df, danger_arr):
    """Run D1 strategy backtest"""
    n = len(bt_df)
    raw_weights = np.array([raw_weight_from_danger(d) for d in danger_arr])
    
    # Simplified circuit breaker
    smooth_weights = np.zeros(n)
    smooth_weights[0] = raw_weights[0]
    
    max_daily_up = 0.18
    max_daily_down = 0.40
    
    for i in range(1, n):
        change = raw_weights[i] - smooth_weights[i-1]
        if change > 0:
            change = min(change, max_daily_up)
        else:
            change = max(change, -max_daily_down)
        smooth_weights[i] = np.clip(smooth_weights[i-1] + change, 0.10, 1.0)
    
    # Calculate equity curve
    final_equity = np.zeros(n)
    daily_rets = np.zeros(n)
    final_equity[0] = INITIAL_INVESTMENT
    
    for i in range(1, n):
        dr = bt_df['daily_return'].iloc[i]
        if np.isnan(dr):
            dr = 0.0
        w = smooth_weights[i]
        pr = w * dr + (1 - w) * CASH_DAILY_RATE
        daily_rets[i] = pr
        final_equity[i] = final_equity[i-1] * (1 + pr)
    
    return smooth_weights, final_equity, daily_rets

def calc_metrics(equity, daily_rets, bt_df):
    """Calculate backtest metrics"""
    eq_s = pd.Series(equity)
    ret_s = pd.Series(daily_rets)
    final = equity[-1]
    n_years = ((bt_df['date'].iloc[-1] - bt_df['date'].iloc[0]).days / 365.25)
    
    total_r = (final / INITIAL_INVESTMENT - 1) * 100
    cagr = ((final / INITIAL_INVESTMENT) ** (1/n_years) - 1) * 100
    
    rm = eq_s.expanding().max()
    dd = (eq_s - rm) / rm * 100
    max_dd = dd.min()
    
    vol = ret_s.std() * np.sqrt(252) * 100
    sharpe = (((ret_s.mean() - CASH_DAILY_RATE) / ret_s.std()) * np.sqrt(252)
              if ret_s.std() > 0 else 0)
    
    return {
        'final_value': final,
        'total_return': total_r,
        'cagr': cagr,
        'max_drawdown': max_dd,
        'volatility': vol,
        'sharpe': sharpe,
    }

# ============================================================
# DATA LOADING
# ============================================================

def load_enriched_data(asset, cfg):
    """Load enriched CSV for asset"""
    csv_path = ENRICHED_CSV_PATH / cfg['enriched_file']
    
    if not csv_path.exists():
        logger.error(f"Enriched file not found: {csv_path}")
        return None
    
    try:
        df = pd.read_csv(csv_path)
        df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
        df = df.rename(columns={'Date': 'date'})
        
        # Detect OHLC columns (dynamic prefix detection)
        ohlc_cols = [c for c in df.columns if c.endswith(('_Open', '_High', '_Low', '_Close'))]
        if ohlc_cols:
            prefix = ohlc_cols[0].rsplit('_', 1)[0]
            col_rename = {
                f'{prefix}_Open': 'open',
                f'{prefix}_High': 'high',
                f'{prefix}_Low': 'low',
                f'{prefix}_Close': 'close',
            }
            df = df.rename(columns=col_rename)
        
        # Detect VIX column
        vix_cols = [c for c in df.columns if 'VIX' in c and c.endswith('_Close')]
        if vix_cols:
            df = df.rename(columns={vix_cols[0]: 'vix_close'})
        
        # Rename Risk Range columns
        df = df.rename(columns={
            'BUY TRADE': 'buy_trade',
            'SELL TRADE': 'sell_trade',
            'PREV. CLOSE': 'prev_close',
            'TREND': 'trend'
        })
        
        # Ensure numeric types
        for c in ['open', 'high', 'low', 'close', 'buy_trade', 'sell_trade']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce')
        
        df = df.dropna(subset=['close']).reset_index(drop=True)
        
        logger.info(f"  Loaded {len(df)} rows from {csv_path.name}")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load {csv_path}: {e}")
        return None

# ============================================================
# ASSET PROCESSOR
# ============================================================

def process_asset(asset, cfg):
    """Process single asset and return summary metrics"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {asset}")
    logger.info(f"{'='*60}")
    
    try:
        # Load data
        df = load_enriched_data(asset, cfg)
        if df is None:
            return None
        
        # Run V5B model
        df['trend'], df['v5b_score'] = trend_v5b_model(df, cfg['v5b_params'])
        
        # Prepare backtest
        bt = df[df['date'] >= BACKTEST_START].copy().reset_index(drop=True)
        
        if len(bt) < 252:
            logger.warning(f"  Insufficient data for backtest ({len(bt)} days)")
            return None
        
        bt['daily_return'] = bt['close'].pct_change().fillna(0)
        bt['score_prev'] = bt['v5b_score'].shift(1)
        bt['score_vel_prev'] = (bt['v5b_score'] - bt['v5b_score'].shift(5)).shift(1)
        bt['trend_prev'] = bt['trend'].shift(1)
        
        bt['vix_prev'] = bt['vix_close'].shift(1) if 'vix_close' in bt.columns else 15.0
        bt['vix_5d_chg'] = (bt['vix_prev'] / bt['vix_prev'].shift(5) - 1) if 'vix_close' in bt.columns else 0.0
        
        # Market high from FULL dataset
        full_market_high = df['close'].expanding().max()
        bt_start_idx = df[df['date'] >= BACKTEST_START].index[0]
        bt['market_high'] = full_market_high.iloc[bt_start_idx:].reset_index(drop=True)
        bt['market_dd_prev'] = ((bt['close'] - bt['market_high']) / bt['market_high']).shift(1)
        
        # Run backtest
        danger = compute_danger_score(bt, cfg['danger_params'])
        bt['danger_score'] = danger
        d1_weights, d1_equity, d1_rets = run_backtest(bt, danger)
        bt['d1_weight'] = d1_weights
        bt['d1_equity'] = d1_equity
        
        # Compute metrics
        d1_m = calc_metrics(d1_equity, d1_rets, bt)
        
        # Get latest signal
        last_row = bt.iloc[-1]
        last_date = last_row['date'].date()
        
        # Prospective danger
        prosp_danger = compute_danger_score_row(
            last_row['v5b_score'],
            last_row['v5b_score'] - bt['v5b_score'].iloc[-6] if len(bt) >= 6 else 0,
            last_row['trend'],
            last_row.get('vix_close', 15.0),
            last_row['vix_5d_chg'] if 'vix_5d_chg' in last_row else 0,
            last_row['market_dd_prev'],
            cfg['danger_params']
        )
        
        # Position sizing
        raw_weight = raw_weight_from_danger(prosp_danger)
        current_weight = last_row['d1_weight']
        
        max_daily_up = 0.18
        max_daily_down = 0.40
        raw_change = raw_weight - current_weight
        if raw_change > 0:
            capped_change = min(raw_change, max_daily_up)
        else:
            capped_change = max(raw_change, -max_daily_down)
        prosp_weight = float(np.clip(current_weight + capped_change, 0.10, 1.0))
        
        # Action determination
        weight_change = prosp_weight - current_weight
        SIGNIFICANT = 0.03
        MINOR = 0.01
        
        if abs(weight_change) < MINOR:
            action = 'HOLD'
            action_icon = '⏸️'
        elif weight_change > SIGNIFICANT:
            action = 'BUY'
            action_icon = '🟢'
        elif weight_change < -SIGNIFICANT:
            action = 'SELL'
            action_icon = '🔴'
        elif weight_change > MINOR:
            action = 'LIGHT BUY'
            action_icon = '🟡'
        else:
            action = 'LIGHT SELL'
            action_icon = '🟡'
        
        # Danger zone
        if prosp_danger <= 25:
            zone = 'SAFE'
            zone_icon = '🟢'
        elif prosp_danger <= 45:
            zone = 'WATCH'
            zone_icon = '🟡'
        elif prosp_danger <= 65:
            zone = 'RISK'
            zone_icon = '🟠'
        elif prosp_danger <= 80:
            zone = 'DANGER'
            zone_icon = '🔴'
        else:
            zone = 'CRISIS'
            zone_icon = '🚨'
        
        logger.info(f"  ✅ {asset} complete: {action} | Target: {prosp_weight*100:.0f}% | Danger: {prosp_danger:.0f}")
        
        return {
            'Asset': asset,
            'Name': cfg['name'],
            'Last_Date': last_date,
            'Close': last_row['close'],
            'Trend': last_row['trend'],
            'V5B_Score': last_row['v5b_score'],
            'Action': action,
            'Action_Icon': action_icon,
            'Current_Weight': current_weight,
            'Target_Weight': prosp_weight,
            'Weight_Change': weight_change,
            'Danger_Score': prosp_danger,
            'Zone': zone,
            'Zone_Icon': zone_icon,
            'Sharpe': d1_m['sharpe'],
            'CAGR': d1_m['cagr'],
            'Max_DD': d1_m['max_drawdown'],
            'Invested_Dollars': prosp_weight * PORTFOLIO_VALUE,
            'Cash_Dollars': (1 - prosp_weight) * PORTFOLIO_VALUE,
            'Dollar_Change': weight_change * PORTFOLIO_VALUE,
        }
        
    except Exception as e:
        logger.error(f"  ❌ Error processing {asset}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ============================================================
# MAIN EXECUTION
# ============================================================

def main():
    logger.info("="*70)
    logger.info("PORTFOLIO ORCHESTRATOR START")
    logger.info("="*70)
    
    results = []
    
    for asset in ASSETS_TO_RUN:
        cfg = ASSET_REGISTRY.get(asset)
        if not cfg:
            logger.error(f"No configuration found for {asset}")
            continue
        
        result = process_asset(asset, cfg)
        if result:
            results.append(result)
    
    if not results:
        logger.error("No assets processed successfully")
        return
    
    # Create summary DataFrame
    summary_df = pd.DataFrame(results)
    
    # Save summary CSV
    summary_csv_path = 'portfolio_summary.csv'
    summary_df.to_csv(summary_csv_path, index=False)
    logger.info(f"\n✅ Saved summary to {summary_csv_path}")
    
    # Generate text report
    generate_text_report(summary_df)
    
    logger.info("\n" + "="*70)
    logger.info("✅ PORTFOLIO ORCHESTRATOR COMPLETE")
    logger.info("="*70)

def generate_text_report(summary_df):
    """Generate human-readable text report"""
    lines = []
    lines.append("=" * 80)
    lines.append("  MULTI-ASSET DAILY ACTION SIGNALS")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary table
    lines.append("SUMMARY TABLE:")
    lines.append("─" * 110)
    lines.append(f"{'ASSET':<8s} │ {'ACTION':<12s} │ {'ΔWeight':>8s} │ {'TGT%':>4s} │ {'DNGR':>4s} │ {'SHRP':>5s} │ {'CAGR':>6s} │ {'MaxDD':>6s} │ {'TREND':<7s}")
    lines.append("─" * 110)
    
    for _, row in summary_df.iterrows():
        action_str = f"{row['Action_Icon']} {row['Action']}"
        delta_pct = row['Weight_Change'] * 100
        delta_str = f"{delta_pct:+.0f}%" if abs(delta_pct) >= 0.5 else "—"
        
        lines.append(
            f"{row['Asset']:<8s} │ {action_str:<12s} │ {delta_str:>8s} │ "
            f"{row['Target_Weight']*100:>3.0f}% │ {row['Danger_Score']:>4.0f} │ "
            f"{row['Sharpe']:>5.2f} │ {row['CAGR']:>5.1f}% │ "
            f"{row['Max_DD']:>5.1f}% │ {row['Trend']:<7s}"
        )
    
    lines.append("")
    lines.append("Legend: ΔWeight = Target - Current | TGT% = Target Position | DNGR = Danger Score")
    lines.append("        SHRP = Sharpe | CAGR = Annual Return | MaxDD = Max Drawdown")
    lines.append("        🟢 = Buy | 🔴 = Sell | 🟡 = Light adjustment | ⏸️ = Hold")
    lines.append("")
    lines.append("=" * 80)
    lines.append("")
    
    # Detailed breakdown for each asset
    for _, row in summary_df.iterrows():
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"  {row['Name'].upper()} ({row['Asset']})")
        lines.append(f"  Data from: {row['Last_Date']}")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append(f"  ACTION:   {row['Action']}")
        lines.append(f"  TARGET:   {row['Target_Weight']*100:.0f}%  (was {row['Current_Weight']*100:.0f}%, change: {row['Weight_Change']*100:+.1f}pp)")
        lines.append("")
        lines.append(f"  On ${PORTFOLIO_VALUE:,.0f} portfolio:")
        lines.append(f"    Invested:  ${row['Invested_Dollars']:>10,.0f}  ({row['Target_Weight']*100:.0f}%)")
        lines.append(f"    Cash:      ${row['Cash_Dollars']:>10,.0f}  ({(1-row['Target_Weight'])*100:.0f}%)")
        
        if abs(row['Dollar_Change']) >= 100:
            direction = 'BUY ' if row['Dollar_Change'] > 0 else 'SELL'
            lines.append(f"    → {direction} ${abs(row['Dollar_Change']):>10,.0f}")
        else:
            lines.append(f"    → No trade needed")
        
        lines.append("")
        lines.append(f"  ZONE: {row['Zone']} {row['Zone_Icon']}  |  Danger: {row['Danger_Score']:.0f}/100")
        lines.append(f"  TREND: {row['Trend']}  |  V5B Score: {row['V5B_Score']:.3f}")
        lines.append("")
        lines.append("  BACKTEST METRICS:")
        lines.append(f"    Sharpe:       {row['Sharpe']:>8.2f}")
        lines.append(f"    CAGR:         {row['CAGR']:>7.1f}%")
        lines.append(f"    Max Drawdown: {row['Max_DD']:>7.1f}%")
        lines.append("")
    
    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    # Write to file
    txt_path = 'portfolio_signals.txt'
    with open(txt_path, 'w') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"✅ Saved text report to {txt_path}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        exit(1)
