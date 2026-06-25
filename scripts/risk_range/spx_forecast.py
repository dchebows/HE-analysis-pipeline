"""
SPX Risk Range Forecast Generator
"""
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import json
from feature_engineering import add_features, add_vix_features, rolling_scaling_slope, add_regime_features
from model_utils import train_regime_models, predict_regime, calibrate_scale, apply_conditional_floor

def classify_vix_regime(v):
    """Classify VIX regime"""
    if pd.isna(v):
        return np.nan
    elif v < 19:
        return "investible"
    elif v < 30:
        return "chop"
    else:
        return "get_out"

def generate_spx_forecast():
    """Generate SPX risk range forecast"""
    try:
        # Download data
        tomorrow = (datetime.now().date() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        spx_raw = yf.download("^GSPC", start="1990-01-01", end=tomorrow, auto_adjust=False, progress=False)
        vix_raw = yf.download("^VIX", start="1990-01-01", end=tomorrow, auto_adjust=False, progress=False)
        
        # Clean column names
        if isinstance(spx_raw.columns, pd.MultiIndex):
            spx_raw.columns = [c[0] for c in spx_raw.columns]
        if isinstance(vix_raw.columns, pd.MultiIndex):
            vix_raw.columns = [c[0] for c in vix_raw.columns]
        
        spx_raw.columns = [c.lower().replace(" ", "_") for c in spx_raw.columns]
        vix_raw.columns = [c.lower().replace(" ", "_") for c in vix_raw.columns]
        
        spx = spx_raw[["open", "high", "low", "close", "adj_close", "volume"]].copy()
        vix = vix_raw[["open", "high", "low", "close", "adj_close"]].copy()
        vix = vix.rename(columns={
            "open": "vix_open", "high": "vix_high", "low": "vix_low",
            "close": "vix_close", "adj_close": "vix_adj_close"
        })
        
        df = spx.join(vix, how="inner").dropna().copy()
        
        # VIX regimes
        df["vix_regime"] = df["vix_close"].apply(classify_vix_regime)
        
        # Create targets
        data = df.copy()
        data["next_high"] = data["high"].shift(-1)
        data["next_low"] = data["low"].shift(-1)
        data["trr_next"] = (data["next_high"] - data["close"]) / data["close"]
        data["llr_next"] = (data["close"] - data["next_low"]) / data["close"]
        
        # Capture latest row BEFORE feature engineering drops it
        latest_row_date = data.index[-1]
        latest_close_raw = data['close'].iloc[-1]
        latest_vix_raw = data['vix_close'].iloc[-1]
        latest_regime_raw = data['vix_regime'].iloc[-1]
        
        # Feature engineering
        data = add_features(data)
        data = add_vix_features(data, "vix")
        
        # Fractal scaling with forward fill
        data["spx_scaling_100"] = rolling_scaling_slope(data["close"], window=100)
        data["spx_scaling_200"] = rolling_scaling_slope(data["close"], window=200)
        data["vix_scaling_100"] = rolling_scaling_slope(data["vix_close"], window=100)
        data["vix_scaling_200"] = rolling_scaling_slope(data["vix_close"], window=200)
        
        data = add_regime_features(data, "vix_regime", "vix")
        
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
            "vix_close",
            "vix_ret_1", "vix_ret_3", "vix_ret_5", "vix_ret_10",
            "vix_range_1", "vix_clv",
            "vix_mean_3", "vix_mean_5", "vix_mean_10", "vix_mean_20",
            "vix_std_3", "vix_std_5", "vix_std_10", "vix_std_20",
            "vix_dist_mean_3", "vix_dist_mean_5", "vix_dist_mean_10", "vix_dist_mean_20",
            "vix_range_vs_5", "vix_range_vs_10",
            "vix_regime_code", "regime_investible", "regime_chop", "regime_get_out",
            "ret_x_vix", "range_x_vix", "clv_x_vixret",
            "spx_scaling_100", "spx_scaling_200",
            "vix_scaling_100", "vix_scaling_200",
            "vix_velocity_abs_1d", "vix_velocity_abs_2d", "vix_velocity_abs_3d", "vix_velocity_abs_5d",
            "tail_interaction_1d", "tail_interaction_2d",
            "vix_up_streak_3", "vix_up_streak_5",
            "range_expansion_2d", "range_expansion_3d",
            "downside_pressure",
        ]
        
        model_data = data[
            feature_cols + ["close", "high", "low", "next_high", "next_low", "trr_next", "llr_next", "vix_regime"]
        ].copy()
        model_data = model_data.replace([np.inf, -np.inf], np.nan).dropna().copy()
        
        # Training setup
        TRAIN_WINDOW_DAYS = 252 * 5
        CAL_WINDOW_DAYS = 126
        TRR_QUANTILES = [0.50, 0.80]
        LLR_QUANTILES = [0.80, 0.90, 0.95]
        
        latest_row = model_data.iloc[[-1]]
        train_end = len(model_data) - 1
        train_start = max(0, train_end - TRAIN_WINDOW_DAYS)
        train_window = model_data.iloc[train_start:train_end]
        cal_window = train_window.iloc[-CAL_WINDOW_DAYS:]
        
        # Train models
        trr_models = train_regime_models(train_window, feature_cols, "trr_next", TRR_QUANTILES)
        llr_models = train_regime_models(train_window, feature_cols, "llr_next", LLR_QUANTILES)
        
        # Calibrate
        latest_regime = latest_row["vix_regime"].iloc[0]
        
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
        
        cal_df = cal_window[["close", "trr_next", "llr_next", "vix_regime"]].copy()
        trr_scales = {}
        llr_scales = {}
        
        for q in TRR_QUANTILES:
            band = str(int(q * 100))
            cal_df[f"trr_{band}_raw"] = cal_trr_preds[band]
            trr_scales[band] = calibrate_scale(cal_df, "trr_next", f"trr_{band}_raw", q, "vix_regime")
        
        for q in LLR_QUANTILES:
            band = str(int(q * 100))
            cal_df[f"llr_{band}_raw"] = cal_llr_preds[band]
            llr_scales[band] = calibrate_scale(cal_df, "llr_next", f"llr_{band}_raw", q, "vix_regime")
        
        # Generate forecast
        trr_preds = predict_regime(latest_row, feature_cols, trr_models, TRR_QUANTILES, "vix_regime")
        llr_preds = predict_regime(latest_row, feature_cols, llr_models, LLR_QUANTILES, "vix_regime")
        
        # Use raw values from before dropna
        latest_close = latest_close_raw
        latest_vix = latest_vix_raw
        latest_regime = latest_regime_raw
        latest_date = latest_row_date
        
        # Calculate forecast levels
        trr_80_cal = trr_preds[0.80] * trr_scales["80"]
        llr_95_cal = llr_preds[0.95] * llr_scales["95"]
        
        forecast_high = latest_close * (1 + trr_80_cal)
        forecast_low = latest_close * (1 - llr_95_cal)
        
        # Apply conditional floor
        forecast_low, floor_active, range_multiple = apply_conditional_floor(
            forecast_low, latest_close, model_data
        )
        
        # Reference levels
        ref_levels = {
            "trr_50": float(latest_close * (1 + trr_preds[0.50] * trr_scales["50"])),
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
        regime_stats = model_data[model_data['vix_regime'] == latest_regime].tail(126).copy()
        regime_stats['daily_range'] = regime_stats['high'] - regime_stats['low']
        regime_stats['range_pct'] = regime_stats['daily_range'] / regime_stats['close']
        p90_range_pct = regime_stats['range_pct'].quantile(0.90) * 100
        predicted_range_pct = (forecast_high - forecast_low) / latest_close * 100
        
        if floor_active:
            risks.append(f"Range persistence detected ({range_multiple:.2f}x median) — floor applied")
        
        # VIX velocity check
        vix_history = model_data[['vix_close']].tail(10).copy()
        if len(vix_history) >= 2:
            vix_1d_change = (latest_vix - vix_history['vix_close'].iloc[-2]) / vix_history['vix_close'].iloc[-2] * 100
            vix_velocity_1d = abs(vix_1d_change)
            if vix_velocity_1d > 15:
                risks.append(f"High VIX velocity ({vix_velocity_1d:.1f}%) — elevated tail risk")
        
        if latest_regime == "chop" and latest_vix > 25:
            risks.append(f"VIX at {latest_vix:.1f}, approaching get_out threshold (30)")
        
        if latest_regime == "get_out":
            risks.append("Get_out regime active — model reliability reduced")
        
        if predicted_range_pct > p90_range_pct:
            risks.append(f"Predicted range ({predicted_range_pct:.2f}%) above 90th percentile for regime")
        
        # Build output JSON
        result = {
            "ticker": "^GSPC",
            "forecast_date": forecast_date.strftime('%Y-%m-%d'),
            "based_on_date": latest_date.strftime('%Y-%m-%d'),
            "based_on_close": float(latest_close),
            "vix": float(latest_vix),
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
            "model_version": "v4",
            "status": "success"
        }
        
        return result
        
    except Exception as e:
        return {
            "ticker": "^GSPC",
            "status": "error",
            "error_message": str(e),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S EST')
        }
