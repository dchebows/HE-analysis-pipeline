"""
Shared feature engineering for SPX and Nasdaq risk range models
"""
import numpy as np
import pandas as pd

def add_features(data):
    """Add all features for risk range modeling"""
    x = data.copy()
    
    # Price/return features
    x["ret_1"] = np.log(x["close"] / x["close"].shift(1))
    x["ret_2"] = np.log(x["close"] / x["close"].shift(2))
    x["ret_3"] = np.log(x["close"] / x["close"].shift(3))
    x["ret_5"] = np.log(x["close"] / x["close"].shift(5))
    x["ret_10"] = np.log(x["close"] / x["close"].shift(10))
    x["ret_20"] = np.log(x["close"] / x["close"].shift(20))
    
    x["ret_accel_1"] = x["ret_1"] - x["ret_1"].shift(1)
    x["ret_accel_5"] = x["ret_5"] - x["ret_5"].shift(1)
    
    x["gap"] = (x["open"] - x["close"].shift(1)) / x["close"].shift(1)
    x["body"] = (x["close"] - x["open"]) / x["open"]
    
    x["range_1"] = (x["high"] - x["low"]) / x["close"].shift(1)
    x["log_hl"] = np.log(x["high"] / x["low"])
    
    daily_range = (x["high"] - x["low"]).replace(0, np.nan)
    x["clv"] = ((x["close"] - x["low"]) - (x["high"] - x["close"])) / daily_range
    x["clv"] = x["clv"].fillna(0)
    
    x["high_to_prev_close"] = (x["high"] - x["close"].shift(1)) / x["close"].shift(1)
    x["prev_close_to_low"] = (x["close"].shift(1) - x["low"]) / x["close"].shift(1)
    
    # Rolling features
    for w in [3, 5, 10, 20]:
        x[f"range_mean_{w}"] = x["range_1"].rolling(w).mean()
        x[f"range_median_{w}"] = x["range_1"].rolling(w).median()
        x[f"range_std_{w}"] = x["range_1"].rolling(w).std()
        x[f"ret_abs_mean_{w}"] = x["ret_1"].abs().rolling(w).mean()
        x[f"ret_std_{w}"] = x["ret_1"].rolling(w).std()
        x[f"close_sma_dist_{w}"] = (x["close"] / x["close"].rolling(w).mean()) - 1.0
    
    x["range_roc_1"] = np.log(x["range_1"] / x["range_1"].shift(1))
    x["range_roc_3"] = np.log(x["range_1"] / x["range_1"].rolling(3).median())
    x["range_roc_5"] = np.log(x["range_1"] / x["range_1"].rolling(5).median())
    
    x["range_vs_med5"] = x["range_1"] / x["range_1"].rolling(5).median()
    x["range_vs_med10"] = x["range_1"] / x["range_1"].rolling(10).median()
    x["range_vs_med20"] = x["range_1"] / x["range_1"].rolling(20).median()
    
    for w in [3, 5, 10, 20]:
        x[f"hl_span_{w}"] = (x["high"].rolling(w).max() - x["low"].rolling(w).min()) / x["close"]
    
    x["vol_ratio_3_10"] = x["ret_abs_mean_3"] / x["ret_abs_mean_10"]
    x["vol_ratio_5_20"] = x["ret_abs_mean_5"] / x["ret_abs_mean_20"]
    x["range_ratio_3_10"] = x["range_mean_3"] / x["range_mean_10"]
    x["range_ratio_5_20"] = x["range_mean_5"] / x["range_mean_20"]
    
    x["up_day"] = (x["ret_1"] > 0).astype(float)
    x["down_day"] = (x["ret_1"] < 0).astype(float)
    x["up_streak_5"] = x["up_day"].rolling(5).sum()
    x["down_streak_5"] = x["down_day"].rolling(5).sum()
    
    return x

