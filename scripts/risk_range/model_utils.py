"""
Model utilities for risk range forecasting
"""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

def make_quantile_model(alpha):
    """Create quantile regression model"""
    return GradientBoostingRegressor(
        loss="quantile", alpha=alpha, n_estimators=100,
        learning_rate=0.08, max_depth=3, min_samples_leaf=30,
        min_samples_split=30, subsample=0.75, random_state=42
    )

def make_median_model():
    """Create median regression model"""
    return GradientBoostingRegressor(
        loss="absolute_error", n_estimators=100,
        learning_rate=0.08, max_depth=3, min_samples_leaf=30,
        min_samples_split=30, subsample=0.75, random_state=42
    )

def train_regime_models(train_df, feature_cols, target_col, quantiles, min_samples=250):
    """Train regime-specific quantile models"""
    regime_models = {}
    global_models = {}
    
    # Train global models first
    for q in quantiles:
        model = make_median_model() if q == 0.50 else make_quantile_model(q)
        model.fit(train_df[feature_cols].values, train_df[target_col].values)
        global_models[q] = model
    
    # Train regime-specific models where possible
    regime_col = [col for col in train_df.columns if 'regime' in col and col.endswith('_regime')][0]
    
    for regime in ["investible", "chop", "get_out"]:
        g = train_df[train_df[regime_col] == regime]
        if len(g) >= min_samples:
            models = {}
            for q in quantiles:
                model = make_median_model() if q == 0.50 else make_quantile_model(q)
                model.fit(g[feature_cols].values, g[target_col].values)
                models[q] = model
            regime_models[regime] = {"models": models, "uses_fallback": False}
        else:
            regime_models[regime] = {"models": global_models, "uses_fallback": True}
    
    return regime_models

def predict_regime(row_df, feature_cols, regime_models, quantiles, regime_col):
    """Generate predictions for a single row"""
    regime = row_df[regime_col].iloc[0]
    X = row_df[feature_cols].values
    models = regime_models[regime]["models"]
    preds = {}
    for q in quantiles:
        preds[q] = max(models[q].predict(X)[0], 0.0)
    return preds

def calibrate_scale(val_df, actual_col, pred_col, target_coverage, regime_col, floor=0.5, ceiling=3.0):
    """Compute calibration scale for a specific regime"""
    g = val_df[val_df[regime_col] == val_df[regime_col].iloc[-1]]
    if len(g) < 30:
        return 1.0
    actual = g[actual_col].values
    pred = g[pred_col].values
    ratio = actual / np.maximum(pred, 1e-8)
    return float(np.clip(np.quantile(ratio, target_coverage), floor, ceiling))

def apply_conditional_floor(forecast_low, latest_close, model_data):
    """Apply conditional floor based on range persistence"""
    prev_5_days = model_data.iloc[-6:-1].copy()
    prev_5_days['daily_range'] = prev_5_days['high'] - prev_5_days['low']
    
    yesterday_range = prev_5_days['daily_range'].iloc[-1]
    range_median_5d = prev_5_days['daily_range'].median()
    prev_range_vs_median = yesterday_range / range_median_5d
    
    FLOOR_THRESHOLD = 1.0
    FLOOR_SCALE = 0.7
    
    floor_active = prev_range_vs_median >= FLOOR_THRESHOLD
    
    if floor_active:
        llr_floor_pct = (yesterday_range / latest_close) * FLOOR_SCALE
        floor_low = latest_close * (1 - llr_floor_pct)
        forecast_low = min(forecast_low, floor_low)
    
    return forecast_low, floor_active, prev_range_vs_median
