"""
Save daily predictions and backfill actuals
Works with original column format: Date, vix_close, vix_regime, etc.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf

def save_and_backfill(forecast_json, ticker_symbol, csv_filename):
    """
    Save today's prediction and backfill yesterday's actuals
    Works with original file format
    
    Args:
        forecast_json: Dict containing forecast data
        ticker_symbol: Yahoo Finance ticker (e.g., "^GSPC")
        csv_filename: Path to live predictions CSV
    """
    csv_path = Path(csv_filename)
    
    # Load existing predictions or create new DataFrame
    if csv_path.exists():
        live_preds = pd.read_csv(csv_path)
        # Handle original column name
        if 'Date' in live_preds.columns:
            live_preds['Date'] = pd.to_datetime(live_preds['Date'])
        elif 'date' in live_preds.columns:
            live_preds = live_preds.rename(columns={'date': 'Date'})
            live_preds['Date'] = pd.to_datetime(live_preds['Date'])
    else:
        # Create new file with original column structure
        live_preds = pd.DataFrame(columns=[
            'Date', 'close', 'next_high', 'next_low', 
            'trr_next', 'llr_next', 
            'vix_close', 'vix_regime',
            'trr_50_raw', 'trr_50', 'high_pred_50',
            'trr_80_raw', 'trr_80', 'high_pred_80',
            'llr_80_raw', 'llr_80', 'low_pred_80',
            'llr_90_raw', 'llr_90', 'low_pred_90',
            'llr_95_raw', 'llr_95', 'low_pred_95'
        ])
    
    # Add today's prediction if not already present
    forecast_date = pd.to_datetime(forecast_json['based_on_date'])
    
    if forecast_date not in live_preds['Date'].values:
        # Parse reference levels
        ref_levels = forecast_json['reference_levels']
        
        # Map new JSON format → old CSV format
        new_pred = {
            'Date': forecast_date,
            'close': forecast_json['based_on_close'],
            'next_high': None,
            'next_low': None,
            'trr_next': None,
            'llr_next': None,
            'vix_close': forecast_json['vix'],
            'vix_regime': forecast_json['regime'],
            'trr_50_raw': None,  # Not in new forecasts
            'trr_50': None,
            'high_pred_50': ref_levels.get('trr_50'),
            'trr_80_raw': None,
            'trr_80': None,
            'high_pred_80': forecast_json['forecast_high'],
            'llr_80_raw': None,
            'llr_80': None,
            'low_pred_80': ref_levels.get('llr_80'),
            'llr_90_raw': None,
            'llr_90': None,
            'low_pred_90': ref_levels.get('llr_90'),
            'llr_95_raw': None,
            'llr_95': None,
            'low_pred_95': forecast_json['forecast_low']
        }
        
        live_preds = pd.concat([live_preds, pd.DataFrame([new_pred])], ignore_index=True)
        print(f"✅ Added prediction for {forecast_date.date()}")
    
    # Backfill actuals for dates without them
    missing_actuals = live_preds[live_preds['next_high'].isna()].copy()
    
    if len(missing_actuals) > 0:
        # Download recent market data
        end_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (missing_actuals['Date'].min() - timedelta(days=5)).strftime('%Y-%m-%d')
        
        try:
            market_data = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)
            
            if isinstance(market_data.columns, pd.MultiIndex):
                market_data.columns = [c[0] for c in market_data.columns]
            
            market_data.columns = [c.lower().replace(" ", "_") for c in market_data.columns]
            
            # Backfill actuals
            for idx, row in missing_actuals.iterrows():
                pred_date = row['Date']
                next_date = pred_date + timedelta(days=1)
                
                # Find next trading day
                attempts = 0
                while next_date not in market_data.index and attempts < 5:
                    next_date += timedelta(days=1)
                    attempts += 1
                
                if next_date in market_data.index:
                    actual_high = market_data.loc[next_date, 'high']
                    actual_low = market_data.loc[next_date, 'low']
                    
                    live_preds.loc[live_preds['Date'] == pred_date, 'next_high'] = actual_high
                    live_preds.loc[live_preds['Date'] == pred_date, 'next_low'] = actual_low
                    
                    # Calculate trr_next and llr_next
                    pred_close = row['close']
                    live_preds.loc[live_preds['Date'] == pred_date, 'trr_next'] = (actual_high - pred_close) / pred_close
                    live_preds.loc[live_preds['Date'] == pred_date, 'llr_next'] = (pred_close - actual_low) / pred_close
                    
                    print(f"✅ Backfilled actuals for {pred_date.date()}")
        
        except Exception as e:
            print(f"⚠️  Could not backfill actuals: {e}")
    
    # Save updated CSV (sort by date descending)
    live_preds = live_preds.sort_values('Date', ascending=False)
    live_preds.to_csv(csv_path, index=False)
    print(f"💾 Saved to {csv_path}")
    
    # Print recent performance
    recent = live_preds.dropna(subset=['next_high', 'next_low']).head(20)
    if len(recent) > 0:
        high_contained = (recent['next_high'] <= recent['high_pred_80']).mean() * 100
        low_contained = (recent['next_low'] >= recent['low_pred_95']).mean() * 100
        high_mae = (recent['high_pred_80'] - recent['next_high']).abs().mean()
        low_mae = (recent['low_pred_95'] - recent['next_low']).abs().mean()
        
        print(f"\n📊 Last {len(recent)} Days Performance:")
        print(f"   High Coverage: {high_contained:.1f}%")
        print(f"   Low Coverage:  {low_contained:.1f}%")
        print(f"   High MAE: {high_mae:.1f} pts")
        print(f"   Low MAE:  {low_mae:.1f} pts")

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
