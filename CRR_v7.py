#!/usr/bin/env python3
"""
Automated Daily Stock Analysis Script
Runs via GitHub Actions at 7pm daily
Outputs: output.csv
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ============================================================
# DYNAMIC DATE CALCULATION
# ============================================================
# Today's date (GitHub Actions runs in UTC, adjust if needed)
today = datetime.now()
end_date = (today + timedelta(days=1)).strftime('%Y-%m-%d')  # Yahoo Finance needs +1 day
start_date = (today - timedelta(days=300)).strftime('%Y-%m-%d')  # Last 90 days

print(f"📅 Fetching data from {start_date} to {end_date}")

# ============================================================
# TICKER CONFIGURATION
# ============================================================
tickers = ['^TNX', '^GSPC', '^IXIC', '^RUT', '^VIX', '^NYICDX', 
           'AAAU', 'AAPL', 'IBIT', 'QQQ', 'GLD', 'SLV', 'NVDA']

# ============================================================
# DOWNLOAD DATA
# ============================================================
print("📊 Downloading current data...")
StkData = yf.download(tickers, start=start_date, end=end_date)
StkData.reset_index(inplace=True)
StkData = StkData.rename(columns={'index': 'Date'})

print("📈 Downloading all-time high data...")
ATH_Data = yf.download(tickers, period='max', auto_adjust=False)['Adj Close']
max_close_prices = ATH_Data.max()

print("✅ Data download complete\n")

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
# MAIN PROCESSING LOOP
# ============================================================
print("🔄 Processing tickers...\n")

for x in tickers:
    print(f"  → {x}")
    
    data['Close'] = StkData['Close'][x]
    data['Volume'] = StkData['Volume'][x]
    data['VIX'] = StkData['Close']['^VIX']
    data['SP_Volume'] = StkData['Volume']['^GSPC']

    # Weighted Moving Average
    WeightList = [.5, .5, 2, 3, 4, 5, 6]
    weights = np.array(WeightList)
    wma7 = data['Close'].rolling(7).apply(lambda prices: np.dot(prices, weights)/weights.sum(), raw=True)
    data['WMA7'] = np.round(wma7, decimals=3)
    data['SMA7'] = data['Close'].rolling(9).mean()

    # Beta Calculation
    data['Stock_Returns'] = data['Close'].pct_change()
    data['SP500_Returns'] = StkData['Close']['^GSPC'].pct_change()
    rolling_cov = data['Stock_Returns'].rolling(252).cov(data['SP500_Returns'])
    rolling_var = data['SP500_Returns'].rolling(252).var()
    data['Beta_1Y'] = rolling_cov / rolling_var

    # Standard Deviation
    data['STD_DEV'] = data.Close.rolling(7).std()

    # Risk Range Calculation
    sigma_u = 1.4
    sigma_l = 1.8
    data['UPPER'] = data.WMA7 + (data.STD_DEV * sigma_u)
    data['LOWER'] = data.SMA7 - (data.STD_DEV * sigma_l)

    # VIX Calculations
    data['VIX_MA'] = data.VIX.rolling(2).mean()
    data['VIX_ROC'] = data.VIX.pct_change().abs()
    data['VIX_ROC_MA'] = data.VIX_ROC.rolling(2).mean()

    # Volume Calculations
    data['VOL'] = data.SP_Volume / 10
    data['VOL_MA'] = data.VOL.rolling(7).mean()
    data['VOL_ROC'] = data.VOL.pct_change().abs()
    data['VOL_ROC_MA'] = data.VOL_ROC.rolling(2).mean()

    # Final Risk Range with VIX/Volume Adjustment
    conditions_u = [(data.VIX_ROC_MA > 0.08) & (data.VIX_MA >= 15) & (data.VOL_ROC_MA > 0.27), 
                    (data.VIX_MA == data.VIX_MA)]
    choices_u = [data.UPPER * .9875, data.UPPER]
    data['TOP_END'] = np.select(conditions_u, choices_u).round(2)

    conditions_l = [(data.VIX_ROC_MA > 0.08) & (data.VIX_MA >= 15) & (data.VOL_ROC_MA > 0.27), 
                    (data.VIX_MA == data.VIX_MA)]
    choices_l = [data.LOWER * .99, data.LOWER]
    data['BOTTOM_END'] = np.select(conditions_l, choices_l).round(2)

    data['DOWN_PCT'] = (((data.LOWER - data.Close) / data.Close) * 100).round(2)
    data['UP_PCT'] = (((data.UPPER - data.Close) / data.Close) * 100).round(2)
    
    # Trade and Trend Levels
    data['Trade_Level'] = data.Close.shift(periods=15).round(2)
    data['Trend_Level'] = data.Close.shift(periods=62).round(2)
    
    condlist1 = [data['Trade_Level'] < data.Close, data['Trade_Level'] > data.Close]
    condlist = [data['Trend_Level'] < data.Close, data['Trend_Level'] > data.Close]
    choicelist = ['Bullish', 'Bearish']
    
    data['Trade'] = np.select(condlist1, choicelist, 'Neutral')
    data['Trend'] = np.select(condlist, choicelist, 'Neutral')

    # Change Indicators
    data['Trade_Change'] = np.where(data['Trade'] != data['Trade'].shift(1), '⚠', '')
    data['Trend_Change'] = np.where(data['Trend'] != data['Trend'].shift(1), '⚠', '')

    # Price Changes
    data['change_1D'] = data.Close.pct_change(periods=1).round(4) * 100
    data['1W_change'] = data.Close.pct_change(periods=5).round(4) * 100
    data['1M_change'] = data.Close.pct_change(periods=21).round(4) * 100
    data['3M_change'] = data.Close.pct_change(periods=63).round(4) * 100
    
    # Volatility Calculations
    data['30D_sd'] = data.change_1D.rolling(21).std()
    data['90D_sd'] = data.change_1D.rolling(63).std()
    data['Vlty'] = data['30D_sd'] * 15.87450786638754
    data['Vlty_3m'] = np.maximum(0, data['90D_sd'] * (252**0.5))

    # Band Analysis
    data['H_TRR'] = data.UPPER.iloc[-63:-2].max()
    data['L_TRR'] = data.UPPER.iloc[-63:-2].min()
    data['H_LRR'] = data.LOWER.iloc[-63:-2].max()
    data['L_LRR'] = data.LOWER.iloc[-63:-2].min()
    data['C_TRR'] = data.UPPER.iloc[-1]
    data['C_LRR'] = data.LOWER.iloc[-1]

    # Get ATH value
    ath_value = None
    if x in max_close_prices.index:
        ath_value = max_close_prices.loc[x]

    # Upper Band Logic with HATH Detection
    if ath_value is not None:
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
    data['Volume_1D'] = data.Volume.pct_change(periods=1).round(4) * 100
    data['Volume_1W'] = data.Volume.pct_change(periods=5).round(4) * 100
    data['Volume_1M'] = data.Volume.pct_change(periods=21).round(4) * 100
    data['Volume_3M'] = data.Volume.pct_change(periods=63).round(4) * 100

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

    if current_rvol_1m < current_rvol_3m:
        machine_classification = 'Systematic Buying'
    else:
        machine_classification = 'Systematic Selling'

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
        x, data.Close.iloc[-1], data.BOTTOM_END.iloc[-1], data.TOP_END.iloc[-1], 
        data.DOWN_PCT.iloc[-1], data.UP_PCT.iloc[-1], data['Lower Band'].iloc[-1], 
        data['Upper Band'].iloc[-1], ath_value, data.Trade_Level.iloc[-1], 
        data.Trend_Level.iloc[-1], data['Trade'].iloc[-1], data['Trade_Change'].iloc[-1],
        data['Trend'].iloc[-1], data['Trend_Change'].iloc[-1], data['change_1D'].iloc[-1],
        data['1W_change'].iloc[-1], data['1M_change'].iloc[-1], data['3M_change'].iloc[-1],
        data['Vlty'].iloc[-1], data['Vlty_3m'].iloc[-1], machine_classification,
        data['Volume_1D'].iloc[-1], data['Volume_1W'].iloc[-1], data['Volume_1M'].iloc[-1],
        data['Volume_3M'].iloc[-1], data['RSI'].iloc[-1], data['Level'].iloc[-1], 
        data['Beta_1Y'].iloc[-1], ss_score, ss_status, ss_action, warning_level, warning_flags
    ]

    summaryList.append(rowList)

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

# ============================================================
# SAVE TO CSV
# ============================================================
output_filename = 'output.csv'
smry.to_csv(output_filename, index=False)

print(f"\n💾 Data saved to {output_filename}")
print(f"📊 File size: {len(smry)} rows x {len(smry.columns)} columns")
print("\n🎉 Script completed successfully!")
