Risk Range Forecasting System
Automated daily S&P 500 and Nasdaq risk range predictions using VIX/VXN regime-aware quantile regression
Image blocked. To view, load content from img.shields.io.
 
Image blocked. To view, load content from img.shields.io.
 
Image blocked. To view, load content from img.shields.io.
📊 Overview
This system generates next-day high/low price forecasts for S&P 500 and Nasdaq Composite indices using machine learning models trained on 5 years of historical data. Forecasts update automatically every weekday at 6:30 PM EST via GitHub Actions and display in a Streamlit dashboard.
Key Features
Asymmetric Protection: Wider downside coverage (95th/97th percentile) vs upside (80th percentile)
Regime-Aware: Separate models for VIX/VXN regimes (investible, chop, get_out)
Conditional Floor: Additional tail protection when range persistence detected
Risk Warnings: Automatic alerts for velocity spikes, regime transitions, anomalies
Fast Loading: Pre-computed forecasts load in <1 second via JSON
🎯 Model Performance
S&P 500 (V4)
Primary Forecast: 80th percentile high / 95th percentile low
Low Coverage: 90.4% (target: 90%)
Tail Day Coverage: 59.3% on 2x+ range days
Width: 33% narrower than benchmark
Nasdaq (V5)
Primary Forecast: 80th percentile high / 97th percentile low
Low Coverage: 92.8% (target: 93%)
Tail Day Coverage: 77.7% on 2x+ range days
Width: 29% narrower than benchmark
🏗️ Architecture
File Structure
Example
HE-analysis-pipeline/
├── scripts/
│   └── risk_range/
│       ├── __init__.py                   # Package initialization
│       ├── feature_engineering.py        # Feature creation (98 features)
│       ├── model_utils.py                # GBM models, calibration
│       ├── spx_forecast.py               # S&P 500 forecasting logic
│       ├── nasdaq_forecast.py            # Nasdaq forecasting logic
│       └── run_daily_forecast.py         # Main orchestrator
├── .github/
│   └── workflows/
│       └── risk_range_daily.yml          # GitHub Actions workflow
├── Risk_Range_Data/
│   └── forecasts/
│       ├── latest_spx_forecast.json      # Current SPX forecast
│       └── latest_nasdaq_forecast.json   # Current Nasdaq forecast
├── app.py                                # Streamlit dashboard (Tab 3)
└── requirements.txt                      # Python dependencies
🔬 Methodology
Data Sources
S&P 500: Yahoo Finance ^GSPC (1990-present)
Nasdaq: Yahoo Finance ^IXIC (2000-present)
VIX/VXN: CBOE volatility indices
VIX/VXN Regimes
Regime
VIX Range
Characteristics
Model Behavior
Investible
< 19 (SPX) / < 20 (Nasdaq)
Low volatility, tight ranges
High confidence, narrow bands
Chop
19-30 (SPX) / 20-30 (Nasdaq)
Elevated volatility
Moderate confidence, wider bands
Get Out
> 30
Extreme volatility, tail risk
Reduced confidence, 2x buffer recommended
Feature Set (98 Features)
Price & Returns (20 features)
Log returns at 1, 2, 3, 5, 10, 20 day horizons
Return acceleration (1-day, 5-day)
Gap, body, intraday range metrics
Range Analysis (28 features)
Rolling range statistics (mean, median, std) at 3, 5, 10, 20 day windows
Range rate of change (1, 3, 5 day)
Range vs median ratios (5, 10, 20 day)
High-low span across multiple timeframes
Volatility Cascade (16 features)
Rolling return volatility at multiple horizons
Volatility ratios (short/long term)
Close distance from SMA (3, 5, 10, 20 day)
VIX/VXN Features (20 features)
VIX returns, range, close location value
Rolling VIX statistics and distance from mean
VIX range vs median ratios
Tail Risk Features (11 features - V4/V5)
VIX velocity (absolute % change) at 1, 2, 3, 5 day horizons
Tail interaction (VIX velocity × range expansion)
VIX up streaks (consecutive up days)
Downside pressure (negative return × VIX velocity)
Regime Interaction (3 features)
Return × VIX, Range × VIX, CLV × VIX return
Model Training
Algorithm: Gradient Boosting Regressor (scikit-learn)
Loss: Quantile regression (asymmetric)
TRR quantiles: 50th, 80th percentile
LLR quantiles: 80th, 90th, 95th (SPX), 97th (Nasdaq)
Estimators: 100 trees
Learning rate: 0.08
Max depth: 3
Min samples: 30 per leaf
Training Window: Rolling 5 years (1,260 trading days)
Calibration:
Recent 126 days (6 months)
Regime-specific scaling factors
Clip range: 0.5x to 3.0x
Conditional Floor
Activated when yesterday's range ≥ 5-day median:
ExamplePython
if (yesterday_range / median_range_5d) >= 1.0:
    floor_low = close × (1 - (yesterday_range / close) × 0.7)
    forecast_low = min(model_prediction, floor_low)
