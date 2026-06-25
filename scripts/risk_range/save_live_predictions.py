"""
Save daily predictions and backfill actuals
Called after forecasts are generated
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf

def save_and_backfill(forecast_json, ticker_symbol, csv_filename):
    """
    Save today's prediction and backfill yesterday's actuals
    
    Args:
        forecast_json: Dict containing forecast data
        ticker_symbol: Yahoo Finance ticker (e.g., "^GSPC")
        csv_filename: Path to live predictions CSV
    """
    csv_path = Path(csv_filename)
    
    # Load existing predictions or create new DataFrame
    if csv_path.exists():
        live_preds = pd.read_csv(csv_path)
        live_preds['date'] = pd.to_datetime(live_preds['date'])
    else:
        live_preds = pd.DataFrame(columns=[
            'date', 'close', 'vix', 'regime',
            'high_pred_50', 'high_pred_80',
            'low_pred_80', 'low_pred_90', 'low_pred_95',
            'floor_active', 'model_version',
            'next_high', 'next_low',
            'high_error_80', 'low_error_95',
            'high_contained_80', 'low_contained_95'
        ])
    
    # Add today's prediction if not already present
    forecast_date = pd.to_datetime(forecast_json['based_on_date'])
    
    if forecast_date not in live_preds['date'].values:
        # Parse reference levels
        ref_levels = forecast_json['reference_levels']
        
        new_pred = {
            'date': forecast_date,
            'close': forecast_json['based_on_close'],
            'vix': forecast_json['vix'],
            'regime': forecast_json['regime'],
            'high_pred_50': ref_levels.get('trr_50'),
            'high_pred_80': forecast_json['forecast_high'],
            'low_pred_80': ref_levels.get('llr_80'),
            'low_pred_90': ref_levels.get('llr_90'),
            'low_pred_95': forecast_json['forecast_low'] if forecast_json.get('model_version') == 'v4' else ref_levels.get('llr_95'),
            'floor_active': forecast_json.get('floor_active', False),
            'model_version': forecast_json.get('model_version'),
            'next_high': None,
            'next_low': None,
            'high_error_80': None,
            'low_error_95': None,
            'high_contained_80': None,
            'low_contained_95': None
        }
        
        # For Nasdaq V5, add 97th percentile
        if forecast_json.get('model_version') == 'v5':
            new_pred['low_pred_97'] = forecast_json['forecast_low']
        
        live_preds = pd.concat([live_preds, pd.DataFrame([new_pred])], ignore_index=True)
        print(f"✅ Added prediction for {forecast_date.date()}")
    
    # Backfill actuals for dates without them
    missing_actuals = live_preds[live_preds['next_high'].isna()].copy()
    
    if len(missing_actuals) > 0:
        # Download recent market data
        end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (missing_actuals['date'].min() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        try:
            market_data = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)
            
            if isinstance(market_data.columns, pd.MultiIndex):
                market_data.columns = [c[0] for c in market_data.columns]
            
            market_data.columns = [c.lower().replace(" ", "_") for c in market_data.columns]
            
            # Backfill actuals
            for idx, row in missing_actuals.iterrows():
                pred_date = row['date']
                next_date = pred_date + timedelta(days=1)
                
                # Find next trading day
                attempts = 0
                while next_date not in market_data.index and attempts < 5:
                    next_date += timedelta(days=1)
                    attempts += 1
                
                if next_date in market_data.index:
                    actual_high = market_data.loc[next_date, 'high']
                    actual_low = market_data.loc[next_date, 'low']
                    
                    live_preds.loc[live_preds['date'] == pred_date, 'next_high'] = actual_high
                    live_preds.loc[live_preds['date'] == pred_date, 'next_low'] = actual_low
                    
                    # Calculate errors
                    high_pred = row['high_pred_80']
                    low_pred = row['low_pred_95']
                    
                    live_preds.loc[live_preds['date'] == pred_date, 'high_error_80'] = abs(high_pred - actual_high)
                    live_preds.loc[live_preds['date'] == pred_date, 'low_error_95'] = abs(low_pred - actual_low)
                    live_preds.loc[live_preds['date'] == pred_date, 'high_contained_80'] = float(actual_high <= high_pred)
                    live_preds.loc[live_preds['date'] == pred_date, 'low_contained_95'] = float(actual_low >= low_pred)
                    
                    print(f"✅ Backfilled actuals for {pred_date.date()}")
        
        except Exception as e:
            print(f"⚠️  Could not backfill actuals: {e}")
    
    # Save updated CSV
    live_preds = live_preds.sort_values('date', ascending=False)
    live_preds.to_csv(csv_path, index=False)
    print(f"💾 Saved to {csv_path}")
    
    # Print recent performance
    recent = live_preds.dropna(subset=['next_high', 'next_low']).head(20)
    if len(recent) > 0:
        print(f"\n📊 Last {len(recent)} Days Performance:")
        print(f"   High Coverage: {recent['high_contained_80'].mean()*100:.1f}%")
        print(f"   Low Coverage:  {recent['low_contained_95'].mean()*100:.1f}%")
        print(f"   High MAE: {recent['high_error_80'].mean():.1f} pts")
        print(f"   Low MAE:  {recent['low_error_95'].mean():.1f} pts")

def main():
    """Run live predictions tracking"""
    import json
    from pathlib import Path
    
    base_path = Path(__file__).parent.parent.parent / "Risk_Range_Data" / "forecasts"
    
    # Process SPX
    spx_json_path = base_path / "latest_spx_forecast.json"
    spx_csv_path = base_path / "spx_live_predictions_v4.csv"
    
    if spx_json_path.exists():
        print("\n" + "="*60)
        print("📊 SPX Live Track Record")
        print("="*60)
        with open(spx_json_path) as f:
            spx_forecast = json.load(f)
        
        if spx_forecast.get('status') == 'success':
            save_and_backfill(spx_forecast, "^GSPC", spx_csv_path)
    
    # Process Nasdaq
    nasdaq_json_path = base_path / "latest_nasdaq_forecast.json"
    nasdaq_csv_path = base_path / "nasdaq_live_predictions_v5.csv"
    
    if nasdaq_json_path.exists():
        print("\n" + "="*60)
        print("💻 Nasdaq Live Track Record")
        print("="*60)
        with open(nasdaq_json_path) as f:
            nasdaq_forecast = json.load(f)
        
        if nasdaq_forecast.get('status') == 'success':
            save_and_backfill(nasdaq_forecast, "^IXIC", nasdaq_csv_path)

if __name__ == "__main__":
    main()
