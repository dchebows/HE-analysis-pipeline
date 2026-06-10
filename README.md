# HE-analysis-pipeline
CRR
# 📊 Hedgeye Risk Range Analysis Pipeline

Automated data pipeline for processing Hedgeye Risk Range data and generating trading signals using GitHub Actions.

## 🎯 Overview

This project provides two automated workflows:

1. **ETL Pipeline** - Processes Hedgeye Risk Range HTML files and enriches them with market data
2. **CRR Analysis** - Generates daily trading signals and gamma exposure metrics

Both workflows run automatically Monday-Friday and commit results back to the repository.

---

## 🏗️ Architecture
┌─────────────────────────────────────────────────────────────────┐ │ HEDGEYE HTML FILES │ │ (uploaded to 00_raw_html/) │ └────────────────────────────┬────────────────────────────────────┘ ▼ ┌────────────────────┐ │ ETL PIPELINE │ │ (Mon-Fri 6am EST) │ └────────┬───────────┘ ▼ ┌──────────────┴──────────────┐ ▼ ▼ ┌─────────────────┐ ┌──────────────────┐ │ STAGE 1 & 2: │ │ STAGE 3 & 4: │ │ HTML → Master │────────→ │ Tickers → ML │ │ CSV │ │ Training Data │ └─────────────────┘ └────────┬─────────┘ ▼ ┌───────────────────────┐ │ CRR ANALYSIS │ │ (Mon-Fri 7pm EST) │ │ • SPX Gamma │ │ • Throttle Metrics │ │ • Trading Signals │ └───────────┬───────────┘ ▼ ┌───────────────────────┐ │ STREAMLIT DASHBOARD │ │ (displays results) │ └───────────────────────┘
---

## 📂 Repository Structure
HE-analysis-pipeline/ ├── .github/workflows/ # GitHub Actions workflows │ ├── etl_pipeline.yml # ETL automation │ └── crr_analysis.yml # CRR signal generation │ ├── scripts/ # Python scripts │ └── etl_pipeline.py # ETL processing logic │ ├── Risk_Range_Data/ # Data storage │ ├── 00_raw_html/ # Input: Hedgeye HTML files │ ├── 01_processed/ # Individual daily CSVs │ ├── 02_master/ # Consolidated master CSV │ ├── 03_tickers/ # Per-ticker subsets │ ├── 04_enriched/ # ML-ready enriched data │ └── logs/ # Execution logs │ ├── CRR_v7.py # CRR analysis script ├── app.py # Streamlit dashboard │ ├── requirements.txt # Full dependencies (GitHub Actions) ├── requirements_streamlit.txt # Minimal deps (Streamlit Cloud) │ ├── output.csv # Daily analysis results ├── spx_gamma.json # SPX gamma metrics └── throttle_history.csv # Historical throttle data
---

## 🚀 Quick Start

### Prerequisites

- GitHub account with Actions enabled
- Hedgeye Risk Range subscription (for HTML files)
- Streamlit Cloud account (optional, for dashboard)

### Setup

1. **Clone or fork this repository**

2. **Upload Hedgeye HTML files:**
   - Navigate to `Risk_Range_Data/00_raw_html/`
   - Upload HTML files (format: `MONTH DD, YYYY.html`)
   - ETL workflow auto-triggers

3. **Monitor workflows:**
   - Go to **Actions** tab
   - Watch ETL and CRR workflows execute
   - Results auto-commit to repository

4. **Access results:**
   - **Trading signals:** `output.csv`
   - **SPX gamma:** `spx_gamma.json`
   - **Enriched data:** `Risk_Range_Data/04_enriched/`

---

## 🔄 Workflows

### 1️⃣ ETL Pipeline - Risk Range Data

**Trigger:**
- Schedule: Mon-Fri at 6:00 AM EST
- Manual: Via Actions tab
- Auto: When HTML files uploaded to `00_raw_html/`

**Process:**

