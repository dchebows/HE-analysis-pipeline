import pandas as pd

# Load your walk-forward predictions
df = pd.read_csv('Risk_Range_Data/forecasts/spx_live_predictions_v4.csv')

# Rename Date to date
df = df.rename(columns={'Date': 'date', 'vix_close': 'vix', 'vix_regime': 'regime'})

# Add missing columns
df['floor_active'] = False  # We don't have this in old data
df['model_version'] = 'v4'

# Calculate errors and containment (if next_high/next_low exist)
if 'next_high' in df.columns and 'next_low' in df.columns:
    df['high_error_80'] = (df['high_pred_80'] - df['next_high']).abs()
    df['low_error_95'] = (df['low_pred_95'] - df['next_low']).abs()
    df['high_contained_80'] = (df['next_high'] <= df['high_pred_80']).astype(float)
    df['low_contained_95'] = (df['next_low'] >= df['low_pred_95']).astype(float)
else:
    df['high_error_80'] = None
    df['low_error_95'] = None
    df['high_contained_80'] = None
    df['low_contained_95'] = None

# Keep only the columns the app needs
keep_cols = [
    'date', 'close', 'vix', 'regime',
    'high_pred_50', 'high_pred_80',
    'low_pred_80', 'low_pred_90', 'low_pred_95',
    'floor_active', 'model_version',
    'next_high', 'next_low',
    'high_error_80', 'low_error_95',
    'high_contained_80', 'low_contained_95'
]

df_clean = df[keep_cols].copy()

# Save
df_clean.to_csv('Risk_Range_Data/forecasts/spx_live_predictions_v4.csv', index=False)
print(f"✅ Saved {len(df_clean)} rows")
print(f"Columns: {list(df_clean.columns)}")
