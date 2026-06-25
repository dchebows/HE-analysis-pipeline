"""
Daily Risk Range Forecast Runner
Called by GitHub Actions to generate SPX and Nasdaq forecasts
"""
import json
import os
import sys
from pathlib import Path

# Add the risk_range directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from spx_forecast import generate_spx_forecast
from nasdaq_forecast import generate_nasdaq_forecast

def main():
    print("=" * 60)
    print("DAILY RISK RANGE FORECAST")
    print("=" * 60)
    print()
    
    # Ensure output directory exists
    output_dir = Path(__file__).parent.parent.parent / "Risk_Range_Data" / "forecasts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate SPX forecast
    print("📊 Generating SPX forecast...")
    spx_result = generate_spx_forecast()
    
    if spx_result['status'] == 'success':
        print(f"✅ SPX forecast complete")
        print(f"   Based on: {spx_result['based_on_date']} close = {spx_result['based_on_close']:.2f}")
        print(f"   Forecasting: {spx_result['forecast_date']}")
        print(f"   Range: {spx_result['forecast_low']:.2f} - {spx_result['forecast_high']:.2f}")
        print(f"   VIX: {spx_result['vix']:.2f} | Regime: {spx_result['regime']}")
    else:
        print(f"❌ SPX forecast failed: {spx_result['error_message']}")
    
    # Save SPX forecast
    spx_path = output_dir / "latest_spx_forecast.json"
    with open(spx_path, 'w') as f:
        json.dump(spx_result, f, indent=2)
    print(f"   Saved to: {spx_path}")
    print()
    
    # Generate Nasdaq forecast
    print("💻 Generating Nasdaq forecast...")
    nasdaq_result = generate_nasdaq_forecast()
    
    if nasdaq_result['status'] == 'success':
        print(f"✅ Nasdaq forecast complete")
        print(f"   Based on: {nasdaq_result['based_on_date']} close = {nasdaq_result['based_on_close']:.2f}")
        print(f"   Forecasting: {nasdaq_result['forecast_date']}")
        print(f"   Range: {nasdaq_result['forecast_low']:.2f} - {nasdaq_result['forecast_high']:.2f}")
        print(f"   VXN: {nasdaq_result['vix']:.2f} | Regime: {nasdaq_result['regime']}")
    else:
        print(f"❌ Nasdaq forecast failed: {nasdaq_result['error_message']}")
    
    # Save Nasdaq forecast
    nasdaq_path = output_dir / "latest_nasdaq_forecast.json"
    with open(nasdaq_path, 'w') as f:
        json.dump(nasdaq_result, f, indent=2)
    print(f"   Saved to: {nasdaq_path}")
    print()
    
    print("=" * 60)
    print("✅ Daily forecast complete!")
    print("=" * 60)
    
    # Exit with error if either forecast failed
    if spx_result['status'] != 'success' or nasdaq_result['status'] != 'success':
        exit(1)

if __name__ == "__main__":
    main()