def add_vix_features(data, vix_col_prefix):
    """Add VIX/VXN features"""
    x = data.copy()
    
    close_col = f"{vix_col_prefix}_close"
    high_col = f"{vix_col_prefix}_high"
    low_col = f"{vix_col_prefix}_low"
    
    x[f"{vix_col_prefix}_ret_1"] = np.log(x[close_col] / x[close_col].shift(1))
    x[f"{vix_col_prefix}_ret_3"] = np.log(x[close_col] / x[close_col].shift(3))
    x[f"{vix_col_prefix}_ret_5"] = np.log(x[close_col] / x[close_col].shift(5))
    x[f"{vix_col_prefix}_ret_10"] = np.log(x[close_col] / x[close_col].shift(10))
    
    x[f"{vix_col_prefix}_range_1"] = (x[high_col] - x[low_col]) / x[close_col].shift(1)
    vix_range = (x[high_col] - x[low_col]).replace(0, np.nan)
    x[f"{vix_col_prefix}_clv"] = ((x[close_col] - x[low_col]) - (x[high_col] - x[close_col])) / vix_range
    x[f"{vix_col_prefix}_clv"] = x[f"{vix_col_prefix}_clv"].fillna(0)
    
    for w in [3, 5, 10, 20]:
        x[f"{vix_col_prefix}_mean_{w}"] = x[close_col].rolling(w).mean()
        x[f"{vix_col_prefix}_std_{w}"] = x[close_col].rolling(w).std()
        x[f"{vix_col_prefix}_dist_mean_{w}"] = (x[close_col] / x[f"{vix_col_prefix}_mean_{w}"]) - 1.0
    
    x[f"{vix_col_prefix}_range_vs_5"] = x[f"{vix_col_prefix}_range_1"] / x[f"{vix_col_prefix}_range_1"].rolling(5).median()
    x[f"{vix_col_prefix}_range_vs_10"] = x[f"{vix_col_prefix}_range_1"] / x[f"{vix_col_prefix}_range_1"].rolling(10).median()
    
    # Tail risk features
    x[f"{vix_col_prefix}_velocity_abs_1d"] = (x[close_col].pct_change(1)).abs()
    x[f"{vix_col_prefix}_velocity_abs_2d"] = (x[close_col].pct_change(2)).abs()
    x[f"{vix_col_prefix}_velocity_abs_3d"] = (x[close_col].pct_change(3)).abs()
    x[f"{vix_col_prefix}_velocity_abs_5d"] = (x[close_col].pct_change(5)).abs()
    
    x["tail_interaction_1d"] = x[f"{vix_col_prefix}_velocity_abs_1d"] * x["range_vs_med5"]
    x["tail_interaction_2d"] = x[f"{vix_col_prefix}_velocity_abs_2d"] * x["range_vs_med5"]
    
    vix_up = (x[close_col].pct_change() > 0).astype(float)
    x[f"{vix_col_prefix}_up_streak_3"] = vix_up.rolling(3).sum()
    x[f"{vix_col_prefix}_up_streak_5"] = vix_up.rolling(5).sum()
    
    x["range_expansion_2d"] = x["range_1"] / x["range_1"].shift(2)
    x["range_expansion_3d"] = x["range_1"] / x["range_1"].shift(3)
    
    x["downside_pressure"] = x["ret_1"].clip(upper=0).abs() * x[f"{vix_col_prefix}_velocity_abs_1d"]
    
    return x

def rolling_scaling_slope(series, window=100, horizons=[1, 2, 5, 10, 20]):
    """Calculate fractal scaling slope"""
    s = pd.Series(series).copy()
    out = pd.Series(index=s.index, dtype=float)
    log_s = np.log(s)
    
    for i in range(window, len(s)):
        segment = log_s.iloc[i-window:i]
        xs, ys = [], []
        for h in horizons:
            diff = segment.diff(h).abs().dropna()
            if len(diff) > 5 and diff.mean() > 0:
                xs.append(np.log(h))
                ys.append(np.log(diff.mean()))
        if len(xs) >= 3:
            out.iloc[i] = np.polyfit(xs, ys, 1)[0]
        else:
            out.iloc[i] = np.nan
    
    # Forward fill to avoid losing recent data
    out = out.fillna(method='ffill')
    return out

def add_regime_features(data, regime_col, vix_col_prefix):
    """Add regime-based features"""
    x = data.copy()
    
    x["regime_investible"] = (x[regime_col] == "investible").astype(int)
    x["regime_chop"] = (x[regime_col] == "chop").astype(int)
    x["regime_get_out"] = (x[regime_col] == "get_out").astype(int)
    x[f"{regime_col}_code"] = x[regime_col].map({"investible": 0, "chop": 1, "get_out": 2})
    
    x["ret_x_vix"] = x["ret_1"] * x[f"{vix_col_prefix}_close"]
    x["range_x_vix"] = x["range_1"] * x[f"{vix_col_prefix}_close"]
    x[f"clv_x_{vix_col_prefix}ret"] = x["clv"] * x[f"{vix_col_prefix}_ret_1"]
    
    return x
