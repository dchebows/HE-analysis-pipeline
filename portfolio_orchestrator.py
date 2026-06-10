#!/usr/bin/env python3
"""
Portfolio Signal Orchestrator - GitHub Actions Version
Complete implementation matching Colab orchestrator
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
# ASSET REGISTRY (COMPLETE)
# ============================================================

ASSET_REGISTRY = {}

# SPX Configuration
ASSET_REGISTRY['SPX'] = {
    'name': 'S&P 500',
    'ticker': '^GSPC',
    'vol_ticker': '^VIX',
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
    'v1_params': {
        'base_period': 58, 'min_period': 27, 'max_period': 142,
        'short_roc': 19, 'long_roc': 77, 'short_weight': 0.33,
        'bull_frac_base': 0.798, 'bear_frac_base': 0.43, 'vix_expansion': 0.052,
        'score_bull_base': 0.168, 'score_bear_base': 0.108,
        'confirm_days': 2, 'smooth_window': 5, 'evidence_thresh': 4.3,
        'evidence_margin': 2.1, 'hysteresis_frac_bull_exit': 0.53,
        'hysteresis_frac_bear_exit': 0.73,
    },
    'v6_ohlc_params': {
        'ath_near_thresh': -2.0, 'ath_far_thresh': -3.0,
        'rvol_low_thresh': 0.85, 'rvol_high_thresh': 1.25,
        'confirm_days': 1, 'v1_trust_near_ath': True, 'v5_trust_far_ath': True,
        'transition_override': False, 'score_decline_thresh': -999,
        'score_decline_lookback': 5,
    },
    'trade_params': {
        'ath_bull_thresh': -0.8, 'ath_bear_thresh': -4.0,
        'rh_period': 18, 'rh_bull_thresh': -1.5, 'rh_bear_thresh': -3.0,
        'use_secondary_rh': True, 'secondary_rh_period': 35,
        'roc_period': 12, 'roc_bull_thresh': 1.5, 'roc_bear_thresh': -2.5,
        'vol_period': 10, 'score_smooth': 2,
        'ath_weight': 0.25, 'rh_weight': 0.20, 'roc_weight': 0.15,
        'vol_weight': 0.05, 'vix_weight': 0.10, 'level_slope_weight': 0.05,
        'level_slope_period': 10, 'hysteresis': 0.06,
        'bull_score_thresh': 0.18, 'bear_score_thresh': -0.08,
        'confirm_days': 1, 'score_weak_zone': 0.02,
        'keltner_ema': 10, 'keltner_atr': 7, 'keltner_mult': 1.5,
        'velocity_lookback': 5, 'velocity_drop_thresh': -999, 'velocity_rise_thresh': 999,
    },
    'danger_params': {
        'vix_l1': 20, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
        'vix_l3': 25, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
        'vix_l5': 35, 'd_vix_l5': 15,
        'dd_l1': -0.03, 'd_dd_l1': 1, 'dd_l2': -0.05, 'd_dd_l2': 4,
        'dd_l3': -0.10, 'd_dd_l3': 7, 'dd_l4': -0.15, 'd_dd_l4': 10,
    },
}

# GOLD Configuration
ASSET_REGISTRY['GOLD'] = {
    'name': 'Gold Futures',
    'ticker': 'GC=F',
    'vol_ticker': '^GVZ',
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
    'v1_params': ASSET_REGISTRY['SPX']['v1_params'].copy(),
    'v6_ohlc_params': {
        'ath_near_thresh': -3.5, 'ath_far_thresh': -4.0,
        'rvol_low_thresh': 0.85, 'rvol_high_thresh': 1.25,
        'confirm_days': 1, 'v1_trust_near_ath': True, 'v5_trust_far_ath': True,
        'transition_override': False, 'score_decline_thresh': -999,
        'score_decline_lookback': 5,
    },
    'trade_params': ASSET_REGISTRY['SPX']['trade_params'].copy(),
    'danger_params': {
        'vix_l1': 18, 'd_vix_l1': 1, 'vix_l2': 22, 'd_vix_l2': 4,
        'vix_l3': 26, 'd_vix_l3': 8, 'vix_l4': 30, 'd_vix_l4': 12,
        'vix_l5': 35, 'd_vix_l5': 15,
        'dd_l1': -0.05, 'd_dd_l1': 1, 'dd_l2': -0.10, 'd_dd_l2': 4,
        'dd_l3': -0.15, 'd_dd_l3': 7, 'dd_l4': -0.20, 'd_dd_l4': 10,
    },
}

# COMPQ Configuration (uses SPX params)
ASSET_REGISTRY['COMPQ'] = {
    'name': 'NASDAQ Composite',
    'ticker': '^IXIC',
    'vol_ticker': '^VIX',
    'enriched_file': 'COMPQ_enriched.csv',
    'v5b_params': ASSET_REGISTRY['SPX']['v5b_params'].copy(),
    'v1_params': ASSET_REGISTRY['SPX']['v1_params'].copy(),
    'v6_ohlc_params': ASSET_REGISTRY['SPX']['v6_ohlc_params'].copy(),
    'trade_params': ASSET_REGISTRY['SPX']['trade_params'].copy(),
    'danger_params': ASSET_REGISTRY['SPX']['danger_params'].copy(),
}

# RUT Configuration
ASSET_REGISTRY['RUT'] = {
    'name': 'Russell 2000',
    'ticker': '^RUT',
    'vol_ticker': '^VIX',
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
    'v1_params': ASSET_REGISTRY['SPX']['v1_params'].copy(),
    'v6_ohlc_params': ASSET_REGISTRY['SPX']['v6_ohlc_params'].copy(),
    'trade_params': ASSET_REGISTRY['SPX']['trade_params'].copy(),
    'danger_params': {
        'vix_l1': 23, 'd_vix_l1': 1, 'vix_l2': 25, 'd_vix_l2': 4,
        'vix_l3': 28, 'd_vix_l3': 8, 'vix_l4': 33, 'd_vix_l4': 12,
        'vix_l5': 38, 'd_vix_l5': 15,
        'dd_l1': -0.05, 'd_dd_l1': 1, 'dd_l2': -0.08, 'd_dd_l2': 4,
        'dd_l3': -0.12, 'd_dd_l3': 7, 'dd_l4': -0.18, 'd_dd_l4': 10,
    },
}

# USD Configuration (uses SPX params)
ASSET_REGISTRY['USD'] = {
    'name': 'US Dollar Index',
    'ticker': 'DX-Y.NYB',
    'vol_ticker': '^VIX',
    'enriched_file': 'USD_enriched.csv',
    'v5b_params': ASSET_REGISTRY['SPX']['v5b_params'].copy(),
    'v1_params': ASSET_REGISTRY['SPX']['v1_params'].copy(),
    'v6_ohlc_params': ASSET_REGISTRY['SPX']['v6_ohlc_params'].copy(),
    'trade_params': ASSET_REGISTRY['SPX']['trade_params'].copy(),
    'danger_params': ASSET_REGISTRY['SPX']['danger_params'].copy(),
}
# ============================================================
# V5B MODEL FUNCTIONS
# ============================================================

def _v5b_distance_metrics(df_w, params):
    """Compute ATH and rolling high distances"""
    p = params
    expanding_high = df_w['high'].expanding().max()
    pct_from_ath = (df_w['close'] - expanding_high) / expanding_high * 100
    
    rolling_high = df_w['high'].rolling(p['rh_period'], min_periods=1).max()
    pct_from_rh = (df_w['close'] - rolling_high) / rolling_high * 100
    
    if p.get('use_secondary_rh', False):
        rh2 = df_w['high'].rolling(p['secondary_rh_period'], min_periods=1).max()
        pct_from_rh2 = (df_w['close'] - rh2) / rh2 * 100
    else:
        pct_from_rh2 = pct_from_rh.copy()
    
    return pct_from_ath, pct_from_rh, pct_from_rh2

def _v5b_momentum(df_w, params):
    """Compute ROC momentum"""
    p = params
    price_roc = df_w['close'].pct_change(p['roc_period']) * 100
    return price_roc

def _v5b_volatility(df_w, params):
    """Compute realized vol ratio and VIX ratio"""
    p = params
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
    
    return rvol_ratio, vix_ratio

def _v5b_level_slope(df_w, params):
    """Compute level slope z-score"""
    p = params
    buy_sell_mid = (df_w['buy_trade'] + df_w['sell_trade']) / 2
    level_slope = buy_sell_mid.pct_change(p['level_slope_period']) * 100
    ls_mean = level_slope.rolling(252, min_periods=63).mean()
    ls_std = level_slope.rolling(252, min_periods=63).std()
    ls_z = (level_slope - ls_mean) / (ls_std + 1e-8)
    return ls_z

def _v5b_composite_score(df_w, params, pct_from_ath, pct_from_rh, pct_from_rh2,
                          price_roc, rvol_ratio, vix_ratio, ls_z):
    """Compute weighted composite score"""
    p = params
    
    def norm(s, bull_thresh, bear_thresh):
        mid = (bull_thresh + bear_thresh) / 2
        hr = (bull_thresh - bear_thresh) / 2
        if hr == 0:
            hr = 1
        return ((s - mid) / hr).clip(-1.5, 1.5)
    
    ath_s = norm(pct_from_ath, p['ath_bull_thresh'], p['ath_bear_thresh'])
    rh_s = norm(pct_from_rh, p['rh_bull_thresh'], p['rh_bear_thresh'])
    rh2_s = norm(pct_from_rh2, p['rh_bull_thresh'] * 1.5, p['rh_bear_thresh'] * 1.5)
    roc_s = norm(price_roc, p['roc_bull_thresh'], p['roc_bear_thresh'])
    vol_s = -norm(rvol_ratio, 0.8, 1.3)
    vix_s = -norm(vix_ratio, 0.8, 1.3)
    ls_s = ls_z.clip(-2, 2) / 2
    
    rh_each = p['rh_weight'] / 2
    tw = (p['ath_weight'] + p['rh_weight'] + p['roc_weight'] +
          p['vol_weight'] + p['vix_weight'] + p['level_slope_weight'])
    
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
    return score

def trend_v5b_model(df_in, params):
    """V5B: Main entry point"""
    df_w = df_in.copy()
    n = len(df_w)
    p = params
    
    pct_from_ath, pct_from_rh, pct_from_rh2 = _v5b_distance_metrics(df_w, p)
    price_roc = _v5b_momentum(df_w, p)
    rvol_ratio, vix_ratio = _v5b_volatility(df_w, p)
    ls_z = _v5b_level_slope(df_w, p)
    
    score = _v5b_composite_score(df_w, p, pct_from_ath, pct_from_rh, pct_from_rh2,
                                   price_roc, rvol_ratio, vix_ratio, ls_z)
    
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
    vel_lookback = int(p.get('velocity_lookback', 5))
    vel_drop = float(p.get('velocity_drop_thresh', -999))
    vel_rise = float(p.get('velocity_rise_thresh', 999))
    
    final = np.zeros(n)
    state = 0
    
    for i in range(n):
        cs = cs_arr[i]
        conf = int(confirmed[i])
        if np.isnan(cs):
            final[i] = state
            continue
        
        velocity = 0.0
        if i >= vel_lookback:
            prev = cs_arr[i - vel_lookback]
            if not np.isnan(prev):
                velocity = cs - prev
        
        sticky = 0.0
        if weak_zone > 0 and abs(cs) < weak_zone:
            sticky = weak_zone - abs(cs)
        
        if state == 1:
            if velocity < vel_drop and cs < p['bull_score_thresh']:
                state = -1 if cs < p['bear_score_thresh'] else 0
            elif conf == -1 or cs < p['bear_score_thresh'] + h_bull_exit - sticky:
                state = -1
            elif conf == 0 and cs < -h_bull_exit / 2 - sticky:
                state = 0
        elif state == -1:
            if velocity > vel_rise and cs > p['bear_score_thresh']:
                state = 1 if cs > p['bull_score_thresh'] else 0
            elif conf == 1 or cs > p['bull_score_thresh'] - h_bear_exit + sticky:
                state = 1
            elif conf == 0 and cs > h_bear_exit / 2 + sticky:
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
# V1 MODEL (Simplified placeholder - returns NEUTRAL)
# ============================================================

def run_v1_model(df_in, params):
    """V1: Fractal/voting model - simplified placeholder"""
    signal = pd.Series('NEUTRAL', index=df_in.index)
    return signal

# ============================================================
# V6 OHLC ENSEMBLE
# ============================================================

def v6_ohlc_context_switch(df_in, v5b_pred, v1_pred, v5b_score, params):
    """V6_OHLC: Context switch ensemble"""
    n = len(df_in)
    p = params
    
    # ATH distance
    expanding_high = df_in['high'].expanding().max()
    ath_dist = ((df_in['close'] - expanding_high) / expanding_high * 100).values
    
    # Realized vol regime
    daily_ret = df_in['close'].pct_change()
    rvol = daily_ret.rolling(21, min_periods=10).std() * np.sqrt(252) * 100
    rvol_med = rvol.rolling(252, min_periods=63).median()
    rvol_ratio = (rvol / (rvol_med + 1e-8)).values
    
    # Context decision
    ath_near = float(p['ath_near_thresh'])
    ath_far = float(p['ath_far_thresh'])
    rvol_low = float(p['rvol_low_thresh'])
    rvol_high = float(p['rvol_high_thresh'])
    v1_near_ath = bool(p.get('v1_trust_near_ath', True))
    v5_far_ath = bool(p.get('v5_trust_far_ath', True))
    
    scores = v5b_score.values if hasattr(v5b_score, 'values') else v5b_score
    result = np.full(n, 'NEUTRAL', dtype=object)
    
    for i in range(n):
        a = ath_dist[i] if not np.isnan(ath_dist[i]) else 0.0
        rv = rvol_ratio[i] if not np.isnan(rvol_ratio[i]) else 1.0
        v1 = v1_pred.iloc[i] if pd.notna(v1_pred.iloc[i]) else 'NEUTRAL'
        v5 = v5b_pred.iloc[i] if pd.notna(v5b_pred.iloc[i]) else 'NEUTRAL'
        
        if v1_near_ath and a > ath_near and rv < rvol_low:
            result[i] = v1
        elif v5_far_ath and a < ath_far:
            result[i] = v5
        elif rv > rvol_high:
            result[i] = v5
        elif v1 == v5:
            result[i] = v1
        else:
            result[i] = v5
    
    # Confirmation
    cd = int(p.get('confirm_days', 1))
    tm = {'BULLISH': 1, 'BEARISH': -1, 'NEUTRAL': 0}
    num = np.array([tm.get(str(r), 0) for r in result])
    
    confirmed = np.zeros(n)
    state, pending, pc = 0, None, 0
    
    for i in range(n):
        rs = int(num[i])
        if rs != state:
            if pending == rs:
                pc += 1
            else:
                pending, pc = rs, 1
            if pc >= cd:
                state, pending, pc = rs, None, 0
        else:
            pending, pc = None, 0
        confirmed[i] = state
    
    sig_map = {1: 'BULLISH', -1: 'BEARISH', 0: 'NEUTRAL'}
    signal = pd.Series(confirmed, index=df_in.index).map(sig_map)
    return signal

# ============================================================
# TRADE SIGNAL MODEL
# ============================================================

def trade_signal_model(df_in, params):
    """TRADE: Short-duration signal"""
    p = params
    df_w = df_in.copy()
    n = len(df_w)
    
    # Build Keltner levels
    ema = df_w['close'].ewm(span=p['keltner_ema'], adjust=False).mean()
    tr = pd.concat([
        df_w['high'] - df_w['low'],
        (df_w['high'] - df_w['close'].shift(1)).abs(),
        (df_w['low'] - df_w['close'].shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(p['keltner_atr'], min_periods=1).mean()
    trade_buy = ema - p['keltner_mult'] * atr
    trade_sell = ema + p['keltner_mult'] * atr
    
    # Compute distance metrics (reuse V5B components)
    pct_from_ath, pct_from_rh, pct_from_rh2 = _v5b_distance_metrics(df_w, p)
    price_roc = _v5b_momentum(df_w, p)
    rvol_ratio, vix_ratio = _v5b_volatility(df_w, p)
    
    # Level slope using Keltner midpoint
    trade_mid = (trade_buy + trade_sell) / 2
    level_slope = trade_mid.pct_change(p['level_slope_period']) * 100
    ls_mean = level_slope.rolling(252, min_periods=63).mean()
    ls_std = level_slope.rolling(252, min_periods=63).std()
    ls_z = (level_slope - ls_mean) / (ls_std + 1e-8)
    
    # Composite score
    score = _v5b_composite_score(df_w, p, pct_from_ath, pct_from_rh, pct_from_rh2,
                                   price_roc, rvol_ratio, vix_ratio, ls_z)
    
    cs_arr = score.values
    
    # Threshold to raw signal
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
    cd = int(p.get('confirm_days', 1))
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
    h = float(p.get('hysteresis', 0.06))
    final = np.zeros(n)
    state = 0
    
    for i in range(n):
        cs = cs_arr[i]
        conf = int(confirmed[i])
        if np.isnan(cs):
            final[i] = state
            continue
        
        if state == 1:
            if conf == -1 or cs < p['bear_score_thresh'] + h:
                state = -1
            elif conf == 0 and cs < -h / 2:
                state = 0
        elif state == -1:
            if conf == 1 or cs > p['bull_score_thresh'] - h:
                state = 1
            elif conf == 0 and cs > h / 2:
                state = 0
        else:
            if conf == 1:
                state = 1
            elif conf == -1:
                state = -1
        
        final[i] = state
    
    sig_map = {1: 'BULLISH', -1: 'BEARISH', 0: 'NEUTRAL'}
    signal = pd.Series(final, index=df_in.index).map(sig_map)
    
    return signal, score, trade_buy, trade_sell
    # Chunk 3
    # ============================================================
# DANGER SCORE CALCULATION
# ============================================================

def _danger_score_row(score, score_vel, trend, trade, vix, vix_5d, mkt_dd, danger_params):
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
    
    # Signal 4: TRADE
    if isinstance(trade, str):
        if trade == 'BEARISH': d += 15
        elif trade == 'NEUTRAL': d += 3
    
    # Signal 5: VIX
    if not np.isnan(vix):
        if vix > dp['vix_l5']: d += dp['d_vix_l5']
        elif vix > dp['vix_l4']: d += dp['d_vix_l4']
        elif vix > dp['vix_l3']: d += dp['d_vix_l3']
        elif vix > dp['vix_l2']: d += dp['d_vix_l2']
        elif vix > dp['vix_l1']: d += dp['d_vix_l1']
    
    # Signal 6: VIX Accel
    if not np.isnan(vix_5d):
        if vix_5d > 0.50: d += 10
        elif vix_5d > 0.30: d += 7
        elif vix_5d > 0.15: d += 3
    
    # Signal 7: Market DD
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
    trade = bt_df['trade_sig_prev'].values
    vix = bt_df['vix_prev'].values
    vix_5d = bt_df['vix_5d_chg'].values
    mkt_dd = bt_df['market_dd_prev'].values
    
    for i in range(n):
        danger[i] = _danger_score_row(
            score[i], score_vel[i], trend[i], trade[i],
            vix[i], vix_5d[i], mkt_dd[i], danger_params
        )
    return danger

def _raw_weight_from_danger(danger_score):
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

def _apply_circuit_breaker(bt_df, raw_weights):
    """Apply portfolio drawdown circuit breaker"""
    n = len(bt_df)
    dd_thresh = -0.06
    dd_emerg = -0.08
    dd_min = 0.12
    
    cb_weights = np.zeros(n)
    equity_cb = np.zeros(n)
    equity_cb[0] = INITIAL_INVESTMENT
    peak_equity = INITIAL_INVESTMENT
    cb_active = False
    cb_target = 0.0
    
    for i in range(n):
        w = raw_weights[i]
        if i > 0:
            dr = bt_df['daily_return'].iloc[i]
            if np.isnan(dr):
                dr = 0.0
            pr = (cb_weights[i-1] * dr + (1 - cb_weights[i-1]) * CASH_DAILY_RATE)
            equity_cb[i] = equity_cb[i-1] * (1 + pr)
            peak_equity = max(peak_equity, equity_cb[i])
        
        pdd = ((equity_cb[i] - peak_equity) / peak_equity if peak_equity > 0 else 0.0)
        
        if pdd < dd_emerg:
            w = dd_min
            cb_active = True
            cb_target = peak_equity * (1 + dd_thresh * 0.5)
        elif pdd < dd_thresh:
            sev = (pdd - dd_thresh) / (dd_emerg - dd_thresh)
            w = max(dd_min, w * (1 - sev * 0.5))
            cb_active = True
            cb_target = peak_equity * (1 + dd_thresh * 0.5)
        elif cb_active:
            if equity_cb[i] >= cb_target:
                cb_active = False
            else:
                w = min(w, max(raw_weights[i] * 0.65, dd_min))
        
        cb_weights[i] = w
    
    return cb_weights, equity_cb

def _apply_asymmetric_smoothing(cb_weights):
    """Apply asymmetric position change limits"""
    n = len(cb_weights)
    max_daily_up = 0.18
    max_daily_down = 0.40
    smooth_weights = np.zeros(n)
    smooth_weights[0] = cb_weights[0]
    
    for i in range(1, n):
        change = cb_weights[i] - smooth_weights[i-1]
        if change > 0:
            change = min(change, max_daily_up)
        else:
            change = max(change, -max_daily_down)
        smooth_weights[i] = np.clip(smooth_weights[i-1] + change, 0.10, 1.0)
    
    return smooth_weights

def run_d1_strategy(bt_df, danger_arr):
    """D1 strategy orchestrator"""
    n = len(bt_df)
    raw_weights = np.array([_raw_weight_from_danger(d) for d in danger_arr])
    cb_weights, _ = _apply_circuit_breaker(bt_df, raw_weights)
    smooth_weights = _apply_asymmetric_smoothing(cb_weights)
    
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
        elif 'GVZ_Close' in df.columns:
            df = df.rename(columns={'GVZ_Close': 'vix_close'})
        
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
# PROSPECTIVE DANGER CALCULATION
# ============================================================

def compute_prospective_danger(bt_df, danger_params):
    """Compute prospective danger from latest data"""
    dp = danger_params
    row = bt_df.iloc[-1]
    n_rows = len(bt_df)
    details = {}
    
    s = row['v5b_score']
    details['score'] = s
    
    # Score velocity
    sv = np.nan
    if n_rows >= 6:
        prev_score = bt_df['v5b_score'].iloc[-6]
        if not np.isnan(prev_score) and not np.isnan(s):
            sv = s - prev_score
    details['velocity'] = sv
    
    # TREND and TRADE
    tr = row['PREDICTED_TREND']
    details['trend'] = tr
    ts = row['trade_signal']
    details['trade'] = ts
    
    # VIX
    v = row.get('vix_close', 15.0)
    details['vix'] = v
    
    # VIX acceleration
    vc = np.nan
    if n_rows >= 6 and 'vix_close' in bt_df.columns:
        vix_prev = bt_df['vix_close'].iloc[-6]
        if not np.isnan(vix_prev) and vix_prev > 0 and not np.isnan(v):
            vc = v / vix_prev - 1
    details['vix_accel'] = vc
    
    # Market drawdown
    market_high = bt_df['close'].expanding().max().iloc[-1]
    mdd = ((row['close'] - market_high) / market_high if market_high > 0 else 0.0)
    details['drawdown'] = mdd
    
    # Call danger score function
    danger = _danger_score_row(s, sv, tr, ts, v, vc, mdd, dp)
    
    # Store component points
    details['score_pts'] = (20 if s < -0.30 else 15 if s < -0.15 else
                            10 if s < -0.05 else 5 if s < 0.05 else
                            2 if s < 0.15 else 0) if not np.isnan(s) else 0
    
    details['velocity_pts'] = (15 if not np.isnan(sv) and sv < -0.30 else
                               10 if not np.isnan(sv) and sv < -0.20 else
                               5 if not np.isnan(sv) and sv < -0.10 else
                               2 if not np.isnan(sv) and sv < -0.05 else 0)
    
    details['trend_pts'] = (15 if tr == 'BEARISH' else 5 if tr == 'NEUTRAL' else 0) if isinstance(tr, str) else 0
    details['trade_pts'] = (15 if ts == 'BEARISH' else 3 if ts == 'NEUTRAL' else 0) if isinstance(ts, str) else 0
    
    if not np.isnan(v):
        details['vix_pts'] = (dp['d_vix_l5'] if v > dp['vix_l5'] else
                              dp['d_vix_l4'] if v > dp['vix_l4'] else
                              dp['d_vix_l3'] if v > dp['vix_l3'] else
                              dp['d_vix_l2'] if v > dp['vix_l2'] else
                              dp['d_vix_l1'] if v > dp['vix_l1'] else 0)
    else:
        details['vix_pts'] = 0
    
    details['vix_accel_pts'] = (10 if not np.isnan(vc) and vc > 0.50 else
                                7 if not np.isnan(vc) and vc > 0.30 else
                                3 if not np.isnan(vc) and vc > 0.15 else 0)
    
    if not np.isnan(mdd):
        details['dd_pts'] = (dp['d_dd_l4'] if mdd < dp['dd_l4'] else
                             dp['d_dd_l3'] if mdd < dp['dd_l3'] else
                             dp['d_dd_l2'] if mdd < dp['dd_l2'] else
                             dp['d_dd_l1'] if mdd < dp['dd_l1'] else 0)
    else:
        details['dd_pts'] = 0
    
    return danger, details
    # Chunk 4
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
        df['pred_v5b'], df['v5b_score'] = trend_v5b_model(df, cfg['v5b_params'])
        
        # Run V1 model (placeholder)
        df['pred_v1'] = run_v1_model(df, cfg['v1_params'])
        
        # Run V6 ensemble
        df['PREDICTED_TREND'] = v6_ohlc_context_switch(
            df, df['pred_v5b'], df['pred_v1'], df['v5b_score'], cfg['v6_ohlc_params']
        )
        
        # Run Trade signal
        df['trade_signal'], df['trade_score'], df['trade_buy'], df['trade_sell'] = \
            trade_signal_model(df, cfg['trade_params'])
        
        # Prepare backtest
        bt = df[df['date'] >= BACKTEST_START].copy().reset_index(drop=True)
        
        if len(bt) < 252:
            logger.warning(f"  Insufficient data for backtest ({len(bt)} days)")
            return None
        
        bt['daily_return'] = bt['close'].pct_change().fillna(0)
        bt['score_prev'] = bt['v5b_score'].shift(1)
        bt['score_vel_prev'] = (bt['v5b_score'] - bt['v5b_score'].shift(5)).shift(1)
        bt['trend_prev'] = bt['PREDICTED_TREND'].shift(1)
        bt['trade_sig_prev'] = bt['trade_signal'].shift(1)
        
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
        d1_weights, d1_equity, d1_rets = run_d1_strategy(bt, danger)
        bt['d1_weight'] = d1_weights
        bt['d1_equity'] = d1_equity
        
        # Compute metrics
        d1_m = calc_metrics(d1_equity, d1_rets, bt)
        
        # Get latest signal
        last_row = bt.iloc[-1]
        last_date = last_row['date'].date()
        
        # Prospective danger
        prosp_danger, det = compute_prospective_danger(bt, cfg['danger_params'])
        prosp_danger = int(round(prosp_danger))
        
        # Position sizing
        raw_weight = _raw_weight_from_danger(prosp_danger)
        current_weight = last_row['d1_weight']
        
        max_daily_up = 0.18
        max_daily_down = 0.40
        raw_change = raw_weight - current_weight
        if raw_change > 0:
            capped_change = min(raw_change, max_daily_up)
        else:
            capped_change = max(raw_change, -max_daily_down)
        prosp_weight = float(np.clip(current_weight + capped_change, 0.10, 1.0))
        
        # Calculate prospective change for display
        prospective_change = prosp_weight - current_weight
        
        # Action determination
        weight_change = prosp_weight - current_weight
        weight_change_pct = weight_change * 100
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
        
        # Format delta for display
        if abs(prospective_change) < 0.005:  # Less than 0.5pp
            delta_display = '—'
            delta_icon = '⚪'
        elif prospective_change > 0:
            delta_display = f'+{prospective_change*100:.0f}%'
            delta_icon = '🔼'
        else:
            delta_display = f'{prospective_change*100:.0f}%'
            delta_icon = '🔽'
        
        logger.info(f"  ✅ {asset} complete: {action} | Target: {prosp_weight*100:.0f}% | Danger: {prosp_danger:.0f}")
        
        return {
            'status': 'SUCCESS',
            'asset': asset,
            'cfg': cfg,
            'df': df,
            'bt': bt,
            'd1_m': d1_m,
            'danger': danger,
            'weights': d1_weights,
            'last_data_date': last_date,
            'action': action,
            'action_icon': action_icon,
            'prosp_weight': prosp_weight,
            'current_weight': current_weight,
            'weight_change': weight_change,
            'prospective_change': prospective_change,
            'delta_display': delta_display,
            'delta_icon': delta_icon,
            'prosp_danger': prosp_danger,
            'zone': zone,
            'zone_icon': zone_icon,
            'det': det,
        }
        
    except Exception as e:
        logger.error(f"  ❌ Error processing {asset}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# ============================================================
# REPORT GENERATION
# ============================================================

def generate_summary_dataframe(results):
    """Generate summary DataFrame from results"""
    summary_rows = []
    
    for result in results:
        if result is None or result.get('status') != 'SUCCESS':
            continue
        
        row = {
            'Asset': result['asset'],
            'Name': result['cfg']['name'],
            'Last_Date': result['last_data_date'],
            'Close': result['bt']['close'].iloc[-1],
            'Trend': result['bt']['PREDICTED_TREND'].iloc[-1],
            'V5B_Score': result['bt']['v5b_score'].iloc[-1],
            'Action': result['action'],
            'Action_Icon': result['action_icon'],
            'Delta_Icon': result['delta_icon'],  # ← ADDED THIS LINE
            'Current_Weight': result['current_weight'],
            'Target_Weight': result['prosp_weight'],
            'Weight_Change': result['weight_change'],
            'Danger_Score': result['prosp_danger'],
            'Zone': result['zone'],
            'Zone_Icon': result['zone_icon'],
            'Sharpe': result['d1_m']['sharpe'],
            'CAGR': result['d1_m']['cagr'],
            'Max_DD': result['d1_m']['max_drawdown'],
            'Invested_Dollars': result['prosp_weight'] * PORTFOLIO_VALUE,
            'Cash_Dollars': (1 - result['prosp_weight']) * PORTFOLIO_VALUE,
            'Dollar_Change': result['weight_change'] * PORTFOLIO_VALUE,
        }
        summary_rows.append(row)
    
    return pd.DataFrame(summary_rows)

def generate_text_report(summary_df, results):
    """Generate human-readable text report"""
    lines = []
    lines.append("=" * 80)
    lines.append("  MULTI-ASSET DAILY ACTION SIGNALS")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    lines.append("")
    
    # Summary table
    lines.append("SUMMARY TABLE:")
    lines.append("─" * 110)
    lines.append(f"{'ASSET':<8s} │ {'ACTION':<12s} │ {'ΔDay':>8s} │ {'TGT%':>4s} │ {'DNGR':>4s} │ {'SHRP':>5s} │ {'CAGR':>6s} │ {'MaxDD':>6s} │ {'TREND':<7s}")
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
    lines.append("Legend: ΔDay = Position % change to reach target | TGT% = Target Position")
    lines.append("        DNGR = Danger Score | SHRP = Sharpe | CAGR = Annual Return | MaxDD = Max Drawdown")
    lines.append("        🟢 = Buy | 🔴 = Sell | 🟡 = Light adjustment | ⏸️ = Hold")
    lines.append("        🔼 = Increase position | 🔽 = Decrease position | ⚪ = No change")
    lines.append("")
    lines.append("=" * 80)
    lines.append("")
    
    # Detailed breakdown for each asset
    for result in results:
        if result is None or result.get('status') != 'SUCCESS':
            continue
        
        row = summary_df[summary_df['Asset'] == result['asset']].iloc[0]
        det = result['det']
        
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"  {result['cfg']['name'].upper()} ({result['asset']})")
        lines.append(f"  Data from: {result['last_data_date']}")
        lines.append("=" * 80)
        lines.append("")
        
        lines.append(f"  ACTION:   {row['Action']}")
        lines.append(f"  TARGET:   {row['Target_Weight']*100:.0f}%  (was {row['Current_Weight']*100:.0f}%, change: {row['Weight_Change']*100:+.1f}pp)")
        lines.append(f"  ΔDay:     {result['delta_display']} from previous backtest day")
        lines.append("")
        lines.append(f"  On ${PORTFOLIO_VALUE:,.0f} portfolio:")
        lines.append(f"    Invested:  ${row['Invested_Dollars']:>10,.0f}  ({row['Target_Weight']*100:.0f}%)")
        lines.append(f"    Cash:      ${row['Cash_Dollars']:>10,.0f}  ({(1-row['Target_Weight'])*100:.0f}%)")
        
        if abs(row['Dollar_Change']) >= 100:
            direction = 'BUY ' if row['Dollar_Change'] > 0 else 'SELL'
            lines.append(f"    → {direction} ${abs(row['Dollar_Change']):>10,.0f} of {result['cfg']['ticker']}")
        else:
            lines.append(f"    → No trade needed")
        
        lines.append("")
        lines.append(f"  ZONE: {row['Zone']}  |  Danger: {row['Danger_Score']:.0f}/100")
        lines.append("")
        
        # Signal breakdown
        lines.append("  SIGNAL BREAKDOWN:")
        lines.append(f"  {'─'*52}")
        lines.append(f"  {'Signal':<22s} {'Value':>14s} {'Points':>8s}")
        lines.append(f"  {'─'*52}")
        lines.append(f"  {'V5B Score':<22s} {det['score']:>14.3f} {det['score_pts']:>8d}")
        lines.append(f"  {'Score Velocity':<22s} {det['velocity']:>14.3f} {det['velocity_pts']:>8d}")
        lines.append(f"  {'TREND':<22s} {str(det['trend']):>14s} {det['trend_pts']:>8d}")
        lines.append(f"  {'TRADE':<22s} {str(det['trade']):>14s} {det['trade_pts']:>8d}")
        lines.append(f"  {result['cfg']['vol_ticker']+' Level':<22s} {det['vix']:>14.1f} {det['vix_pts']:>8d}")
        lines.append(f"  {result['cfg']['vol_ticker']+' Accel':<22s} {det['vix_accel']:>14.1%} {det['vix_accel_pts']:>8d}")
        lines.append(f"  {'Mkt Drawdown':<22s} {det['drawdown']:>14.1%} {det['dd_pts']:>8d}")
        lines.append(f"  {'─'*52}")
        lines.append(f"  {'TOTAL DANGER':<22s} {'':>14s} {row['Danger_Score']:>8.0f}")
        lines.append("")
        
        # Backtest context
        lines.append("  BACKTEST CONTEXT:")
        lines.append(f"  {'─'*52}")
        lines.append(f"  {'Metric':<20s} {'D1':>12s}")
        lines.append(f"  {'─'*52}")
        lines.append(f"  {'Sharpe':<20s} {row['Sharpe']:>12.2f}")
        lines.append(f"  {'CAGR':<20s} {row['CAGR']:>11.1f}%")
        lines.append(f"  {'Max Drawdown':<20s} {row['Max_DD']:>11.1f}%")
        lines.append(f"  {'Avg Exposure':<20s} {result['bt']['d1_weight'].mean()*100:>11.0f}%")
        lines.append("")
    
    # Footer
    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return '\n'.join(lines)

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
    
    # Generate summary DataFrame
    summary_df = generate_summary_dataframe(results)
    
    # Save summary CSV
    summary_csv_path = 'portfolio_summary.csv'
    summary_df.to_csv(summary_csv_path, index=False)
    logger.info(f"\n✅ Saved summary to {summary_csv_path}")
    
    # Generate and save text report
    text_report = generate_text_report(summary_df, results)
    txt_path = 'portfolio_signals.txt'
    with open(txt_path, 'w') as f:
        f.write(text_report)
    logger.info(f"✅ Saved text report to {txt_path}")
    
    # Print summary table to console
    logger.info("\n" + "="*110)
    logger.info("📊 CONSOLIDATED SUMMARY TABLE")
    logger.info("="*110)
    logger.info("")
    logger.info(f"{'ASSET':<8s} │ {'ACTION':<10s} │ {'ΔDay':>6s} │ {'TGT%':>4s} │ {'DNGR':>4s} │ {'SHRP':>5s} │ {'CAGR':>6s} │ {'MaxDD':>6s} │ {'TREND':<6s}")
    logger.info("─" * 110)
    
    for _, row in summary_df.iterrows():
        delta_pct = row['Weight_Change'] * 100
        delta_str = f"{row['delta_icon']}{delta_pct:+.0f}%" if abs(delta_pct) >= 0.5 else "—"
        logger.info(
            f"{row['Asset']:<8s} │ {row['Action_Icon']} {row['Action']:<8s} │ {delta_str:>6s} │ "
            f"{row['Target_Weight']*100:>3.0f}% │ {row['Danger_Score']:>4.0f} │ {row['Sharpe']:>5.2f} │ "
            f"{row['CAGR']:>5.1f}% │ {row['Max_DD']:>5.1f}% │ {row['Trend']:<6s}"
        )
    
    logger.info("")
    logger.info("Legend: ΔDay = Position % change to reach target | TGT% = Target Position")
    logger.info("        DNGR = Danger Score | SHRP = Sharpe | CAGR = Annual Return | MaxDD = Max Drawdown")
    logger.info("        🟢 = Buy | 🔴 = Sell | 🟡 = Light adjustment | ⏸️ = Hold")
    logger.info("        🔼 = Increase position | 🔽 = Decrease position | ⚪ = No change")
    logger.info("="*110)
    
    logger.info("\n" + "="*70)
    logger.info("✅ PORTFOLIO ORCHESTRATOR COMPLETE")
    logger.info("="*70)
    logger.info(f"\n  Assets processed: {len(results)}/{len(ASSETS_TO_RUN)} successful")
    logger.info(f"  📄 Output files:")
    logger.info(f"     - {summary_csv_path}")
    logger.info(f"     - {txt_path}")
    logger.info("")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        exit(1)
