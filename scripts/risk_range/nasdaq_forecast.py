"""
Nasdaq Risk Range Forecast Generator
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
from feature_engineering import add_features, add_vix_features, rolling_scaling_slope, add_regime_features
from model_utils import train_regime_models, predict_regime, calibrate_scale, apply_conditional_floor

def classify_vxn_regime(v):
    """Classify VXN regime"""
    if pd.isna(v):
        return np.nan
    elif v < 20:
        return "investible"
    elif v < 30:
        return "chop"
    else:
        return "get_out"

def generate_nasdaq_forecast():
    """Generate Nasdaq risk range forecast"""
    try:
        # Download data
        tomorrow = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        ndx_raw = yf.download("^IXIC", start="2000-01-01", end=tomorrow, auto_adjust=False, progress=False)
        vxn_raw = yf.download("^VXN", start="2000-01-01", end=tomorrow, auto_adjust=False, progress=False)
        
        # Clean column names
        if isinstance(ndx_raw.columns, pd.MultiIndex):
            ndx_raw.columns = [c[0] for c in ndx_raw.columns]
        if isinstance(vxn_raw.columns, pd.MultiIndex):
            vxn_raw.columns = [c[0] for c in vxn_raw.columns]
        
        ndx_raw.columns = [c.lower().replace(" ", "_") for c in ndx_raw.columns]
        vxn_raw.columns = [c.lower().replace(" ", "_") for c in vxn_raw.columns]
        
        ndx = ndx_raw[["open", "high", "low", "close", "adj_close", "volume"]].copy()
        vxn = vxn_raw[["open", "high", "low", "close", "adj_close"]].copy()
        vxn = vxn.rename(columns={
            "open": "vxn_open", "high": "vxn_high", "low": "vxn_low",
            "close": "vxn_close", "adj_close": "vxn_adj_close"
        })
        
        df = ndx.join(vxn, how="inner").dropna().copy()
        
        # VXN regimes
        df["vxn_regime"] = df["vxn_close"].apply(classify_vxn_regime)
        
        # Create targets
        data = df.copy()
        data["next_high"] = data["high"].shift(-1)
        data["next_low"] = data["low"].shift(-1)
        data["trr_next"] = (data["next_high"] - data["close"]) / data["close"]
        data["llr_next"] = (data["close"] - data["next_low"]) / data["close"]
        
        # Capture latest row BEFORE feature engineering
        latest_row_date = data.index[-1]
        latest_close_raw = data['close'].iloc[-1]
        latest_vxn_raw = data['vxn_close'].iloc[-1]
        latest_regime_raw = data['vxn_regime'].iloc[-1]
        
        # Feature engineering
        data = add_features(data)
        data = add_vix_features(data, "vxn")
        
        # Fractal scaling
        data["ndx_scaling_100"] = rolling_scaling_slope(data["close"], window=100)
        data["ndx_scaling_200"] = rolling_scaling_slope(data["close"], window=200)
        data["vxn_scaling_100"] = rolling_scaling_slope(data["vxn_close"], window=100)
        data["vxn_scaling_200"] = rolling_scaling_slope(data["vxn_close"], window=200)
        
        data = add_regime_features(data, "vxn_regime", "vxn")
        
        # Feature list
        feature_cols = [
            "ret_1", "ret_2", "ret_3", "ret_5", "ret_10", "ret_20",
            "ret_accel_1", "ret_accel_5",
            "gap", "body", "range_1", "log_hl", "clv",
            "high_to_prev_close", "prev_close_to_low",
            "range_mean_3", "range_mean_5", "range_mean_10", "range_mean_20",
            "range_median_3", "range_median_5", "range_median_10", "range_median_20",
            "range_std_3", "range_std_5", "range_std_10", "range_std_20",
            "ret_abs_mean_3", "ret_abs_mean_5", "ret_abs_mean_10", "ret_abs_mean_20",
            "ret_std_3", "ret_std_5", "ret_std_10", "ret_std_20",
            "close_sma_dist_3", "close_sma_dist_5", "close_sma_dist_10", "close_sma_dist_20",
            "range_roc_1", "range_roc_3", "range_roc_5",
            "range_vs_med5", "range_vs_med10", "range_vs_med20",
            "hl_span_3", "hl_span_5", "hl_span_10", "hl_span_20",
            "vol_ratio_3_10", "vol_ratio_5_20", "range_ratio_3_10", "range_ratio_5_20",
            "up_streak_5", "down_streak_5",
            "vxn_close",
            "vxn_ret_1", "vxn_ret_3", "vxn_ret_5", "vxn_ret_10",
            "vxn_range_1", "vxn_clv",
            "vxn_mean_3", "vxn_mean_5", "vxn_mean_10", "vxn_mean_20",
            "vxn_std_3", "vxn_std_5", "vxn_std_10", "vxn_std_20",
            "vxn_dist_mean_3", "vxn_dist_mean_5", "vxn_dist_mean_10", "vxn_dist_mean_20",
            "vxn_range_vs_5", "vxn_range_vs_10",
            "vxn_regime_code", "regime_investible", "regime_chop", "regime_get_out",
            "ret_x_vix", "range_x_vix", "clv_x_vxnret",
            "ndx_scaling_100", "ndx_scaling_200",
            "vxn_scaling_100", "vxn_scaling_200",
            "vxn_velocity_abs_1d", "vxn_velocity_abs_2d", "vxn_velocity_abs_3d", "vxn_velocity_abs_5d",
            "tail_interaction_1d", "tail_interaction_2d",
            "vxn_up_streak_3", "vxn_up_streak_5",
            "range_expansion_2d", "range_expansion_3d",
            "downside_pressure",
        ]
        
        model_data = data[
            feature_cols + ["close", "high", "low", "next_high", "next_low", "trr_next", "llr_next", "vxn_regime"]
        ].copy()
        model_data = model_data.replace([np.inf, -np.inf], np.nan).dropna().copy()
        
        # Training setup
        TRAIN_WINDOW_DAYS = 252 * 5
        CAL_WINDOW_DAYS = 126
        TRR_QUANTILES = [0.50, 0.80]
        LLR_QUANTILES = [0.80, 0.90, 0.95, 0.97]  # V5 includes 97th percentile
        
        latest_row = model_data.iloc[[-1]]
        train_end = len(model_data) - 1
        train_start = max(0, train_end - TRAIN_WINDOW_DAYS)
        train_window = model_data.iloc[train_start:train_end]
        cal_window = train_window.iloc[-CAL_WINDOW_DAYS:]
        
        # Train models
        trr_models = train_regime_models(train_window, feature_cols, "trr_next", TRR_QUANTILES)
        llr_models = train_regime_models(train_window, feature_cols, "llr_next", LLR_QUANTILES)
        
        # Calibrate
        latest_regime = latest_row["vxn_regime"].iloc[0]
        
        cal_trr_preds = {}
        cal_llr_preds = {}
        
        for q in TRR_QUANTILES:
            band = str(int(q * 100))
            models = trr_models[latest_regime]["models"]
            cal_trr_preds[band] = np.maximum(models[q].predict(cal_window[feature_cols].values), 0.0)
        
        for q in LLR_QUANTILES:
            band = str(int(q * 100))
            models = llr_models[latest_regime]["models"]
            cal_llr_preds[band] = np.maximum(models[q].predict(cal_window[feature_cols].values), 0.0)
        
        cal_df = cal_window[["close", "trr_next", "llr_next", "vxn_regime"]].copy()
        trr_scales = {}
        llr_scales = {}
        
        for q in TRR_QUANTILES:
            band = str(int(q * 100))
            cal_df[f"trr_{band}_raw"] = cal_trr_preds[band]
            trr_scales[band] = calibrate_scale(cal_df, "trr_next", f"trr_{band}_raw", q, "vxn_regime")
        
        for q in LLR_QUANTILES:
            band = str(int(q * 100))
            cal_df[f"llr_{band}_raw"] = cal_llr_preds[band]
            llr_scales[band] = calibrate_scale(cal_df, "llr_next", f"llr_{band}_raw", q, "vxn_regime")
        
        # Generate forecast
        trr_preds = predict_regime(latest_row, feature_cols, trr_models, TRR_QUANTILES, "vxn_regime")
        llr_preds = predict_regime(latest_row, feature_cols, llr_models, LLR_QUANTILES, "vxn_regime")
        
        # Use raw values
        latest_close = latest_close_raw
        latest_vxn = latest_vxn_raw
        latest_regime = latest_regime_raw
        latest_date = latest_row_date
        
        # Calculate forecast levels
        trr_80_cal = trr_preds[0.80] * trr_scales["80"]
        llr_97_cal = llr_preds[0.97] * llr_scales["97"]  # V5 uses 97th percentile
        
        forecast_high = latest_close * (1 + trr_80_cal)
        forecast_low = latest_close * (1 - llr_97_cal)
        
        # Apply conditional floor
        forecast_low, floor_active, range_multiple = apply_conditional_floor(
            forecast_low, latest_close, model_data
        )
        
        # Reference levels
        ref_levels = {
            "trr_50": float(latest_close * (1 + trr_preds[0.50] * trr_scales["50"])),
            "llr_95": float(latest_close * (1 - llr_preds[0.95] * llr_scales["95"])),
            "llr_90": float(latest_close * (1 - llr_preds[0.90] * llr_scales["90"])),
            "llr_80": float(latest_close * (1 - llr_preds[0.80] * llr_scales["80"]))
        }
        
        # Calculate next trading day
        forecast_date = latest_date + timedelta(days=1)
        while forecast_date.weekday() >= 5:
            forecast_date += timedelta(days=1)
        
        # Identify risks
        risks = []
        
        # Get regime stats
        regime_stats = model_data[model_data['vxn_regime'] == latest_regime].tail(126).copy()
        regime_stats['daily_range'] = regime_stats['high'] - regime_stats['low']
        regime_stats['range_pct'] = regime_stats['daily_range'] / regime_stats['close']
        p90_range_pct = regime_stats['range_pct'].quantile(0.90) * 100
        predicted_range_pct = (forecast_high - forecast_low) / latest_close * 100
        
        if floor_active:
            risks.append(f"Range persistence detected ({range_multiple:.2f}x median) — floor applied")
        
        # VXN velocity check
        vxn_history = model_data[['vxn_close']].tail(10).copy()
        if len(vxn_history) >= 2:
            vxn_1d_change = (latest_vxn - vxn_history['vxn_close'].iloc[-2]) / vxn_history['vxn_close'].iloc[-2] * 100
            vxn_velocity_1d = abs(vxn_1d_change)
            if vxn_velocity_1d > 15:
                risks.append(f"High VXN velocity ({vxn_velocity_1d:.1f}%) — elevated tail risk")
        
        if latest_regime == "chop" and latest_vxn > 25:
            risks.append(f"VXN at {latest_vxn:.1f}, approaching get_out threshold (30)")
        
        if latest_regime == "get_out":
            risks.append("Get_out regime active — model reliability reduced")
        
        if predicted_range_pct > p90_range_pct:
            risks.append(f"Predicted range ({predicted_range_pct:.2f}%) above 90th percentile for regime")
        
        # Build output JSON
        result = {
            "ticker": "^IXIC",
            "forecast_date": forecast_date.strftime('%Y-%m-%d'),
            "based_on_date": latest_date.strftime('%Y-%m-%d'),
            "based_on_close": float(latest_close),
            "vix": float(latest_vxn),
            "regime": latest_regime,
            "forecast_high": float(forecast_high),
            "forecast_low": float(forecast_low),
            "high_pct": float((forecast_high - latest_close) / latest_close * 100),
            "low_pct": float((forecast_low - latest_close) / latest_close * 100),
            "range_width": float(forecast_high - forecast_low),
            "floor_active": bool(floor_active),
            "reference_levels": ref_levels,
            "risks": risks,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S EST'),
            "model_version": "v5",
            "status": "success"
        }
        
        return result
        
    except Exception as e:
        return {
            "ticker": "^IXIC",
            "status": "error",
            "error_message": str(e),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')
        }