Improves tail day coverage by 0.5-1.0 percentage points.
🚀 Usage
Daily Forecast (Streamlit)
Navigate to your Streamlit app
Click the "🎯 Risk Range" tab
Select "📈 S&P 500" or "💻 Nasdaq" sub-tab
View forecast levels, regime, and risk warnings
Interpreting the Forecast
Example
Based on: 2026-06-25 close = 7,404.22
Forecasting for: 2026-06-26

High (TRR 80):  7,503.69 (+1.34%)   ← 80% chance actual high stays below this
Low (LLR 95):   7,273.74 (-1.76%)   ← 90% chance actual low stays above this
Range Width:       229.95 pts       ← Expected trading range
VIX Regime: 🟢 Investible / 🟡 Chop / 🔴 Get Out
Floor Active: 🛡️ Additional downside protection applied when range persistence detected
Risk Warnings
The system automatically flags:
🚨 High VIX velocity (>15% 1-day change)
⚠️ Regime transition warnings (VIX near thresholds)
📊 Predicted range above 90th percentile for regime
🔴 Get_out regime active (model reliability reduced)
Trading Applications
Use Case
Level to Use
Sell resistance
TRR 80 (forecast high)
Buy support
LLR 95/97 (forecast low)
Stop loss placement
Below LLR 95/97
Position sizing
Adjust based on regime + range width
Options strategies
Use range width for straddle/strangle sizing
⚙️ Configuration
GitHub Actions Workflow
Schedule: Runs automatically at 6:30 PM EST Monday-Friday
Manual Trigger:
Go to Actions → Risk Range Daily Forecast
Click Run workflow
Select branch (usually main)
Click green Run workflow button
Compute Usage: ~4-6 minutes per run (~30 min/week, 1.5% of free tier)
Adjusting Forecast Timing
Edit .github/workflows/risk_range_daily.yml:
ExampleYAML
on:
  schedule:
    - cron: '30 22 * * 1-5'  # 6:30 PM EST = 22:30 UTC (change as needed)
Model Parameters
To adjust quantile levels, edit the forecast files:
spx_forecast.py / nasdaq_forecast.py:
ExamplePython
TRR_QUANTILES = [0.50, 0.80]        # Top Risk Range percentiles
LLR_QUANTILES = [0.80, 0.90, 0.95]  # Lower Risk Range percentiles (SPX)
LLR_QUANTILES = [0.80, 0.90, 0.95, 0.97]  # Nasdaq includes 97th
Conditional Floor:
ExamplePython
FLOOR_THRESHOLD = 1.0   # Activate when yesterday ≥ 1.0x median
FLOOR_SCALE = 0.7       # Use 70% of yesterday's range as floor
🔧 Development
Local Testing
Example
# Clone the repo
git clone https://github.com/dchebows/HE-analysis-pipeline.git
cd HE-analysis-pipeline

# Install dependencies
pip install -r requirements.txt

# Run forecast manually
python scripts/risk_range/run_daily_forecast.py

# Check outputs
cat Risk_Range_Data/forecasts/latest_spx_forecast.json
cat Risk_Range_Data/forecasts/latest_nasdaq_forecast.json
Running Streamlit Locally
Example
streamlit run app.py
Navigate to http://localhost:8501 → Risk Range tab
Adding New Features
Add feature logic to feature_engineering.py:
ExamplePython
def add_new_feature(data):
    data["my_feature"] = ...
    return data