#### Stage 1: HTML Parsing
- Extracts risk range tables from Hedgeye HTML files
- Parses: `INDEX`, `BUY TRADE`, `SELL TRADE`, `PREV. CLOSE`, `TREND`
- Outputs: Individual CSVs in `01_processed/`

#### Stage 2: Master Aggregation
- Combines all processed CSVs into single master file
- Deduplicates by date + ticker
- Sorts chronologically
- Outputs: `02_master/risk_ranges_master.csv`

#### Stage 3: Ticker Subsetting
- Creates individual CSV per tracked ticker:
  - `SPX`, `GOLD`, `UST10Y`, `COMPQ`, `RUT`, `VIX`, `USD`, `AAPL`, `BITCOIN`
- Outputs: 9 files in `03_tickers/`

#### Stage 4: Enrichment
- Downloads Yahoo Finance historical data (since 2017)
- Adds OHLC prices (Open, High, Low, Close)
- Adds volatility indices (VIX, GVZ, etc.)
- Creates training-compatible column names
- Outputs: 9 enriched files in `04_enriched/`

**Smart Detection:**
- Only processes new HTML files
- Skips enrichment if data unchanged
- Tracks processed files in `processed_files.txt`

**Runtime:** ~10-15 minutes

---

### 2️⃣ CRR Analysis - Trading Signals

**Trigger:**
- Schedule: Mon-Fri at 7:00 PM EST
- Manual: Via Actions tab

**Process:**

#### Data Collection
- Downloads latest prices via Yahoo Finance
- Fetches SPX options chain from CBOE
- Calculates 500 days of historical data

#### SPX Gamma Calculation
- Computes gamma exposure across strike range
- Identifies gamma flip point
- Measures net dealer positioning

#### Signal Generation
- **Signal Strength Score** (-100 to +100)
  - Layers: Trend, Risk Range, Bands, Volatility, Momentum
- **Status Classification**
  - Bull signals: MAX BULL, STRONG BULL, BULL INTACT, etc.
  - Bear signals: MAX BEAR, STRONG BEAR, RECOVERY WATCH, etc.
- **Warning Flags**
  - Trade/Trend flips, VIX spikes, RSI extremes

#### Gamma Throttle
- Volatility suppression metric
- Combines distance from flip + net GEX
- Regime classification (Positive/Negative gamma)
- Position sizing recommendations

**Outputs:**
- `output.csv` - Full analysis (13 tickers)
- `spx_gamma.json` - SPX metrics + throttle
- `throttle_history.csv` - Historical time series

**Runtime:** ~3-5 minutes

---

## ⚙️ Configuration

### ETL Pipeline (`scripts/etl_pipeline.py`)

