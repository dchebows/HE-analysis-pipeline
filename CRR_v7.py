#!/usr/bin/env python3
"""
Automated Daily Stock Analysis Script
Runs via GitHub Actions at 7pm EST/EDT (Mon-Fri only)
Outputs: output.csv, spx_gamma.json
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import requests
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CBOE OPTIONS CHAIN FUNCTIONS FOR SPX GAMMA
# ============================================================

def get_cboe_options_chain(symbol):
    """Fetch options chain from CBOE"""
    s = requests.Session()
    response = s.get(f'https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json')
    data = json.loads(response.content)
    s.close()
    quote = data['data']
    options = pd.DataFrame(quote['options'])
    quote.pop('options')

    options[['symbol', 'expiration_date', 'put_call', 'strike_price']] = options.option.str.extract(r'([A-Z]+)(\d{6})([CP])(\d+)')
    options['expiration_date'] = pd.to_datetime(options.expiration_date, yearfirst=True)

    for c in ['strike_price', 'open_interest', 'iv', 'gamma']:
        options[c] = pd.to_numeric(options[c])
    options['strike_price'] = options['strike_price'] / 1000
    snapshot_time = pd.to_datetime(data['timestamp'])
    options['days_to_expiration'] = np.busday_count(
        pd.Series(snapshot_time).dt.date.values.astype('datetime64[D]'),
        options['expiration_date'].dt.date.values.astype('datetime64[D]')) / 262

    return quote, options, snapshot_time


def _calcGammaExCall(S, K, iv, T, r, q, OI):
    """Calculate gamma exposure for calls"""
    d1 = (np.log(S / K) + T * (r - q + 0.5 * iv ** 2)) / (iv * np.sqrt(T))
    gamma = np.exp(-q * T) * norm.pdf(d1) / (S * iv * np.sqrt(T))
    return OI * 100 * S * S * 0.01 * gamma


def _isThirdFriday(d):
    """Check if date is third Friday of month"""
    return d.weekday() == 4 and 15 <= d.day <= 21


def _gamma_range(quote, from_range=0.8, to_range=1.2):
    """Calculate gamma range around spot"""
    spotPrice = quote['current_price']
    fromStrike = from_range * spotPrice
    toStrike = to_range * spotPrice
    return spotPrice, fromStrike, toStrike


def calculate_spx_gamma_metrics(symbol='_SPX'):
    """
    Calculate SPX gamma exposure, spot, and flip point
    Returns: dict with gamma, spot, flip, timestamp
    """
    print(f"📊 Fetching CBOE options chain for {symbol}...")
    
    try:
        quote, options, snapshot_time = get_cboe_options_chain(symbol)
        
        spotPrice, fromStrike, toStrike = _gamma_range(quote)
        levels = np.linspace(fromStrike, toStrike, 60)
        
        # For 0DTE options, set DTE = 1 day
        options.loc[options['days_to_expiration'] <= 0, 'days_to_expiration'] = 1/262
        
        totalGamma = []
        
        # Calculate gamma at each level
        df = options.copy()
        for level in levels:
            df_ = df[df.put_call == 'C']
            df.loc[df_.index, 'callGammaEx'] = _calcGammaExCall(
                level, df_.strike_price, df_.iv, df_.days_to_expiration, 0, 0, df_.open_interest
            )
            
            df_ = df[df.put_call == 'P']
            df.loc[df_.index, 'putGammaEx'] = _calcGammaExCall(
                level, df_.strike_price, df_.iv, df_.days_to_expiration, 0, 0, df_.open_interest
            )
            
            totalGamma.append(df.callGammaEx.sum() - df.putGammaEx.sum())
        
        # Convert to billions
        totalGamma = np.array(totalGamma) / 10 ** 9
        
        # Find Gamma Flip Point
        zeroCrossIdx = np.where(np.diff(np.sign(totalGamma)))[0]
        
        if len(zeroCrossIdx) > 0:
            negGamma = totalGamma[zeroCrossIdx]
            posGamma = totalGamma[zeroCrossIdx + 1]
            negStrike = levels[zeroCrossIdx]
            posStrike = levels[zeroCrossIdx + 1]
            
            zeroGamma = posStrike - ((posStrike - negStrike) * posGamma / (posGamma - negGamma))
            zeroGamma = float(zeroGamma[0])
        else:
            zeroGamma = float(spotPrice)
        
        # Calculate total gamma at spot
        spot_gamma = float(np.interp(spotPrice, levels, totalGamma))
        
        result = {
            'spx_gamma': round(spot_gamma, 2),
            'spx_spot': round(float(spotPrice), 2),
            'spx_flip': round(zeroGamma, 2),
            'timestamp': snapshot_time.strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol
        }
        
        print(f"✅ SPX Gamma Metrics:")
        print(f"   Spot: ${result['spx_spot']:,.2f}")
        print(f"   Gamma: ${result['spx_gamma']:.2f} Bn")
        print(f"   Flip: ${result['spx_flip']:,.2f}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error calculating SPX gamma: {e}")
        return {
            'spx_gamma': 0,
            'spx_spot': 0,
            'spx_flip': 0,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'error': str(e)
        }

def calculate_gamma_throttle_metrics(quote, options, spot_price, gamma_flip, total_gex_bn):
    """
    Calculate gamma throttle and related metrics for dashboard
    Returns: dict with throttle, regime, signals, key levels
    """
    print("📊 Calculating gamma throttle metrics...")
    
    try:
        # Download historical data for context
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        spx_hist = yf.download('^GSPC', start=start_date, end=end_date, progress=False)
        vix_hist = yf.download('^VIX', start=start_date, end=end_date, progress=False)
        
        # Handle multi-index columns from yfinance (flatten if needed)
        if isinstance(spx_hist.columns, pd.MultiIndex):
            spx_hist.columns = spx_hist.columns.get_level_values(0)
        if isinstance(vix_hist.columns, pd.MultiIndex):
            vix_hist.columns = vix_hist.columns.get_level_values(0)
        
        # Calculate 10-day realized volatility
        spx_hist['log_returns'] = np.log(spx_hist['Close'] / spx_hist['Close'].shift(1))
        spx_hist['RV_10'] = spx_hist['log_returns'].rolling(10).std() * np.sqrt(252) * 100
        
        # Extract scalar values properly
        current_rv_10 = float(spx_hist['RV_10'].iloc[-1])
        current_vix = float(vix_hist['Close'].iloc[-1])
        
        # Calculate throttle (calibrated formula)
        distance_from_flip_pct = (spot_price - gamma_flip) / spot_price * 100
        dealer_fraction = 0.15  # Adjust for dealer-relevant OI
        adjusted_gex = total_gex_bn * dealer_fraction
        
        if distance_from_flip_pct >= 0:
            # Positive gamma regime
            throttle = distance_from_flip_pct * 2 + adjusted_gex * 3
            throttle = min(throttle, 35)
        else:
            # Negative gamma regime
            throttle = distance_from_flip_pct * 3 - abs(adjusted_gex) * 5
            throttle = max(throttle, -100)
        
        # Determine regime
        if throttle > 20:
            regime = "STRONG POSITIVE GAMMA"
            regime_desc = "Dealers aggressively long gamma. Market pinned. Vol crushed."
            risk_level = "LOW"
            position_size = "100% of normal"
        elif throttle > 10:
            regime = "POSITIVE GAMMA"
            regime_desc = "Dealers moderately long gamma. Mean-reversion dominant."
            risk_level = "LOW-MODERATE"
            position_size = "75-100% of normal"
        elif throttle > 0:
            regime = "WEAK POSITIVE GAMMA"
            regime_desc = "Mild positive gamma. Some suppression but fragile."
            risk_level = "MODERATE"
            position_size = "50-75% of normal"
        elif throttle > -10:
            regime = "TRANSITION ZONE"
            regime_desc = "Gamma near neutral. Regime could flip. Elevated uncertainty."
            risk_level = "ELEVATED"
            position_size = "25-50% of normal"
        elif throttle > -30:
            regime = "NEGATIVE GAMMA"
            regime_desc = "Dealers short gamma. Moves amplified. Trending market."
            risk_level = "HIGH"
            position_size = "25% of normal or hedged"
        else:
            regime = "DEEP NEGATIVE GAMMA"
            regime_desc = "Extreme negative gamma. Crash/melt-up dynamics possible."
            risk_level = "EXTREME"
            position_size = "Flat or fully hedged"
        
        # Volatility signal
        vix_rv_spread = current_vix - current_rv_10
        if throttle > 10 and vix_rv_spread > 5:
            vol_signal = "SELL VOLATILITY"
        elif throttle > 10:
            vol_signal = "NEUTRAL (Vol fairly priced)"
        elif -10 <= throttle <= 10:
            vol_signal = "CAUTION - REDUCE EXPOSURE"
        else:
            vol_signal = "BUY VOLATILITY / TREND FOLLOW"
        
        # Directional signal
        if throttle > 10:
            if distance_from_flip_pct > 3:
                dir_signal = "BULLISH BIAS (strong support from gamma)"
            else:
                dir_signal = "NEUTRAL-BULLISH (close to flip)"
        elif throttle < -10:
            dir_signal = "FOLLOW THE TREND"
        else:
            dir_signal = "NO CLEAR DIRECTION"
        
        # Key levels
        key_levels = {
            'gamma_flip': round(gamma_flip, 0),
            'put_wall': round(gamma_flip * 0.97, 0),
            'call_wall': round(spot_price * 1.03, 0),
            'danger_zone': round(gamma_flip * 0.95, 0)
        }
        
        result = {
            'gamma_throttle': round(throttle, 2),
            'rv_10day': round(current_rv_10, 2),
            'vix': round(current_vix, 2),
            'dist_to_flip_pct': round(distance_from_flip_pct, 2),
            'regime': regime,
            'regime_description': regime_desc,
            'risk_level': risk_level,
            'position_size': position_size,
            'vol_signal': vol_signal,
            'dir_signal': dir_signal,
            'key_levels': key_levels
        }
        
        print(f"✅ Throttle: {throttle:.2f} | Regime: {regime}")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating throttle: {e}")
        return {
            'gamma_throttle': 0,
            'rv_10day': 0,
            'vix': 0,
            'dist_to_flip_pct': 0,
            'regime': 'UNKNOWN',
            'regime_description': 'Error calculating metrics',
            'risk_level': 'UNKNOWN',
            'position_size': 'Unknown',
            'vol_signal': 'Unknown',
            'dir_signal': 'Unknown',
            'key_levels': {}
        }

# ============================================================
# DYNAMIC DATE CALCULATION
# ============================================================
# Today's date (GitHub Actions runs in UTC, adjust if needed)
today = datetime.now()
end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')  # Yahoo Finance needs +1 day
start_date = (today - timedelta(days=500)).strftime('%Y-%m-%d')  # 🔧 500 days = ~365 trading days

print(f"📅 Fetching data from {start_date} to {end_date}")

# ============================================================
# TICKER CONFIGURATION
# ============================================================
tickers = ['^TNX', '^GSPC', '^IXIC', '^RUT', '^VIX', '^NYICDX', 
           'AAAU', 'AAPL', 'IBIT', 'QQQ', 'GLD', 'SLV', 'NVDA']

# ============================================================
# DOWNLOAD DATA - 🔧 FIXED DATA DOWNLOAD
# ============================================================
print("📊 Downloading current data...")
# 🔧 FIX: Download without group_by to get consistent format
StkData = yf.download(tickers, start=start_date, end=end_date, progress=False)

# 🔧 FIX: Handle yfinance column structure
if len(tickers) == 1:
    # Single ticker - columns are simple
    print("   ℹ️  Single ticker mode")
    StkData.reset_index(inplace=True)
else:
    # Multiple tickers - columns are MultiIndex
    print("   ℹ️  Multiple ticker mode - handling MultiIndex")
    StkData.reset_index(inplace=True)

# Ensure Date column exists
if 'Date' not in StkData.columns:
    if 'index' in StkData.columns:
        StkData = StkData.rename(columns={'index': 'Date'})

print(f"   📅 Date range: {StkData['Date'].min()} to {StkData['Date'].max()}")
print(f"   📊 Data shape: {StkData.shape} (rows x columns)")
print(f"   📊 Total trading days: {len(StkData)}")

# 🔧 NEW: Download ATH data separately
print("\n📈 Downloading all-time high data...")
max_close_prices = {}
for ticker in tickers:
    try:
        ath_data = yf.download(ticker, period='max', progress=False, auto_adjust=False)
        if not ath_data.empty:
            if isinstance(ath_data['Adj Close'], pd.Series):
                max_close_prices[ticker] = ath_data['Adj Close'].max()
            else:
                max_close_prices[ticker] = ath_data['Adj Close'].iloc[:, 0].max()
        else:
            max_close_prices[ticker] = None
    except Exception as e:
        print(f"   ⚠️  Could not get ATH for {ticker}: {e}")
        max_close_prices[ticker] = None

print("✅ Data download complete\n")

# ============================================================
# CALCULATE SPX GAMMA METRICS
# ============================================================
print("🎯 Calculating SPX Gamma Exposure...")
spx_metrics = calculate_spx_gamma_metrics('_SPX')

# If gamma calculation was successful, add throttle metrics
if 'error' not in spx_metrics:
    # Re-fetch options data for throttle calculation
    quote, options, snapshot_time = get_cboe_options_chain('_SPX')
    
    # Calculate throttle metrics
    throttle_metrics = calculate_gamma_throttle_metrics(
        quote=quote,
        options=options,
        spot_price=spx_metrics['spx_spot'],
        gamma_flip=spx_metrics['spx_flip'],
        total_gex_bn=spx_metrics['spx_gamma']
    )
    
    # Merge throttle metrics into spx_metrics
    spx_metrics.update(throttle_metrics)

# Save to JSON file for Streamlit dashboard
with open('spx_gamma.json', 'w') as f:
    json.dump(spx_metrics, f, indent=2)
print(f"💾 SPX gamma data saved to spx_gamma.json\n")

# Save daily throttle history for charting
if 'gamma_throttle' in spx_metrics and spx_metrics['gamma_throttle'] != 0:
    history_file = 'throttle_history.csv'
    
    # Create new row
    new_row = pd.DataFrame({
        'date': [spx_metrics['timestamp']],
        'throttle': [spx_metrics['gamma_throttle']],
        'rv_10': [spx_metrics['rv_10day']],
        'spot': [spx_metrics['spx_spot']],
        'flip': [spx_metrics['spx_flip']],
        'regime': [spx_metrics['regime']]
    })
    
    # Append to history (or create if doesn't exist)
    try:
        if pd.io.common.file_exists(history_file):
            history = pd.read_csv(history_file)
            # Don't duplicate today's entry
            history['date'] = pd.to_datetime(history['date'])
            new_row['date'] = pd.to_datetime(new_row['date'])
            if new_row['date'].iloc[0] not in history['date'].values:
                history = pd.concat([history, new_row], ignore_index=True)
                history.to_csv(history_file, index=False)
                print(f"✅ Throttle history updated: {len(history)} days")
            else:
                print(f"ℹ️  Today's throttle data already in history")
        else:
            new_row.to_csv(history_file, index=False)
            print(f"✅ Created throttle history file")
    except Exception as e:
        print(f"⚠️  Could not update throttle history: {e}")

print(f"💾 SPX gamma data saved to spx_gamma.json\n")

# ============================================================
# INITIALIZE LOOP VARIABLES
# ============================================================
data = pd.DataFrame()
summaryList = []
rowList = []

# ============================================================
# SIGNAL STRENGTH CONFIGURATION
# ============================================================
current_quad = 'Quad2'  # Manual input: Quad1, Quad2, Quad3, Quad4

def calculate_signal_strength(trade, trend, trade_chg, trend_chg,
                               close, lrr, trr, upper_band, lower_band,
                               ath_value, rsi, rvol_1m, rvol_3m,
                               vix, vix_ma, vix_roc_ma, vol_roc_ma,
                               chg_1d, chg_1w, chg_1m, chg_3m,
                               volume_1d, volume_1w):
    """
    Calculate composite Signal Strength Score (-100 to +100)
    Based on Rate of Change of PRICE, VOLUME, and VOLATILITY.

    Returns: (ss_score, ss_status, ss_action, warning_level, warning_flags)
    """

    # ============================================================
    # LAYER 1: TREND ALIGNMENT (max ±30 points)
    # ============================================================
    trend_alignment = {
        ('Bullish', 'Bullish'):   30,
        ('Bullish', 'Neutral'):   15,
        ('Neutral', 'Bullish'):   10,
        ('Neutral', 'Neutral'):    0,
        ('Bearish', 'Bullish'):   -5,
        ('Bullish', 'Bearish'):  -10,
        ('Bearish', 'Neutral'):  -15,
        ('Neutral', 'Bearish'):  -20,
        ('Bearish', 'Bearish'):  -30,
    }

    layer1_score = trend_alignment.get((trade, trend), 0)

    # ============================================================
    # LAYER 2: RISK RANGE POSITION (max ±25 points)
    # ============================================================
    layer2_score = 0

    if trr > lrr and (trr - lrr) > 0:
        range_width = trr - lrr
        position_in_range = (close - lrr) / range_width
        position_in_range = max(-0.5, min(1.5, position_in_range))

        if close <= lrr:
            if trend == 'Bullish' or trade == 'Bullish':
                layer2_score = 25
            elif trend == 'Bearish' and trade == 'Bearish':
                layer2_score = -25
            else:
                layer2_score = 5

        elif close >= trr:
            if upper_band == 'HATH':
                layer2_score = 15
            elif upper_band == 'HH':
                layer2_score = 10
            elif trend == 'Bearish':
                layer2_score = -5
            else:
                layer2_score = -10

        elif position_in_range <= 0.25:
            if trade == 'Bullish' or trend == 'Bullish':
                layer2_score = 18
            else:
                layer2_score = 0

        elif position_in_range <= 0.50:
            if trade == 'Bullish' and trend == 'Bullish':
                layer2_score = 10
            else:
                layer2_score = 2

        elif position_in_range <= 0.75:
            layer2_score = -3

        else:
            layer2_score = -8

    # ============================================================
    # LAYER 3: BAND PATTERN (max ±20 points)
    # ============================================================
    band_scores = {
        ('HATH', 'HL'):       20,
        ('HH', 'HL'):         15,
        ('HATH', 'Brownian'): 14,
        ('HH', 'Brownian'):   10,
        ('Brownian', 'HL'):    5,
        ('HATH', 'LL'):        3,
        ('HH', 'LL'):         -2,
        ('Brownian', 'Brownian'): 0,
        ('LH', 'HL'):         -3,
        ('LH', 'Brownian'):   -8,
        ('Brownian', 'LL'):  -12,
        ('LH', 'LL'):        -20,
    }

    layer3_score = band_scores.get((upper_band, lower_band), 0)

    # ============================================================
    # LAYER 4: VOLATILITY REGIME (max ±15 points)
    # ============================================================
    if vix < 15:
        vix_bucket_score = 6
    elif vix < 20:
        vix_bucket_score = 4
    elif vix < 25:
        vix_bucket_score = 0
    elif vix < 30:
        vix_bucket_score = -3
    else:
        vix_bucket_score = -6

    if rvol_1m > 0 and rvol_3m > 0:
        rvol_ratio = rvol_1m / rvol_3m
        if rvol_ratio < 0.90:
            rvol_score = 5
        elif rvol_ratio < 0.95:
            rvol_score = 3
        elif rvol_ratio <= 1.05:
            rvol_score = 0
        elif rvol_ratio <= 1.10:
            rvol_score = -3
        else:
            rvol_score = -5
    else:
        rvol_score = 0

    if vix_roc_ma < 0.04:
        vix_roc_score = 4
    elif vix_roc_ma < 0.06:
        vix_roc_score = 2
    elif vix_roc_ma < 0.08:
        vix_roc_score = 0
    elif vix_roc_ma < 0.12:
        vix_roc_score = -2
    else:
        vix_roc_score = -4

    layer4_score = vix_bucket_score + rvol_score + vix_roc_score

    # ============================================================
    # LAYER 5: MOMENTUM CONFIRMATION (max ±10 points)
    # ============================================================
    layer5_score = 0

    pos_count = sum([1 for x in [chg_1w, chg_1m, chg_3m] if x is not None and x > 0])
    neg_count = sum([1 for x in [chg_1w, chg_1m, chg_3m] if x is not None and x < 0])

    if pos_count == 3:
        layer5_score += 5
    elif neg_count == 3:
        layer5_score -= 5
    elif pos_count == 2:
        layer5_score += 2
    elif neg_count == 2:
        layer5_score -= 2

    if rsi is not None:
        if 50 <= rsi <= 65:
            layer5_score += 5
        elif 40 <= rsi < 50:
            if trend == 'Bullish':
                layer5_score += 3
            else:
                layer5_score -= 1
        elif 65 < rsi <= 70:
            layer5_score += 2
        elif rsi > 70:
            layer5_score -= 3
        elif 30 <= rsi < 40:
            if trend == 'Bullish':
                layer5_score += 2
            else:
                layer5_score -= 3
        elif rsi < 30:
            if trend == 'Bullish':
                layer5_score += 3
            else:
                layer5_score -= 5

    layer5_score = max(-10, min(10, layer5_score))

    # ============================================================
    # COMPOSITE SCORE
    # ============================================================
    raw_score = layer1_score + layer2_score + layer3_score + layer4_score + layer5_score
    ss_score = max(-100, min(100, raw_score))

    # ============================================================
    # WARNING FLAGS
    # ============================================================
    warnings = []

    if trade_chg == '⚠':
        warnings.append('Trade Flip')

    if trend_chg == '⚠':
        warnings.append('Trend Flip')

    if vix_roc_ma is not None and vix_ma is not None:
        if vix_roc_ma > 0.08 and vix_ma >= 15:
            warnings.append('VIX Spike')

    if vol_roc_ma is not None and vol_roc_ma > 0.27:
        warnings.append('Vol Spike')

    if rsi is not None and (rsi > 70 or rsi < 30):
        warnings.append('RSI Extreme')

    if rvol_1m > 0 and rvol_3m > 0 and rvol_1m > rvol_3m * 1.10:
        warnings.append('RVOL Cross')

    if chg_1d is not None and abs(chg_1d) > 2.0:
        warnings.append('Big Move')

    warning_level = min(3, len(warnings))
    warning_flags = ', '.join(warnings) if warnings else 'None'

    # ============================================================
    # STATUS DETERMINATION
    # ============================================================
    is_bullish = (trade == 'Bullish' or trend == 'Bullish')
    is_bearish = (trade == 'Bearish' and trend == 'Bearish')
    is_neutral = not is_bullish and not is_bearish

    if is_bullish:
        if warning_level >= 3:
            ss_status = '🔴 BULL DANGER'
            ss_action = 'Breakdown likely — prepare to exit'
        elif warning_level == 2:
            ss_status = '🟠 BULL CAUTION'
            ss_action = 'Multiple warnings — stop buying, tighten stops'
        elif warning_level == 1:
            if ss_score >= 60:
                ss_status = '🟡 BULL WATCH'
                ss_action = 'Strong but warning active — reduce aggression'
            else:
                ss_status = '🟡 BULL WATCH'
                ss_action = 'Early stress — reduce aggression, stop adding'
        else:
            if ss_score >= 80:
                ss_status = '🟢 MAX BULL'
                ss_action = 'Full conviction — add on dips to LRR'
            elif ss_score >= 60:
                ss_status = '✅ STRONG BULL'
                ss_action = 'Normal positioning — buy dips 50-100bps'
            elif ss_score >= 40:
                ss_status = '✅ BULL INTACT'
                ss_action = 'Hold, buy only at LRR'
            elif ss_score >= 20:
                ss_status = '✅ ALL CLEAR'
                ss_action = 'Bull intact — maintain position'
            else:
                ss_status = '⬜ WEAK BULL'
                ss_action = 'Marginal — hold small, do not add'

    elif is_bearish:
        recovery_signals = 0
        if layer3_score > 0:
            recovery_signals += 1
        if layer4_score > 0:
            recovery_signals += 1
        if layer5_score > 0:
            recovery_signals += 1
        if upper_band in ['HH', 'HATH']:
            recovery_signals += 1
        if lower_band == 'HL':
            recovery_signals += 1

        recovery_score = recovery_signals * 20

        if recovery_score >= 60:
            ss_status = '🟢 RECOVERY IMMINENT'
            ss_action = 'Strong convergence — prepare to cover shorts'
        elif recovery_score >= 40:
            ss_status = '🟡 RECOVERY LIKELY'
            ss_action = 'Multiple recovery signals — stop adding shorts'
        elif recovery_score >= 20:
            ss_status = '🟠 RECOVERY WATCH'
            ss_action = 'Early recovery signs — monitor daily'
        else:
            if ss_score <= -80:
                ss_status = '🔴 MAX BEAR'
                ss_action = 'Full short conviction — add on rips to TRR'
            elif ss_score <= -60:
                ss_status = '🔴 STRONG BEAR'
                ss_action = 'Short positioning — sell rallies'
            elif ss_score <= -40:
                ss_status = '🔴 BEAR INTACT'
                ss_action = 'No recovery signals — stay out or short'
            else:
                ss_status = '🔴 BEAR HOLD'
                ss_action = 'Bearish but weakening — hold short, watch closely'

    else:
        if ss_score > 20:
            ss_status = '🟡 LEANING BULL'
            ss_action = 'Watch for TRADE confirm — prepare to buy'
        elif ss_score < -20:
            ss_status = '🟡 LEANING BEAR'
            ss_action = 'Watch for breakdown — prepare to short/exit'
        else:
            if warning_level >= 2:
                ss_status = '⚪ NEUTRAL STRESSED'
                ss_action = 'No signal + warnings — stay flat, capital preservation'
            else:
                ss_status = '⚪ NEUTRAL'
                ss_action = 'No directional signal — stay flat'

    return ss_score, ss_status, ss_action, warning_level, warning_flags

# ============================================================
# MAIN PROCESSING LOOP - 🔧 COMPLETELY REWRITTEN
# ============================================================
print("🔄 Processing tickers...\n")

for x in tickers:
    print(f"{'='*60}")
    print(f"🔍 Processing: {x}")
    print(f"{'='*60}")
    
    try:
        # 🔧 FIX: Create a completely clean DataFrame with reset index
        ticker_data = pd.DataFrame()
        
        # Extract Close and Volume for this ticker
        if isinstance(StkData['Close'], pd.DataFrame):
            # MultiIndex format (multiple tickers)
            ticker_data['Close'] = StkData['Close'][x].values  # 🔧 Use .values to avoid index issues
            ticker_data['Volume'] = StkData['Volume'][x].values
            ticker_data['VIX'] = StkData['Close']['^VIX'].values
            ticker_data['SP_Volume'] = StkData['Volume']['^GSPC'].values
            ticker_data['Date'] = StkData['Date'].values
        else:
            # Single ticker format (shouldn't happen with multiple tickers)
            ticker_data['Close'] = StkData['Close'].values
            ticker_data['Volume'] = StkData['Volume'].values
            ticker_data['VIX'] = StkData['Close'].values
            ticker_data['SP_Volume'] = StkData['Volume'].values
            ticker_data['Date'] = StkData['Date'].values
        
        # 🔧 CRITICAL: Remove any NaN rows from Close prices
        ticker_data = ticker_data.dropna(subset=['Close']).reset_index(drop=True)
        
        # Now work with the clean ticker_data DataFrame
        data = ticker_data.copy()
        
        # Check if we have valid data
        non_null_count = len(data)
        print(f"   ✅ Loaded {non_null_count} valid data points")
        
        if non_null_count < 63:  # Minimum for 3M calculations
            print(f"   ⚠️  Insufficient data ({non_null_count} days), skipping...")
            continue
        
        # 🔧 FIX: Weighted Moving Average
        WeightList = [.5, .5, 2, 3, 4, 5, 6]
        weights = np.array(WeightList)
        wma7 = data['Close'].rolling(7).apply(lambda prices: np.dot(prices, weights)/weights.sum(), raw=True)
        data['WMA7'] = wma7.round(3)
        data['SMA7'] = data['Close'].rolling(9).mean()

        # 🔧 FIX: Beta Calculation with proper SP500 data
        data['Stock_Returns'] = data['Close'].pct_change()
        
        # Get S&P 500 returns properly
        if isinstance(StkData['Close'], pd.DataFrame) and '^GSPC' in StkData['Close'].columns:
            sp500_close = StkData['Close']['^GSPC'].values
            # Align with current data length
            if len(sp500_close) > len(data):
                sp500_close = sp500_close[-len(data):]
            sp500_series = pd.Series(sp500_close, index=data.index)
        else:
            sp500_series = data['Close'].copy()
        
        data['SP500_Returns'] = sp500_series.pct_change()
        
        # Only calculate Beta if we have enough data
        if non_null_count >= 252:
            # Calculate rolling covariance and variance manually
            # Beta = Cov(Stock, Market) / Var(Market)
            
            # Create a combined dataframe for rolling calculation
            returns_df = pd.DataFrame({
                'stock': data['Stock_Returns'],
                'market': data['SP500_Returns']
            })
            
            # Calculate rolling covariance between stock and market
            rolling_cov = returns_df['stock'].rolling(window=252).cov(returns_df['market'])
            
            # Calculate rolling variance of market
            rolling_var = returns_df['market'].rolling(window=252).var()
            
            # Beta = Covariance / Variance
            data['Beta_1Y'] = rolling_cov / rolling_var
            
            # Check if Beta was actually calculated
            beta_value = data['Beta_1Y'].iloc[-1]
            if pd.notna(beta_value):
                print(f"   ✅ Beta calculated: {beta_value:.3f}")
            else:
                print(f"   ⚠️  Beta calculation returned NaN")
        else:
            data['Beta_1Y'] = np.nan
            print(f"   ⚠️  Beta skipped ({non_null_count} < 252 days)")

        # Standard Deviation
        data['STD_DEV'] = data['Close'].rolling(7).std()

        # Risk Range Calculation
        sigma_u = 1.4
        sigma_l = 1.8
        data['UPPER'] = data['WMA7'] + (data['STD_DEV'] * sigma_u)
        data['LOWER'] = data['SMA7'] - (data['STD_DEV'] * sigma_l)

        # VIX Calculations
        data['VIX_MA'] = data['VIX'].rolling(2).mean()
        data['VIX_ROC'] = data['VIX'].pct_change().abs()
        data['VIX_ROC_MA'] = data['VIX_ROC'].rolling(2).mean()

        # Volume Calculations
        data['VOL'] = data['SP_Volume'] / 10
        data['VOL_MA'] = data['VOL'].rolling(7).mean()
        data['VOL_ROC'] = data['VOL'].pct_change().abs()
        data['VOL_ROC_MA'] = data['VOL_ROC'].rolling(2).mean()

        # Final Risk Range with VIX/Volume Adjustment
        conditions_u = [(data['VIX_ROC_MA'] > 0.08) & (data['VIX_MA'] >= 15) & (data['VOL_ROC_MA'] > 0.27), 
                        (data['VIX_MA'].notna())]
        choices_u = [data['UPPER'] * .9875, data['UPPER']]
        data['TOP_END'] = np.select(conditions_u, choices_u, default=data['UPPER']).round(2)

        conditions_l = [(data['VIX_ROC_MA'] > 0.08) & (data['VIX_MA'] >= 15) & (data['VOL_ROC_MA'] > 0.27), 
                        (data['VIX_MA'].notna())]
        choices_l = [data['LOWER'] * .99, data['LOWER']]
        data['BOTTOM_END'] = np.select(conditions_l, choices_l, default=data['LOWER']).round(2)

        data['DOWN_PCT'] = (((data['LOWER'] - data['Close']) / data['Close']) * 100).round(2)
        data['UP_PCT'] = (((data['UPPER'] - data['Close']) / data['Close']) * 100).round(2)
        
        # 🔧 DEBUG: Check if risk range was calculated
        last_top = data['TOP_END'].iloc[-1] if len(data) > 0 else None
        last_bottom = data['BOTTOM_END'].iloc[-1] if len(data) > 0 else None
        print(f"   Risk Range: Bottom={last_bottom}, Top={last_top}")
        
        # Trade and Trend Levels
        data['Trade_Level'] = data['Close'].shift(periods=15).round(2)
        data['Trend_Level'] = data['Close'].shift(periods=62).round(2)
        
        condlist1 = [data['Trade_Level'] < data['Close'], data['Trade_Level'] > data['Close']]
        condlist = [data['Trend_Level'] < data['Close'], data['Trend_Level'] > data['Close']]
        choicelist = ['Bullish', 'Bearish']
        
        data['Trade'] = np.select(condlist1, choicelist, 'Neutral')
        data['Trend'] = np.select(condlist, choicelist, 'Neutral')

        # Change Indicators
        data['Trade_Change'] = np.where(data['Trade'] != data['Trade'].shift(1), '⚠', '')
        data['Trend_Change'] = np.where(data['Trend'] != data['Trend'].shift(1), '⚠', '')

        # Price Changes
        data['change_1D'] = data['Close'].pct_change(periods=1).round(4) * 100
        data['1W_change'] = data['Close'].pct_change(periods=5).round(4) * 100
        data['1M_change'] = data['Close'].pct_change(periods=21).round(4) * 100
        data['3M_change'] = data['Close'].pct_change(periods=63).round(4) * 100
        
        # Volatility Calculations
        data['30D_sd'] = data['change_1D'].rolling(21).std()
        data['90D_sd'] = data['change_1D'].rolling(63).std()
        data['Vlty'] = data['30D_sd'] * 15.87450786638754
        data['Vlty_3m'] = np.maximum(0, data['90D_sd'] * (252**0.5))

        # 🔧 DEBUG: Check volatility calculations
        last_rvol_1m = data['Vlty'].iloc[-1] if len(data) > 0 else None
        last_rvol_3m = data['Vlty_3m'].iloc[-1] if len(data) > 0 else None
        print(f"   RVOL: 1M={last_rvol_1m}, 3M={last_rvol_3m}")

        # Band Analysis
        if len(data) >= 63:
            data['H_TRR'] = data['UPPER'].iloc[-63:-2].max()
            data['L_TRR'] = data['UPPER'].iloc[-63:-2].min()
            data['H_LRR'] = data['LOWER'].iloc[-63:-2].max()
            data['L_LRR'] = data['LOWER'].iloc[-63:-2].min()
            data['C_TRR'] = data['UPPER'].iloc[-1]
            data['C_LRR'] = data['LOWER'].iloc[-1]
        else:
            data['H_TRR'] = data['UPPER'].max()
            data['L_TRR'] = data['UPPER'].min()
            data['H_LRR'] = data['LOWER'].max()
            data['L_LRR'] = data['LOWER'].min()
            data['C_TRR'] = data['UPPER'].iloc[-1]
            data['C_LRR'] = data['LOWER'].iloc[-1]

        # Get ATH value
        ath_value = max_close_prices.get(x, None)

        # Upper Band Logic with HATH Detection
        if ath_value is not None and not pd.isna(ath_value):
            condlist_high = [
                data['C_TRR'] > ath_value,
                np.logical_and(data['C_TRR'] > data['H_TRR'], data['C_TRR'] <= ath_value),
                data['C_TRR'] < data['L_TRR'],
                np.logical_and(data['C_TRR'] <= data['H_TRR'], data['C_TRR'] >= data['L_TRR'])
            ]
            choice_high = ['HATH', 'HH', 'LH', 'Brownian']
        else:
            condlist_high = [
                data['C_TRR'] > data['H_TRR'],
                data['C_TRR'] < data['L_TRR'],
                np.logical_and(data['C_TRR'] <= data['H_TRR'], data['C_TRR'] >= data['L_TRR'])
            ]
            choice_high = ['HH', 'LH', 'Brownian']

        data['Upper Band'] = np.select(condlist_high, choice_high, 'Brownian')
        data['HATH_Flag'] = np.where(data['Upper Band'] == 'HATH', 1, 0)

        # Lower Band Logic
        condlist_low = [data['C_LRR'] > data['H_LRR'], data['C_LRR'] < data['L_LRR'], data['C_LRR'] < data['H_LRR']]
        choice_low = ['HL', 'LL', 'Brownian']
        data['Lower Band'] = np.select(condlist_low, choice_low, 'Brownian')

        # Volume Indicators
        data['Volume_1D'] = data['Volume'].pct_change(periods=1).round(4) * 100
        data['Volume_1W'] = data['Volume'].pct_change(periods=5).round(4) * 100
        data['Volume_1M'] = data['Volume'].pct_change(periods=21).round(4) * 100
        data['Volume_3M'] = data['Volume'].pct_change(periods=63).round(4) * 100

        # RSI Calculation
        periods = 14
        close_delta = data['Close'].diff()
        up = close_delta.clip(lower=0)
        down = -1 * close_delta.clip(upper=0)
        ma_up = up.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
        ma_down = down.ewm(com=periods - 1, adjust=True, min_periods=periods).mean()
        rsi = ma_up / ma_down
        data['RSI'] = 100 - (100 / (1 + rsi))

        # RSI Level
        condlist_rsi = [data['RSI'] > 70, data['RSI'] < 30, (data['RSI'] >= 30) & (data['RSI'] <= 70)]
        choice_rsi = ['Overbought', 'Oversold', 'In-Range']
        data['Level'] = np.select(condlist_rsi, choice_rsi, 'In-Range')

        # Machine Classification
        current_rvol_1m = data['Vlty'].iloc[-1]
        current_rvol_3m = data['Vlty_3m'].iloc[-1]

        if pd.notna(current_rvol_1m) and pd.notna(current_rvol_3m) and current_rvol_3m > 0:
            if current_rvol_1m < current_rvol_3m:
                machine_classification = 'Systematic Buying'
            else:
                machine_classification = 'Systematic Selling'
        else:
            machine_classification = 'Systematic Selling'  # Default

        # Calculate Signal Strength
        ss_score, ss_status, ss_action, warning_level, warning_flags = calculate_signal_strength(
            trade=data['Trade'].iloc[-1],
            trend=data['Trend'].iloc[-1],
            trade_chg=data['Trade_Change'].iloc[-1],
            trend_chg=data['Trend_Change'].iloc[-1],
            close=data['Close'].iloc[-1],
            lrr=data['BOTTOM_END'].iloc[-1],
            trr=data['TOP_END'].iloc[-1],
            upper_band=data['Upper Band'].iloc[-1],
            lower_band=data['Lower Band'].iloc[-1],
            ath_value=ath_value,
            rsi=data['RSI'].iloc[-1],
            rvol_1m=data['Vlty'].iloc[-1],
            rvol_3m=data['Vlty_3m'].iloc[-1],
            vix=data['VIX'].iloc[-1],
            vix_ma=data['VIX_MA'].iloc[-1],
            vix_roc_ma=data['VIX_ROC_MA'].iloc[-1],
            vol_roc_ma=data['VOL_ROC_MA'].iloc[-1],
            chg_1d=data['change_1D'].iloc[-1],
            chg_1w=data['1W_change'].iloc[-1],
            chg_1m=data['1M_change'].iloc[-1],
            chg_3m=data['3M_change'].iloc[-1],
            volume_1d=data['Volume_1D'].iloc[-1],
            volume_1w=data['Volume_1W'].iloc[-1]
        )

        # Build Row for Summary
        rowList = [
            x, 
            data['Close'].iloc[-1], 
            data['BOTTOM_END'].iloc[-1], 
            data['TOP_END'].iloc[-1], 
            data['DOWN_PCT'].iloc[-1], 
            data['UP_PCT'].iloc[-1], 
            data['Lower Band'].iloc[-1], 
            data['Upper Band'].iloc[-1], 
            ath_value, 
            data['Trade_Level'].iloc[-1], 
            data['Trend_Level'].iloc[-1], 
            data['Trade'].iloc[-1], 
            data['Trade_Change'].iloc[-1],
            data['Trend'].iloc[-1], 
            data['Trend_Change'].iloc[-1], 
            data['change_1D'].iloc[-1],
            data['1W_change'].iloc[-1], 
            data['1M_change'].iloc[-1], 
            data['3M_change'].iloc[-1],
            data['Vlty'].iloc[-1], 
            data['Vlty_3m'].iloc[-1], 
            machine_classification,
            data['Volume_1D'].iloc[-1], 
            data['Volume_1W'].iloc[-1], 
            data['Volume_1M'].iloc[-1],
            data['Volume_3M'].iloc[-1], 
            data['RSI'].iloc[-1], 
            data['Level'].iloc[-1], 
            data['Beta_1Y'].iloc[-1], 
            ss_score, 
            ss_status, 
            ss_action, 
            warning_level, 
            warning_flags
        ]

        summaryList.append(rowList)
        print(f"   ✅ {x} processing complete\n")
        
    except Exception as e:
        print(f"   ❌ ERROR processing {x}: {str(e)}")
        import traceback
        traceback.print_exc()
        print()
        continue

print("\n✅ Processing complete\n")

# ============================================================
# CREATE SUMMARY DATAFRAME
# ============================================================
smry = pd.DataFrame(summaryList, columns=[
    'Ticker', 'Close', 'Bottom End', 'Top End', 'Down side %', 'Up side %',
    'Lower Band', 'Upper band', 'ATH', 'Trade_lvl', 'Trend_Lvl',
    'Trade', 'Trade_Chg', 'Trend', 'Trend_Chg',
    '1D %', '1W %', '1M %', '3M %', 'RVOL_1M', 'RVOL_3M', 'Machine',
    'Vlm 1D %', 'Vlm 1W %', 'Vlm 1M %', 'Vlm 3M %', 'RSI', 'Level', 'Beta_1Y',
    'SS_Score', 'SS_Status', 'SS_Action', 'Warn_Lvl', 'Warn_Flags'
])

print("📋 Summary DataFrame created")
print(f"   Rows: {len(smry)}")
print(f"   Columns: {len(smry.columns)}")

# 🔧 DEBUG: Check for missing data in output
print("\n🔍 Checking for missing data in output:")
for col in ['Bottom End', 'Top End', 'RVOL_1M', 'RVOL_3M', 'Beta_1Y']:
    missing_count = smry[col].isna().sum()
    print(f"   {col:15s}: {missing_count} missing values")

# ============================================================
# SAVE TO CSV
# ============================================================
output_filename = 'output.csv'
smry.to_csv(output_filename, index=False)

print(f"\n💾 Data saved to {output_filename}")
print(f"📊 File size: {len(smry)} rows x {len(smry.columns)} columns")
print("\n🎉 Script completed successfully!")