Update feature list in spx_forecast.py and nasdaq_forecast.py:
ExamplePython
feature_cols = [
    # ... existing features ...
    "my_feature",  # Add here
]
Test locally before pushing:
Example
python scripts/risk_range/run_daily_forecast.py
Debugging Forecast Errors
If workflow fails, check:
GitHub Actions logs: Actions → Risk Range Daily Forecast → Latest run
JSON output: Check Risk_Range_Data/forecasts/*.json for "status": "error"
Common issues:
Yahoo Finance API changes
Missing data for specific dates
Pandas version incompatibility (fillna vs ffill)
📈 JSON Output Format
ExampleJSON
{
  "ticker": "^GSPC",
  "forecast_date": "2026-06-26",
  "based_on_date": "2026-06-25",
  "based_on_close": 7404.22,
  "vix": 19.49,
  "regime": "chop",
  "forecast_high": 7503.69,
  "forecast_low": 7273.74,
  "high_pct": 1.34,
  "low_pct": -1.76,
  "range_width": 229.95,
  "floor_active": true,
  "reference_levels": {
    "trr_50": 7455.45,
    "llr_90": 7290.05,
    "llr_80": 7299.93
  },
  "risks": [
    "Range persistence detected (1.09x median) — floor applied",
    "Predicted range (3.11%) above 90th percentile for regime"
  ],
  "timestamp": "2026-06-25 18:30:00 EST",
  "model_version": "v4",
  "status": "success"
}
🐛 Troubleshooting
Streamlit Shows "Error Loading Forecast"
Cause: Old cached data or JSON not yet generated
Fix:
Click hamburger menu (☰) → Clear cache
Refresh page
Wait for workflow to run (6:30 PM EST)
Workflow Fails with Import Error
Cause: Relative import issues
Fix: Ensure all imports in spx_forecast.py and nasdaq_forecast.py use absolute imports:
ExamplePython
from feature_engineering import add_features  # ✅ Correct
from .feature_engineering import add_features  # ❌ Wrong
"NDFrame.fillna() got unexpected keyword argument 'method'"
Cause: Pandas 2.0+ deprecated fillna(method='ffill')
Fix: Use ffill() directly:
ExamplePython
out = out.ffill()  # ✅ Correct
out = out.fillna(method='ffill')  # ❌ Deprecated
Forecast Always Shows Same Date
Cause: Cached forecast from previous day
Fix: Wait 1 hour (cache TTL) or clear Streamlit cache manually
📚 Dependencies
Example
yfinance>=0.2.28          # Market data download
pandas>=2.0.0             # Data manipulation
numpy>=1.24.0             # Numerical computing
scipy>=1.10.0             # Statistical functions
scikit-learn>=1.3.0       # Machine learning models
streamlit>=1.32.0         # Dashboard UI
plotly>=5.0.0             # Interactive charts
requests>=2.31.0          # HTTP requests
🔮 Future Enhancements
Planned Features
 Historical comparison charts (model vs benchmark)
 Live track record with daily predictions CSV
 Performance metrics dashboard (MAE, coverage by regime)
 Email/Slack alerts for high-risk conditions
 Russell 2000 (^RUT) forecasts
 Individual stock forecasts (requires separate validation)
Potential Model Improvements
 98th/99th percentile for crisis conditions
 Intraday high/low prediction (vs next-day)
 Options-implied volatility features
 Sector rotation signals for Nasdaq
 Ensemble with simple statistical models
📄 License
This project is part of the HE Analysis Pipeline. See main repository for license details.
🤝 Contributing
This is a personal project, but suggestions welcome via GitHub Issues.
📞 Support
For questions or issues:
Check this README first
Review GitHub Actions logs
Inspect JSON output files
Open a GitHub Issue with error details
Last Updated: 2026-06-25
Model Versions: SPX V4, Nasdaq V5
Maintained by: dchebows
Quick Reference Card
Metric
S&P 500
Nasdaq
Ticker
^GSPC
^IXIC
Volatility Index
VIX
VXN
Model Version
V4
V5
Primary Forecast
80H / 95L
80H / 97L
Training Window
5 years
5 years
Calibration Window
126 days
126 days
Update Time
6:30 PM EST
6:30 PM EST
Runtime
~4 minutes
~4 minutes
Investible Threshold
VIX < 19
VXN < 20
Get Out Threshold
VIX > 30
VXN > 30