Yahoo Finance Mappings:
**Tracked Tickers:**
```python
CONFIG = {
    'tracked_tickers': [
        'UST10Y', 'SPX', 'COMPQ', 'RUT', 'VIX',
        'USD', 'GOLD', 'AAPL', 'BITCOIN'
    ]
}

'yahoo_tickers': {
    'SPX': '^GSPC',
    'GOLD': 'GC=F',
    'UST10Y': '^TNX',
    # ...
}

Enrichment Settings:
'enrichment': {
    'start_date': '2017-01-02',  # Historical data start
    'max_retries': 3,             # Yahoo Finance retries
}
Risk Range Calculation:
ExamplePython
sigma_u = 1.4  # Upper band multiplier
sigma_l = 1.8  # Lower band multiplier
Signal Strength Layers:
Layer 1: Trend Alignment (±30 points)
Layer 2: Risk Range Position (±25 points)
Layer 3: Band Pattern (±20 points)
Layer 4: Volatility Regime (±15 points)
Layer 5: Momentum Confirmation (±10 points)
📊 Data Outputs
Enriched CSVs (04_enriched/)
Training-ready format with columns:
Column
Description
Date
Trading date (MM/DD/YYYY)
TICKER
Asset ticker
BUY TRADE
Hedgeye lower risk range
SELL TRADE
Hedgeye upper risk range
PREV. CLOSE
Previous close price
TREND
Hedgeye trend (BULLISH/BEARISH/NEUTRAL)
{PREFIX}_Open
Yahoo Finance open price
{PREFIX}_High
Yahoo Finance high
{PREFIX}_Low
Yahoo Finance low
{PREFIX}_Close
Yahoo Finance close
{VOL}_Close
Volatility index close
NEEDS_MANUAL_UPDATE
Flag for missing data
Example for SPX:
GSPC_Open, GSPC_High, GSPC_Low, GSPC_Close
VIX_Close (volatility)
Analysis Output (output.csv)
Column
Description
Ticker
Asset symbol
Close
Current price
Bottom End / Top End
Calculated risk ranges
Trade / Trend
15-day / 63-day signals
SS_Score
Signal Strength (-100 to +100)
SS_Status
Classification (MAX BULL, etc.)
SS_Action
Recommended action
RVOL_1M / RVOL_3M
Realized volatility
RSI
Relative Strength Index
Beta_1Y
1-year beta vs SPX
Warn_Flags
Active warnings
SPX Gamma (spx_gamma.json)
ExampleJSON
{
  "spx_gamma": -2.45,          // Net gamma (billions)
  "spx_spot": 5432.10,         // SPX spot price
  "spx_flip": 5380.25,         // Gamma flip point
  "gamma_throttle": -15.3,     // Volatility throttle
  "rv_10day": 12.5,            // 10-day realized vol
  "vix": 14.2,                 // VIX level
  "regime": "NEGATIVE GAMMA",  // Current regime
  "position_size": "25% of normal",
  "vol_signal": "BUY VOLATILITY",
  "dir_signal": "FOLLOW THE TREND"
}
🛠️ Development
Local Testing
ETL Pipeline:
Example
# Install dependencies
pip install -r requirements.txt

# Run ETL
python scripts/etl_pipeline.py
CRR Analysis:
Example
# Run analysis
python CRR_v7.py
Streamlit Dashboard:
Example
# Install Streamlit deps
pip install -r requirements_streamlit.txt

# Run locally
streamlit run app.py
Manual Workflow Triggers
Go to Actions tab
Select workflow (ETL or CRR)
Click "Run workflow"
Select main branch
Click "Run workflow"
🐛 Troubleshooting
ETL Pipeline Issues
Problem: HTML parsing fails
Example
ERROR: Table extraction failed
Solution: Check HTML format, ensure class='dtr-table' exists
Problem: No files processed
Example
✅ Everything up-to-date! No processing needed.
Solution: Check processed_files.txt, remove entries to reprocess
Problem: Yahoo Finance download fails
Example
ERROR: Failed after 3 attempts
Solution: Check ticker mapping, verify Yahoo Finance is accessible
CRR Analysis Issues
Problem: No data in output.csv
Example
ERROR: Could not download data
Solution: Check internet connectivity, Yahoo Finance status
Problem: SPX gamma calculation fails
Example
ERROR: Error calculating SPX gamma
Solution: Check CBOE API availability, verify options chain format
Workflow Permission Issues
Problem: Commit failed
Example
fatal: pathspec 'Risk_Range_Data/**/*.csv' did not match any files
Solution: Ensure workflow has write permissions, check folder structure
📈 Streamlit Dashboard
Live dashboard displaying:
SPX Index with daily change
VIX status (Investable/Chop/F Bucket)
Machine status (Systematic Buying/Selling)
SPX Gamma Volatility Throttle
Signal Strength rankings
Full analysis table with color coding
Deployment:
Connect repository to Streamlit Cloud
Set requirements file: requirements_streamlit.txt
Main file: app.py
Deploy!
URL: https://share.streamlit.io/ (configure in your account)
🔐 Security
No API keys stored in repository
GitHub Actions uses temporary tokens
Workflows run in isolated containers
All data committed to repository (public/private as configured)
📝 Logging
ETL Pipeline Logs:
Location: Risk_Range_Data/logs/etl_YYYYMMDD_HHMMSS.log
Retention: 30 days in GitHub Actions artifacts
Contains: Stage-by-stage execution details
Workflow Logs:
Location: Actions tab → Workflow run
Retention: 90 days (GitHub default)
Contains: Complete stdout/stderr
🚦 Workflow Status
Check current status:
Actions tab: Real-time workflow execution
Commit history: Auto-generated commit messages
File timestamps: Last updated times
Log files: Detailed execution history
🔮 Future Enhancements
 Backtesting framework for signal validation
 Machine learning model training automation
 Email/Slack notifications for high-conviction signals
 Additional data sources (FRED, Quandl, etc.)
 Portfolio optimization integration
 Risk management automation
 Real-time alerts via webhooks
📚 Resources
Hedgeye: https://hedgeye.com/
Yahoo Finance API: https://python-yahoofinance.readthedocs.io/
CBOE Options Data: https://www.cboe.com/
GitHub Actions: https://docs.github.com/en/actions
Streamlit: https://docs.streamlit.io/
🤝 Contributing
This is a personal trading pipeline. Feel free to fork and adapt for your own use.
⚖️ License
This project is for personal use. Market data is sourced from public APIs.
Disclaimer: This tool is for informational purposes only. Not financial advice. Trade at your own risk.
📞 Support
For issues or questions:
Check Troubleshooting section above
Review workflow logs in Actions tab
Check Risk_Range_Data/logs/ for ETL details
🎯 Version History
v2.0 (Current)
✅ GitHub Actions automation
✅ Dual workflow system (ETL + CRR)
✅ SPX gamma throttle integration
✅ Complete historical enrichment
✅ Streamlit dashboard
v1.0 (Legacy)
Google Colab-based manual workflow
Local execution only
Last Updated: June 2026
Status: ✅ Production Ready
Made with 📊 for systematic trading

# 💼 Portfolio Signals Daily Update

## Overview

The **Portfolio Signals Daily Update** is an automated trading signal system that generates daily position sizing and action recommendations for a multi-asset portfolio. It runs every weekday at **7:05 PM EST** via GitHub Actions, processing enriched market data through sophisticated quantitative models.

## What It Does

This system analyzes **5 core assets** and produces:
- **Buy/Sell/Hold signals** with position sizing recommendations
- **Danger scores** (0-100) for risk management
- **Performance metrics** (Sharpe ratio, CAGR, Max Drawdown)
- **Detailed signal breakdowns** showing what's driving each recommendation

## Assets Covered

| Asset | Name | Ticker |
|-------|------|--------|
| SPX | S&P 500 Index | ^GSPC |
| GOLD | Gold Futures | GC=F |
| COMPQ | NASDAQ Composite | ^IXIC |
| RUT | Russell 2000 | ^RUT |
| USD | US Dollar Index | DX-Y.NYB |

## How It Works

### 1. Data Pipeline Flow

Enriched CSVs (from ETL Pipeline) ↓ Portfolio Orchestrator (Python Script) ↓ V5B Trend Model → Signals V1 Fractal Model → Signals V6 Ensemble → Combined Trend Trade Signal Model → Short-term signals ↓ Danger Score Calculation (7 inputs) ↓ D1 Strategy Backtest → Position sizing ↓ Output Files (CSV + TXT) ↓ Streamlit Dashboard (Auto-refresh)

### 2. Model Architecture

**V5B Trend Model:**
- ATH distance analysis
- Rolling high momentum
- Rate of change
- Volatility regime detection
- VIX integration
- Level slope analysis

**V6 Ensemble:**
- Context-aware model switching
- ATH proximity logic
- Volatility regime adaptation
- Confirmation system with hysteresis

**Trade Signal Model:**
- Keltner channel-based levels
- Short-term momentum
- Dynamic position sizing

**Danger Score System:**
- V5B score contribution
- Score velocity
- Trend/Trade alignment
- VIX levels and acceleration
- Market drawdown
- **Output:** 0-100 score (higher = more danger)

### 3. Position Sizing Logic

**Dynamic Weighting:**
- Danger 0-25: 100% position (SAFE)
- Danger 25-45: 70-100% position (WATCH)
- Danger 45-65: 35-70% position (RISK)
- Danger 65-80: 15-35% position (DANGER)
- Danger 80-100: 10-15% position (CRISIS)

**Safety Constraints:**
- Maximum daily increase: 18%
- Maximum daily decrease: 40%
- Minimum position: 10%
- Circuit breaker at -6% portfolio drawdown
- Emergency reduction at -8% portfolio drawdown

## Automated Schedule

| Time (EST) | Action | Output |
|------------|--------|--------|
| 7:00 PM | ETL Pipeline runs | Enriched CSVs updated |
| 7:05 PM | Portfolio Orchestrator runs | Signals generated |
| 7:08 PM | Files committed to GitHub | `portfolio_summary.csv`, `portfolio_signals.txt` |
| 8:00 PM | Streamlit cache refreshes | Dashboard updates |

**Runs:** Monday-Friday (market days only)

## Output Files

### 1. `portfolio_summary.csv`

Machine-readable CSV with columns:
- Asset, Name, Last_Date, Close, Trend, V5B_Score
- Action, Action_Icon, Delta_Icon
- Current_Weight, Target_Weight, Weight_Change
- Danger_Score, Zone, Zone_Icon
- Sharpe, CAGR, Max_DD
- Invested_Dollars, Cash_Dollars, Dollar_Change

### 2. `portfolio_signals.txt`

Human-readable text report with:
- **Summary table** - Quick overview of all assets
- **Detailed breakdowns** - Signal components for each asset
- **Action recommendations** - Specific buy/sell dollar amounts
- **Risk zones** - Current danger level classification
- **Performance context** - Backtest metrics

## Streamlit Dashboard Integration

### Location
**Tab:** 💼 Portfolio Signals (second tab)

### Features
- **Summary metrics** - Average danger, target positions, action counts
- **Interactive table** - Sortable, filterable asset list
- **Expandable details** - Click to see full breakdown per asset
- **Download buttons** - Export CSV or TXT reports
- **Real-time updates** - Auto-refresh hourly

### How to Use
1. Open Streamlit app
2. Click **"💼 Portfolio Signals"** tab
3. Review summary table:
   - 🟢 = BUY signal
   - 🔴 = SELL signal
   - ⏸️ = HOLD signal
   - 🟡 = Light adjustment
4. Check **Danger Score** and **Zone** for risk context
5. Expand asset rows for detailed signal breakdown
6. Download reports for offline analysis

## Technical Implementation

### Script: `portfolio_orchestrator.py`

**Location:** Root directory

**Key Functions:**
- `trend_v5b_model()` - V5B trend detection
- `v6_ohlc_context_switch()` - Ensemble logic
- `trade_signal_model()` - Short-term signals
- `compute_danger_score()` - Risk assessment
- `run_d1_strategy()` - Position sizing backtest
- `generate_text_report()` - Human-readable output

**Dependencies:**
- pandas
- numpy
- yfinance (not used directly, data from enriched CSVs)
- scipy

### Workflow: `.github/workflows/portfolio_daily.yml`

**Trigger:** 
- Schedule: `5 23 * * 1-5` (7:05 PM EST, Mon-Fri)
- Manual: workflow_dispatch

**Steps:**
1. Checkout repository
2. Set up Python 3.11
3. Install dependencies
4. Run `portfolio_orchestrator.py`
5. Verify output files exist
6. Commit and push to GitHub
7. Upload artifacts (backup)

## Risk Management Features

### Built-in Safety Systems

**Circuit Breaker:**
- Monitors portfolio drawdown in real-time
- Reduces exposure at -6% drawdown
- Emergency reduction at -8% drawdown
- Auto-recovery when back above -3%

**Asymmetric Position Limits:**
- Faster selling than buying (risk management)
- Prevents overexposure during rallies
- Allows quick exit during downturns

**Danger Score Smoothing:**
- Multi-day confirmation required
- Hysteresis prevents whipsaws
- Score velocity tracking

## Performance Metrics

Based on backtests from 2017-01-01 to present:

| Asset | Sharpe Ratio | CAGR | Max Drawdown |
|-------|--------------|------|--------------|
| SPX | 1.08 | 9.8% | -9.8% |
| GOLD | 1.04 | 13.2% | -8.9% |
| COMPQ | 1.05 | 12.1% | -11.6% |
| RUT | 0.86 | 8.2% | -8.4% |
| USD | -0.28 | 0.8% | -7.6% |

**Portfolio Average Sharpe:** 0.75+

## Interpreting Signals

### Action Types

| Action | Meaning | Typical Scenario |
|--------|---------|------------------|
| 🟢 BUY | Increase position significantly (>3%) | Strong bullish signals, low danger |
| 🟡 LIGHT BUY | Small increase (1-3%) | Moderately positive signals |
| ⏸️ HOLD | No change needed (<1%) | Position already optimal |
| 🟡 LIGHT SELL | Small decrease (1-3%) | Moderately negative signals |
| 🔴 SELL | Decrease position significantly (>3%) | Bearish signals, high danger |

### Danger Zones

| Score | Zone | Icon | Meaning |
|-------|------|------|---------|
| 0-25 | SAFE | 🟢 | Low risk, normal positioning |
| 25-45 | WATCH | 🟡 | Moderate risk, start reducing |
| 45-65 | RISK | 🟠 | Elevated risk, defensive positioning |
| 65-80 | DANGER | 🔴 | High risk, minimal exposure |
| 80-100 | CRISIS | 🚨 | Extreme risk, preservation mode |

### Trend Signals

- **BULLISH** - Uptrend confirmed, favor long positions
- **BEARISH** - Downtrend confirmed, reduce or short
- **NEUTRAL** - No clear trend, cautious positioning

## Customization

### Adding New Assets

1. Add enriched CSV to `Risk_Range_Data/04_enriched/`
2. Update `ASSETS_TO_RUN` in `portfolio_orchestrator.py`
3. Add asset configuration to `ASSET_REGISTRY`
4. Commit and workflow will include new asset

### Adjusting Parameters

Edit `portfolio_orchestrator.py`:
- **V5B parameters** - Trend sensitivity
- **Trade parameters** - Short-term signal tuning
- **Danger parameters** - Risk thresholds
- **Position sizing** - Danger-to-weight mapping

### Changing Schedule

Edit `.github/workflows/portfolio_daily.yml`:
```yaml
schedule:
  - cron: '5 23 * * 1-5'  # Current: 7:05 PM EST

Maintenance
Daily Monitoring
Check GitHub Actions for green checkmarks
Verify output files updated with current date
Review Streamlit dashboard for anomalies
Weekly Review
Compare signals to actual market performance
Check for failed workflow runs
Verify enriched CSVs are updating
Monthly Analysis
Review backtest performance metrics
Compare actual vs. predicted results
Adjust parameters if needed
Troubleshooting
Issue: Workflow fails with "File not found"
Cause: Enriched CSVs not created by ETL pipeline
Solution: Run ETL workflow first to generate enriched data
Issue: Signals different from Colab output
Cause: Path-dependent backtest (uses yesterday's position)
Solution: This is expected behavior for live trading
Issue: Streamlit shows old data
Cause: Cache not refreshed
Solution: Press "C" key in Streamlit app → Clear cache
Issue: Missing danger score components
Cause: Missing VIX data in enriched CSVs
Solution: Verify enriched CSVs have VIX_Close column
Credits
Models:
V5B Trend Model - Proprietary distance/momentum composite
V6 Ensemble - Context-aware regime switching
D1 Strategy - Dynamic danger-based allocation
Data Sources:
Hedgeye Risk Range signals (manual HTML upload)
Yahoo Finance OHLC data (automated via ETL)
CBOE VIX/GVZ volatility indices
Infrastructure:
GitHub Actions (automation)
Streamlit Cloud (dashboard hosting)
Python 3.11 (execution environment)
License
This portfolio signal system is part of the HE-analysis-pipeline project.
Last Updated: 2026-06-10
Version: 1.0.0
Status: ✅ Production Ready
