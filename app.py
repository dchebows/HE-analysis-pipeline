import streamlit as st
import pandas as pd
from datetime import datetime
import json
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import requests

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="CRR Analysis Dashboard",
    page_icon="📊",
    layout="wide"
)

# ============================================================
# DATA LOADING
# ============================================================
CSV_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/output.csv"
PORTFOLIO_CSV_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/portfolio_summary.csv"
PORTFOLIO_TXT_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/portfolio_signals.txt"

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Load data from GitHub CSV and SPX gamma JSON"""
    try:
        df = pd.read_csv(CSV_URL)
        
        # Load SPX gamma data
        SPX_GAMMA_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/spx_gamma.json"
        THROTTLE_HISTORY_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/throttle_history.csv"
        
        import requests
        gamma_response = requests.get(SPX_GAMMA_URL)
        spx_gamma = json.loads(gamma_response.text)
        
        # Load throttle history for charting
        try:
            throttle_history = pd.read_csv(THROTTLE_HISTORY_URL)
            throttle_history['date'] = pd.to_datetime(throttle_history['date'])
        except:
            throttle_history = None
        
        return df, spx_gamma, throttle_history, None
    except Exception as e:
        return None, None, None, str(e)

@st.cache_data(ttl=3600)
def load_portfolio_data():
    """Load portfolio signals data"""
    try:
        portfolio_df = pd.read_csv(PORTFOLIO_CSV_URL)
        
        # Load text report
        import requests
        txt_response = requests.get(PORTFOLIO_TXT_URL)
        portfolio_txt = txt_response.text
        
        return portfolio_df, portfolio_txt, None
    except Exception as e:
        return None, None, str(e)

# ============================================================
# DEBT MARKET LOADERS
# ============================================================
DEBT_JSON_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/debt_market.json"
DEBT_CSV_URL  = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/debt_series.csv"

@st.cache_data(ttl=3600)
def load_debt_data():
    """Load debt market JSON (metrics/highlights) and CSV (time series)."""
    try:
        resp = requests.get(DEBT_JSON_URL)
        debt = json.loads(resp.text)
        series = pd.read_csv(DEBT_CSV_URL, parse_dates=['date'])
        return debt, series, None
    except Exception as e:
        return None, None, str(e)
# ============================================================
# CFTC COT LOADER
# ============================================================
CFTC_JSON_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/cftc.json"

@st.cache_data(ttl=3600)
def load_cftc_data():
    try:
        resp = requests.get(CFTC_JSON_URL)
        return json.loads(resp.text), None
    except Exception as e:
        return None, str(e)
# ============================================================
# SECTOR RRG LOADERS
# ============================================================
SECTORS_JSON_URL   = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/sectors.json"
SECTORS_PRICES_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/sectors_prices.csv"

@st.cache_data(ttl=3600)
def load_sectors_data():
    try:
        meta = json.loads(requests.get(SECTORS_JSON_URL).text)
        prices = pd.read_csv(SECTORS_PRICES_URL, parse_dates=['date'], index_col='date')
        return meta, prices, None
    except Exception as e:
        return None, None, str(e)
# ============================================================
# CROSS-ASSET LOADERS
# ============================================================
CROSSASSET_JSON_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/crossasset.json"
CROSSASSET_CSV_URL  = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/crossasset_series.csv"

@st.cache_data(ttl=3600)
def load_crossasset_data():
    try:
        meta = json.loads(requests.get(CROSSASSET_JSON_URL).text)
        series = pd.read_csv(CROSSASSET_CSV_URL, parse_dates=['date'], index_col='date')
        return meta, series, None
    except Exception as e:
        return None, None, str(e)



# ============================================================
# RISK RANGE HELPER FUNCTIONS
# ============================================================
@st.cache_data(ttl=3600)
def load_spx_forecast():
    """Load latest SPX forecast from GitHub"""
    try:
        SPX_FORECAST_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/forecasts/latest_spx_forecast.json"
        response = requests.get(SPX_FORECAST_URL)
        return json.loads(response.text)
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def load_nasdaq_forecast():
    """Load latest Nasdaq forecast from GitHub"""
    try:
        NASDAQ_FORECAST_URL = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/forecasts/latest_nasdaq_forecast.json"
        response = requests.get(NASDAQ_FORECAST_URL)
        return json.loads(response.text)
    except Exception as e:
        return None

def display_risk_range(forecast, ticker_name):
    """Display formatted risk range forecast with charts and downloads"""
    if forecast is None or forecast.get('status') != 'success':
        st.error(f"❌ Error loading {ticker_name} forecast")
        if forecast and 'error_message' in forecast:
            st.error(f"Details: {forecast['error_message']}")
        st.info("💡 Forecast data will be available after the workflow runs for the first time (6:30 PM EST)")
        return
    
    # Header
    st.markdown(f"### Based on: {forecast['based_on_date']} close = {forecast['based_on_close']:,.2f}")
    st.markdown(f"**Forecasting for:** {forecast['forecast_date']}")
    
    # Regime indicator
    regime = forecast['regime']
    vix_label = "VIX" if ticker_name == "S&P 500" else "VXN"
    
    if regime == "investible":
        regime_color = "#28a745"
        regime_icon = "🟢"
    elif regime == "chop":
        regime_color = "#ffc107"
        regime_icon = "🟡"
    else:
        regime_color = "#dc3545"
        regime_icon = "🔴"
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"{vix_label}", f"{forecast['vix']:.2f}")
    with col2:
        st.markdown(f"""
            <div style="background-color: {regime_color}; padding: 10px; border-radius: 5px; text-align: center;">
                <span style="color: white; font-weight: bold;">{regime_icon} {regime.upper()}</span>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Main forecast table
    st.markdown("### 🎯 Forecast Levels")
    
    llr_label = 'Low (LLR 95)' if ticker_name == "S&P 500" else 'Low (LLR 97)'
    llr_confidence = '90% coverage' if ticker_name == "S&P 500" else '93% coverage'
    
    forecast_data = {
        'Level': ['High (TRR 80)', llr_label],
        'Price': [f"{forecast['forecast_high']:,.2f}", f"{forecast['forecast_low']:,.2f}"],
        'Distance': [f"{forecast['high_pct']:+.2f}%", f"{forecast['low_pct']:+.2f}%"],
        'Confidence': ['80% coverage', llr_confidence]
    }
    
    forecast_df = pd.DataFrame(forecast_data)
    
    # Style the dataframe
    def color_distance(val):
        try:
            num = float(val.strip('%').strip('+'))
            if num > 0:
                return 'background-color: #d4edda; color: #155724'
            else:
                return 'background-color: #f8d7da; color: #721c24'
        except:
            return ''
    
    styled_forecast = forecast_df.style.map(color_distance, subset=['Distance'])
    st.dataframe(styled_forecast, use_container_width=True, hide_index=True)
    
    # Range width
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Range Width (Points)",
            f"{forecast['range_width']:.2f}"
        )
    with col2:
        st.metric(
            "Range Width (%)",
            f"{(forecast['range_width']/forecast['based_on_close']*100):.2f}%"
        )
    
    # Floor indicator
    if forecast.get('floor_active'):
        st.info("🛡️ **FLOOR ACTIVE** - Yesterday's range exceeded median, additional downside protection applied")
    
    st.divider()
    
    # Download Current Forecast
    st.markdown("### 📥 Download Current Forecast")
    
    col1, col2 = st.columns(2)
    with col1:
        csv_data = generate_forecast_csv(forecast)
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"{ticker_name.replace(' ', '_')}_forecast_{forecast['forecast_date']}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Show preview button
        if st.button(f"👁️ Preview CSV", key=f"preview_{ticker_name}"):
            st.dataframe(pd.read_csv(pd.io.common.StringIO(csv_data)), use_container_width=True)
    
    st.divider()
    
    
    
    # Historical Comparison Section
    st.markdown("### 📊 Historical Performance")
    
    ticker_code = "SPX" if ticker_name == "S&P 500" else "NASDAQ"
    live_preds = load_live_predictions(ticker_code)
    hedgeye_data = load_hedgeye_data(ticker_code)
    
    if live_preds is not None and len(live_preds) > 0:
        # Filter to complete predictions only
        complete_preds = live_preds.dropna(subset=['next_high', 'next_low'])
        
        if len(complete_preds) > 0:
            # Calculate containment and error metrics on the fly
            complete_preds['high_contained_80'] = (complete_preds['next_high'] <= complete_preds['high_pred_80']).astype(float)
            complete_preds['low_contained_95'] = (complete_preds['next_low'] >= complete_preds['low_pred_95']).astype(float)
            complete_preds['high_error_80'] = (complete_preds['high_pred_80'] - complete_preds['next_high']).abs()
            complete_preds['low_error_95'] = (complete_preds['low_pred_95'] - complete_preds['next_low']).abs()
            
            # Performance metrics
            col1, col2, col3, col4 = st.columns(4)
            
            recent_20 = complete_preds.head(20)
            
            with col1:
                high_cov = recent_20['high_contained_80'].mean() * 100
                st.metric("High Coverage (20d)", f"{high_cov:.1f}%")
            
            with col2:
                low_cov = recent_20['low_contained_95'].mean() * 100
                st.metric("Low Coverage (20d)", f"{low_cov:.1f}%")
            
            with col3:
                high_mae = recent_20['high_error_80'].mean()
                st.metric("High MAE (20d)", f"{high_mae:.1f} pts")
            
            with col4:
                low_mae = recent_20['low_error_95'].mean()
                st.metric("Low MAE (20d)", f"{low_mae:.1f} pts")
            
            # Charts
            if hedgeye_data is not None:
                st.markdown("#### 📈 Forecast vs Actual Comparison")
                
                days_to_plot = st.slider(
                    "Days to display",
                    min_value=20,
                    max_value=min(120, len(complete_preds)),
                    value=60,
                    step=10,
                    key=f"slider_{ticker_name}"
                )
                
                # Comparison chart
                comparison_fig = create_comparison_chart(complete_preds, hedgeye_data, days=days_to_plot)
                st.plotly_chart(comparison_fig, use_container_width=True)
                
                # Error chart
                st.markdown("#### 📉 Error Comparison")
                error_fig = create_error_chart(complete_preds, hedgeye_data, days=days_to_plot)
                st.plotly_chart(error_fig, use_container_width=True)
                
                # Performance summary table
                with st.expander("📊 Detailed Performance Metrics"):
                    merged = complete_preds.merge(
                        hedgeye_data[['Date', 'hedgeye_high', 'hedgeye_low']],
                        left_on='date',
                        right_on='Date',
                        how='left'
                    ).dropna(subset=['hedgeye_high'])
                    
                    if len(merged) > 0:
                        # Ensure metrics are calculated
                        if 'high_contained_80' not in merged.columns:
                            merged['high_contained_80'] = (merged['next_high'] <= merged['high_pred_80']).astype(float)
                            merged['low_contained_95'] = (merged['next_low'] >= merged['low_pred_95']).astype(float)
                            merged['high_error_80'] = (merged['high_pred_80'] - merged['next_high']).abs()
                            merged['low_error_95'] = (merged['low_pred_95'] - merged['next_low']).abs()
                        
                        # Calculate metrics
                        model_high_mae = merged['high_error_80'].mean()
                        model_low_mae = merged['low_error_95'].mean()
                        model_high_cov = (merged['high_contained_80'].mean() * 100)
                        model_low_cov = (merged['low_contained_95'].mean() * 100)
                        
                        he_high_error = (merged['hedgeye_high'] - merged['next_high']).abs().mean()
                        he_low_error = (merged['hedgeye_low'] - merged['next_low']).abs().mean()
                        he_high_cov = ((merged['next_high'] <= merged['hedgeye_high']).mean() * 100)
                        he_low_cov = ((merged['next_low'] >= merged['hedgeye_low']).mean() * 100)
                        
                        metrics_data = {
                            'Metric': [
                                'High MAE (pts)',
                                'Low MAE (pts)',
                                'High Coverage %',
                                'Low Coverage %',
                                'Sample Size'
                            ],
                            'V4/V5 Model': [
                                f"{model_high_mae:.1f}",
                                f"{model_low_mae:.1f}",
                                f"{model_high_cov:.1f}%",
                                f"{model_low_cov:.1f}%",
                                len(merged)
                            ],
                            'HE Model': [
                                f"{he_high_error:.1f}",
                                f"{he_low_error:.1f}",
                                f"{he_high_cov:.1f}%",
                                f"{he_low_cov:.1f}%",
                                len(merged)
                            ],
                            'Advantage': [
                                f"{model_high_mae - he_high_error:+.1f}",
                                f"{model_low_mae - he_low_error:+.1f}",
                                f"{model_high_cov - he_high_cov:+.1f}",
                                f"{model_low_cov - he_low_cov:+.1f}",
                                "—"
                            ]
                        }
                        
                        st.dataframe(pd.DataFrame(metrics_data), use_container_width=True, hide_index=True)
            
            # Download live track record
            st.markdown("#### 📥 Download Complete Track Record")
            
            csv_track = live_preds.to_csv(index=False)
            st.download_button(
                label="📊 Download Full Track Record CSV",
                data=csv_track,
                file_name=f"{ticker_name.replace(' ', '_')}_live_track_record.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("📊 Historical data will appear after predictions are backfilled (next day)")
    else:
        st.info("📊 Live track record will be available after the first forecast runs")
    
    st.divider()
    
    # Additional reference levels (collapsible)
    with st.expander("📊 Additional Reference Levels"):
        ref_levels = forecast['reference_levels']
        
        if ticker_name == "S&P 500":
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("TRR 50 (median high)", f"{ref_levels['trr_50']:,.2f}")
            with col2:
                st.metric("LLR 90", f"{ref_levels['llr_90']:,.2f}")
            with col3:
                st.metric("LLR 80", f"{ref_levels['llr_80']:,.2f}")
        else:  # Nasdaq
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("TRR 50 (median high)", f"{ref_levels['trr_50']:,.2f}")
            with col2:
                st.metric("LLR 95", f"{ref_levels['llr_95']:,.2f}")
            with col3:
                st.metric("LLR 90", f"{ref_levels['llr_90']:,.2f}")
            with col4:
                st.metric("LLR 80", f"{ref_levels['llr_80']:,.2f}")
    
    # Key risks
    if forecast.get('risks'):
        with st.expander("⚠️ Key Risks to Monitor", expanded=True):
            for risk in forecast['risks']:
                st.warning(f"• {risk}")
    else:
        st.success("✅ No elevated risk factors detected")
    
    # Timestamp
    st.caption(f"🔄 Forecast generated: {forecast['timestamp']}")
    st.caption(f"🤖 Model version: {forecast['model_version']}")


# ============================================================
# RISK RANGE ENHANCED FEATURES
# ============================================================

@st.cache_data(ttl=3600)
def load_live_predictions(ticker):
    """Load live prediction track record with column name compatibility"""
    try:
        if ticker == "SPX":
            url = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/forecasts/spx_live_predictions_v4.csv"
        else:
            url = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/forecasts/nasdaq_live_predictions_v5.csv"
        
        df = pd.read_csv(url)
        
        # Handle old column format (Date, vix_close, vix_regime)
        column_mapping = {
            'Date': 'date',
            'vix_close': 'vix',
            'vix_regime': 'regime'
        }
        
        # Apply mapping if old columns exist
        df = df.rename(columns=column_mapping)
        
        # Ensure date column is datetime
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        return df
    except Exception as e:
        print(f"Error loading live predictions: {e}")  # For debugging
        return None

@st.cache_data(ttl=3600)
def load_hedgeye_data(ticker):
    """Load Hedgeye benchmark data"""
    try:
        if ticker == "SPX":
            url = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/04_enriched/SPX_enriched.csv"
        else:
            url = "https://raw.githubusercontent.com/dchebows/HE-analysis-pipeline/main/Risk_Range_Data/04_enriched/COMPQ_enriched.csv"
        
        df = pd.read_csv(url)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.rename(columns={'BUY TRADE': 'hedgeye_low', 'SELL TRADE': 'hedgeye_high'})
        return df
    except Exception as e:
        return None

def create_comparison_chart(live_preds, hedgeye_data, days=60):
    """Create historical comparison chart"""
    import plotly.graph_objects as go
    
    # Get recent data
    plot_data = live_preds.head(days).copy()
    plot_data = plot_data.dropna(subset=['next_high', 'next_low'])
    
    # Merge with Hedgeye
    plot_data = plot_data.merge(
        hedgeye_data[['Date', 'hedgeye_high', 'hedgeye_low']],
        left_on='date',
        right_on='Date',
        how='left'
    )
    
    fig = go.Figure()
    
    # Hedgeye range (background)
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['hedgeye_high'],
        name='HE TRR (80)',
        line=dict(color='blue', width=1, dash='dash'),
        mode='lines'
    ))
    
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['hedgeye_low'],
        name='HE LRR (95)',
        fill='tonexty',
        fillcolor='rgba(0, 0, 255, 0.1)',
        line=dict(color='blue', width=1, dash='dash'),
        mode='lines'
    ))
    
    # Model predictions
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['high_pred_80'],
        name='V4/V5 High (80)',
        line=dict(color='green', width=2),
        mode='lines'
    ))
    
    low_col = 'low_pred_97' if 'low_pred_97' in plot_data.columns else 'low_pred_95'
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data[low_col],
        name='V4/V5 Low (95/97)',
        fill='tonexty',
        fillcolor='rgba(0, 255, 0, 0.2)',
        line=dict(color='green', width=2),
        mode='lines'
    ))
    
    # Actual high/low
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['next_high'],
        name='Actual High',
        mode='markers',
        marker=dict(size=4, color='red', symbol='triangle-up')
    ))
    
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['next_low'],
        name='Actual Low',
        mode='markers',
        marker=dict(size=4, color='red', symbol='triangle-down')
    ))
    
    fig.update_layout(
        title=f"Risk Range Forecast vs Actual (Last {days} Days)",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode='x unified',
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def create_error_chart(live_preds, hedgeye_data, days=60):
    """Create error comparison chart"""
    import plotly.graph_objects as go
    
    plot_data = live_preds.head(days).copy()
    plot_data = plot_data.dropna(subset=['high_error_80', 'low_error_95'])
    
    plot_data = plot_data.merge(
        hedgeye_data[['Date', 'hedgeye_high', 'hedgeye_low']],
        left_on='date',
        right_on='Date',
        how='left'
    )
    
    # Calculate Hedgeye errors
    plot_data['he_high_error'] = (plot_data['hedgeye_high'] - plot_data['next_high']).abs()
    plot_data['he_low_error'] = (plot_data['hedgeye_low'] - plot_data['next_low']).abs()
    plot_data['he_total_error'] = plot_data['he_high_error'] + plot_data['he_low_error']
    
    low_col = 'low_error_97' if 'low_error_97' in plot_data.columns else 'low_error_95'
    plot_data['model_total_error'] = plot_data['high_error_80'] + plot_data.get(low_col, plot_data['low_error_95'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=plot_data['date'],
        y=plot_data['model_total_error'],
        name='V4/V5 Total Error',
        marker_color='green',
        opacity=0.6
    ))
    
    fig.add_trace(go.Bar(
        x=plot_data['date'],
        y=plot_data['he_total_error'],
        name='HE Total Error',
        marker_color='blue',
        opacity=0.6
    ))
    
    fig.update_layout(
        title=f"Daily Forecast Error Comparison (Last {days} Days)",
        xaxis_title="Date",
        yaxis_title="Total Error (points)",
        barmode='group',
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig

def generate_forecast_csv(forecast):
    """Generate CSV export of current forecast"""
    data = {
        'Metric': [
            'Forecast Date',
            'Based On Date',
            'Based On Close',
            'VIX/VXN',
            'Regime',
            'Forecast High (TRR 80)',
            'Forecast Low (LLR 95/97)',
            'High Distance %',
            'Low Distance %',
            'Range Width (pts)',
            'Range Width %',
            'Floor Active',
            'Model Version'
        ],
        'Value': [
            forecast['forecast_date'],
            forecast['based_on_date'],
            f"{forecast['based_on_close']:.2f}",
            f"{forecast['vix']:.2f}",
            forecast['regime'].upper(),
            f"{forecast['forecast_high']:.2f}",
            f"{forecast['forecast_low']:.2f}",
            f"{forecast['high_pct']:+.2f}%",
            f"{forecast['low_pct']:+.2f}%",
            f"{forecast['range_width']:.2f}",
            f"{(forecast['range_width']/forecast['based_on_close']*100):.2f}%",
            'Yes' if forecast.get('floor_active') else 'No',
            forecast.get('model_version', 'N/A')
        ]
    }
    
    df = pd.DataFrame(data)
    
    # Add reference levels
    ref_data = []
    for level_name, level_value in forecast['reference_levels'].items():
        ref_data.append({'Metric': level_name.upper(), 'Value': f"{level_value:.2f}"})
    
    if ref_data:
        ref_df = pd.DataFrame(ref_data)
        df = pd.concat([df, ref_df], ignore_index=True)
    
    # Add risks
    if forecast.get('risks'):
        df = pd.concat([df, pd.DataFrame([{'Metric': 'RISKS', 'Value': ''}])], ignore_index=True)
        for i, risk in enumerate(forecast['risks'], 1):
            df = pd.concat([df, pd.DataFrame([{'Metric': f'Risk {i}', 'Value': risk}])], ignore_index=True)
    
    return df.to_csv(index=False)


# ============================================================
# TAB NAVIGATION
# ============================================================
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋 Daily Briefing",
    "📊 CRR Analysis", "💼 Portfolio Signals", "🎯 Risk Range",
    "🏦 Debt Markets", "📊 CFTC Positioning", "🔄 Sector RRG",
    "🌐 Cross-Asset"
])

# ============================================================
# TAB 1: CRR ANALYSIS (EXISTING DASHBOARD)
# ============================================================
with tab1:
    st.title("📊 Daily CRR Analysis Dashboard")
    st.caption("🤖 Automated updates daily at 7pm UTC")

    # Load data
    df, spx_gamma, throttle_history, error = load_data()

    if error:
        st.error(f"❌ Error loading data: {error}")
        st.stop()

    if df is None:
        st.warning("⚠️ No data available")
        st.stop()

    # ============================================================
    # HEADER: S&P 500 INDEX, VIX & MACHINE STATUS
    # ============================================================
    col1, col2, col3 = st.columns(3)

    with col1:
        # Get S&P 500 data from dataframe
        spx_row = df[df['Ticker'] == '^GSPC']
        if not spx_row.empty:
            spx_close = spx_row['Close'].values[0]
            spx_change = spx_row['1D %'].values[0]
            
            change_color = "🟢" if spx_change >= 0 else "🔴"
            st.markdown(f"### S&P 500 Index: {spx_close:,.2f} {change_color} ({spx_change:+.2f}%)")
        else:
            st.markdown("### S&P 500 Index: Data Not Available")

    with col2:
        # VIX Status
        vix_row = df[df['Ticker'] == '^VIX']
        if not vix_row.empty:
            vix_value = vix_row['Close'].values[0]
            
            # Determine VIX status and color
            if vix_value <= 19:
                vix_status = "INVESTABLE"
                vix_bg_color = "#28a745"  # Green
            elif vix_value <= 29.99:
                vix_status = "CHOP BUCKET"
                vix_bg_color = "#ffc107"  # Yellow
            else:
                vix_status = "F BUCKET"
                vix_bg_color = "#dc3545"  # Red
            
            st.markdown(f"""
                <div style="text-align: center;">
                    <h3 style="margin-bottom: 10px;">VIX: {vix_value:.2f}</h3>
                    <div style="background-color: {vix_bg_color}; padding: 10px 20px; border-radius: 5px; display: inline-block;">
                        <span style="color: white; font-size: 20px; font-weight: bold;">{vix_status}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("### VIX: Data Not Available")

    with col3:
        # Get Machine status from ^GSPC row
        if not spx_row.empty:
            machine_status = spx_row['Machine'].values[0]
            bg_color = "#28a745" if machine_status == 'Systematic Buying' else "#dc3545"
            
            st.markdown(f"""
                <div style="text-align: center;">
                    <h3 style="margin-bottom: 10px;">The Machine:</h3>
                    <div style="background-color: {bg_color}; padding: 10px 20px; border-radius: 5px; display: inline-block;">
                        <span style="color: white; font-size: 20px; font-weight: bold;">{machine_status}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("### The Machine: Data Not Available")

    st.divider()

    # ============================================================
    # SPX GAMMA VOLATILITY THROTTLE DASHBOARD
    # ============================================================
    if spx_gamma and 'gamma_throttle' in spx_gamma:
        st.subheader("📊 S&P 500 Gamma Volatility Throttle")
        
        # Display scatter plot if history available
        if throttle_history is not None and len(throttle_history) > 5:
            # Create scatter plot
            fig = go.Figure()
            
            # Add scatter points with color gradient by date
            fig.add_trace(go.Scatter(
                x=throttle_history['throttle'],
                y=throttle_history['rv_10'],
                mode='markers',
                marker=dict(
                    size=8,
                    color=throttle_history.index,
                    colorscale='RdYlGn',
                    showscale=False,
                    opacity=0.7
                ),
                text=throttle_history['date'].dt.strftime('%Y-%m-%d'),
                hovertemplate='<b>%{text}</b><br>Throttle: %{x:.1f}<br>10-Day RV: %{y:.2f}%<extra></extra>',
                showlegend=False
            ))
            
            # Add exponential fit line
            x_data = throttle_history['throttle'].values
            y_data = throttle_history['rv_10'].values
            
            try:
                from scipy.optimize import curve_fit
                
                def exp_decay(x, a, b, c):
                    return a * np.exp(-b * x) + c
                
                y_max = y_data.max()
                y_min = y_data.min()
                
                popt, _ = curve_fit(
                    exp_decay, x_data, y_data, 
                    p0=[y_max - y_min, 0.02, y_min], 
                    maxfev=50000
                )
                
                x_fit = np.linspace(x_data.min(), x_data.max(), 200)
                y_fit = exp_decay(x_fit, *popt)
                
                fig.add_trace(go.Scatter(
                    x=x_fit,
                    y=y_fit,
                    mode='lines',
                    line=dict(color='blue', width=2, dash='dash'),
                    name='Exponential Trend',
                    hoverinfo='skip'
                ))
                
            except Exception as e:
                # Fallback to polynomial
                z = np.polyfit(x_data, y_data, 3)
                p = np.poly1d(z)
                x_fit = np.linspace(x_data.min(), x_data.max(), 200)
                y_fit = p(x_fit)
                
                valid_mask = y_fit > 0
                
                fig.add_trace(go.Scatter(
                    x=x_fit[valid_mask],
                    y=y_fit[valid_mask],
                    mode='lines',
                    line=dict(color='blue', width=2, dash='dash'),
                    name='Polynomial Trend',
                    hoverinfo='skip'
                ))
            
            # Highlight current point
            current_throttle = spx_gamma['gamma_throttle']
            current_rv = spx_gamma['rv_10day']
            
            fig.add_trace(go.Scatter(
                x=[current_throttle],
                y=[current_rv],
                mode='markers+text',
                marker=dict(size=15, color='white', line=dict(color='black', width=2)),
                text=['Last'],
                textposition='top center',
                textfont=dict(size=12, color='black', family='Arial Black'),
                hovertemplate=f'<b>Current</b><br>Throttle: {current_throttle:.1f}<br>10-Day RV: {current_rv:.2f}%<extra></extra>',
                showlegend=False
            ))
            
            # Add gamma transition zone
            fig.add_vrect(x0=-5, x1=5, fillcolor="gray", opacity=0.1, line_width=0)
            
            # Layout
            fig.update_layout(
                title="SPX Gamma Volatility Throttle vs. 10-Day Realized Volatility",
                xaxis_title="Gamma Throttle",
                yaxis_title="10-Day Realized Volatility (%)",
                xaxis=dict(range=[-105, 40], gridcolor='lightgray'),
                yaxis=dict(range=[0, max(y_data.max() * 1.1, 30)], gridcolor='lightgray'),
                plot_bgcolor='white',
                height=500,
                hovermode='closest',
                font=dict(size=11)
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Top metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            throttle_value = spx_gamma['gamma_throttle']
            st.metric(
                label="Gamma Throttle",
                value=f"{throttle_value:.1f}"
            )
        
        with col2:
            st.metric(
                label="10-Day RV",
                value=f"{spx_gamma['rv_10day']:.2f}%"
            )
        
        with col3:
            st.metric(
                label="VIX",
                value=f"{spx_gamma['vix']:.2f}"
            )
        
        with col4:
            st.metric(
                label="Dist. to Flip",
                value=f"{spx_gamma['dist_to_flip_pct']:+.2f}%"
            )
        
        # Regime display
        regime = spx_gamma['regime']
        regime_desc = spx_gamma['regime_description']
        
        # Determine regime color
        if 'POSITIVE' in regime:
            regime_color = "#28a745"
        elif 'TRANSITION' in regime:
            regime_color = "#ffc107"
        else:
            regime_color = "#dc3545"
        
        st.markdown(f"""
            <div style="text-align: center; margin: 20px 0;">
                <div style="background-color: {regime_color}; padding: 15px 30px; border-radius: 8px; display: inline-block;">
                    <span style="color: white; font-size: 18px; font-weight: bold;">{regime}</span>
                </div>
                <p style="margin-top: 10px; font-style: italic; color: #666;">{regime_desc}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Risk & Position Size
        col1, col2 = st.columns(2)
        
        with col1:
            risk_level = spx_gamma['risk_level']
            if risk_level in ['LOW', 'LOW-MODERATE']:
                risk_color = "#28a745"
            elif risk_level in ['MODERATE', 'ELEVATED']:
                risk_color = "#ffc107"
            else:
                risk_color = "#dc3545"
            
            st.markdown(f"""
                <div style="text-align: center;">
                    <p style="margin-bottom: 5px; font-weight: bold;">Risk Level</p>
                    <div style="background-color: {risk_color}; padding: 10px; border-radius: 5px;">
                        <span style="color: white; font-size: 16px; font-weight: bold;">{risk_level}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div style="text-align: center;">
                    <p style="margin-bottom: 5px; font-weight: bold;">Position Size</p>
                    <div style="background-color: #6c757d; padding: 10px; border-radius: 5px;">
                        <span style="color: white; font-size: 16px; font-weight: bold;">{spx_gamma['position_size']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Key Levels
        st.markdown("**🎯 Key Levels**")
        key_levels = spx_gamma['key_levels']
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Gamma Flip", f"{key_levels['gamma_flip']:,.0f}")
        with col2:
            st.metric("Put Wall", f"{key_levels['put_wall']:,.0f}")
        with col3:
            st.metric("Call Wall", f"{key_levels['call_wall']:,.0f}")
        with col4:
            st.metric("Danger Zone", f"{key_levels['danger_zone']:,.0f}")
        
        # Signals
        col1, col2 = st.columns(2)
        
        # Signals
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**📊 Volatility Signal**")
        vol_signal = spx_gamma['vol_signal']
        if 'SELL' in vol_signal:
            vol_bg = "#28a745"
        elif 'BUY' in vol_signal:
            vol_bg = "#dc3545"
        else:
            vol_bg = "#ffc107"
        
        st.markdown(f"""
            <div style="background-color: {vol_bg}; padding: 10px; border-radius: 5px; text-align: center;">
                <span style="color: white; font-weight: bold;">{vol_signal}</span>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**📈 Directional Signal**")
        dir_signal = spx_gamma['dir_signal']
        if 'BULLISH' in dir_signal:
            dir_bg = "#28a745"
        elif 'BEAR' in dir_signal or 'TREND' in dir_signal:
            dir_bg = "#dc3545"
        else:
            dir_bg = "#6c757d"
        
        st.markdown(f"""
            <div style="background-color: {dir_bg}; padding: 10px; border-radius: 5px; text-align: center;">
                <span style="color: white; font-weight: bold;">{dir_signal}</span>
            </div>
        """, unsafe_allow_html=True)
    
    # Data source and timestamp
    st.caption(f"🔄 Data refreshed: {spx_gamma['timestamp']} UTC | Source: CBOE GEX + Yahoo Finance")

    st.divider()
    
    # ============================================================
    # SIGNAL STRENGTH HIGHLIGHTS
    # ============================================================
    st.subheader("🎯 Signal Strength Highlights")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🟢 Strongest Signals")
        top_signals = df.nlargest(5, 'SS_Score')[['Ticker', 'SS_Score', 'SS_Status', 'SS_Action']]
        st.dataframe(top_signals, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("### 🔴 Weakest Signals")
        bottom_signals = df.nsmallest(5, 'SS_Score')[['Ticker', 'SS_Score', 'SS_Status', 'SS_Action']]
        st.dataframe(bottom_signals, use_container_width=True, hide_index=True)

    st.divider()

    # ============================================================
    # (Filters removed — table shows all rows)
    # ============================================================
    filtered_df = df.copy()

    # ============================================================
    # FULL DATA TABLE WITH COLOR STYLING
    # ============================================================
    st.subheader("📋 Full Analysis Table")

    # Define styling functions
    def color_negative_positive(val):
        """Color percentage columns: green for positive, red for negative"""
        try:
            color = '#28a745' if float(val) >= 0 else '#dc3545'
            return f'background-color: {color}; color: white'
        except:
            return ''

    def color_trade_trend(val):
        """Color Trade/Trend columns"""
        if val == 'Bullish':
            return 'background-color: #28a745; color: white; font-weight: bold'
        elif val == 'Bearish':
            return 'background-color: #dc3545; color: white; font-weight: bold'
        elif val == 'Neutral':
            return 'background-color: #6c757d; color: white'
        return ''

    def color_machine(val):
        """Color Machine column"""
        if val == 'Systematic Buying':
            return 'background-color: #28a745; color: white; font-weight: bold'
        elif val == 'Systematic Selling':
            return 'background-color: #dc3545; color: white; font-weight: bold'
        return ''

    def color_change_indicator(val):
        """Color change indicators"""
        if val == '⚠':
            return 'background-color: #ffc107; color: black; font-weight: bold'
        return ''

    def color_rsi_level(val):
        """Color RSI Level"""
        if val in ['Overbought', 'Oversold']:
            return 'background-color: #dc3545; color: white; font-weight: bold'
        elif val == 'In-Range':
            return 'background-color: #28a745; color: white; font-weight: bold'
        return ''

    def color_ss_score(val):
        """Color SS_Score with gradient"""
        try:
            val = float(val)
            if val >= 60:
                return 'background-color: #00aa00; color: white; font-weight: bold'
            elif val >= 40:
                return 'background-color: #44cc44; color: white'
            elif val >= 20:
                return 'background-color: #88dd88; color: black'
            elif val >= 0:
                return 'background-color: #cceecc; color: black'
            elif val >= -20:
                return 'background-color: #eecccc; color: black'
            elif val >= -40:
                return 'background-color: #dd8888; color: black'
            elif val >= -60:
                return 'background-color: #cc4444; color: white'
            else:
                return 'background-color: #aa0000; color: white; font-weight: bold'
        except:
            return ''

    def color_ss_status(val):
        """Color SS_Status"""
        if not isinstance(val, str):
            return ''
        if 'MAX BULL' in val or 'RECOVERY IMMINENT' in val:
            return 'background-color: #00aa00; color: white; font-weight: bold'
        elif 'STRONG BULL' in val:
            return 'background-color: #44cc44; color: white; font-weight: bold'
        elif 'BULL INTACT' in val or 'ALL CLEAR' in val:
            return 'background-color: #88dd88; color: black'
        elif 'WEAK BULL' in val:
            return 'background-color: #cceecc; color: black'
        elif 'LEANING BULL' in val or 'RECOVERY LIKELY' in val:
            return 'background-color: #dddd44; color: black'
        elif 'BULL WATCH' in val or 'RECOVERY WATCH' in val:
            return 'background-color: #ffcc00; color: black'
        elif 'BULL CAUTION' in val:
            return 'background-color: #ff8800; color: white'
        elif 'BULL DANGER' in val:
            return 'background-color: #cc0000; color: white; font-weight: bold'
        elif 'NEUTRAL' in val:
            return 'background-color: #dddddd; color: black'
        elif 'LEANING BEAR' in val:
            return 'background-color: #ffcc00; color: black'
        elif 'BEAR HOLD' in val:
            return 'background-color: #dd8888; color: black'
        elif 'BEAR INTACT' in val:
            return 'background-color: #cc4444; color: white'
        elif 'STRONG BEAR' in val or 'MAX BEAR' in val:
            return 'background-color: #aa0000; color: white; font-weight: bold'
        return ''

    def color_warning_level(val):
        """Color warning levels"""
        try:
            val = int(val)
            if val == 0:
                return 'background-color: #88dd88; color: black'
            elif val == 1:
                return 'background-color: #ffcc00; color: black'
            elif val == 2:
                return 'background-color: #ff8800; color: white'
            else:
                return 'background-color: #cc0000; color: white; font-weight: bold'
        except:
            return ''

    # Custom formatting for price columns based on ticker type
    def format_price(row, column_name):
        ticker = row['Ticker']
        value = row[column_name]
        if pd.isna(value):
            return ''
        if ticker == '^TNX':
            return f'{value:.2f}%'
        elif ticker in ['^GSPC', '^IXIC', '^RUT', '^VIX']:
            return f'{value:,.2f}'
        else:
            return f'${value:,.2f}'

    # Create a copy for display
    display_df = filtered_df.copy()
    display_df['Close'] = display_df.apply(lambda row: format_price(row, 'Close'), axis=1)
    display_df['Bottom End'] = display_df.apply(lambda row: format_price(row, 'Bottom End'), axis=1)
    display_df['Top End'] = display_df.apply(lambda row: format_price(row, 'Top End'), axis=1)

    # Apply styling
    styled_df = display_df.style\
        .map(color_negative_positive, subset=['1D %', '1W %', '1M %', '3M %', 'Vlm 1D %', 'Vlm 1W %', 'Vlm 1M %', 'Vlm 3M %'])\
        .map(color_trade_trend, subset=['Trade', 'Trend'])\
        .map(color_machine, subset=['Machine'])\
        .map(color_change_indicator, subset=['Trade_Chg', 'Trend_Chg'])\
        .map(color_rsi_level, subset=['Level'])\
        .map(color_ss_score, subset=['SS_Score'])\
        .map(color_ss_status, subset=['SS_Status'])\
        .map(color_warning_level, subset=['Warn_Lvl'])\
        .format({
            'ATH': '{:.2f}',
            'Trade_lvl': '{:.2f}',
            'Trend_Lvl': '{:.2f}',
            'Down side %': '{:.2f}%',
            'Up side %': '{:.2f}%',
            '1D %': '{:+.2f}%',
            '1W %': '{:+.2f}%',
            '1M %': '{:+.2f}%',
            '3M %': '{:+.2f}%',
            'RVOL_1M': '{:.2f}',
            'RVOL_3M': '{:.2f}',
            'RSI': '{:.1f}',
            'Beta_1Y': '{:.2f}',
            'SS_Score': '{:.0f}'
        })

    # Display styled table with frozen Ticker column
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=600,
        column_config={
            "Ticker": st.column_config.TextColumn(
                "Ticker",
                width="small",
                pinned=True,
            ),
        },
    )

    # Add data refresh timestamp at bottom
    if spx_gamma and 'timestamp' in spx_gamma:
        data_timestamp = spx_gamma['timestamp']
    else:
        data_timestamp = "Unknown"

    st.caption(f"🔄 Data generated: {data_timestamp} UTC | GitHub Actions runs daily at 7:00 PM EST")
    st.caption(f"📊 Dashboard cache refreshes hourly from GitHub")

    

    # ============================================================
    # DOWNLOAD BUTTON
    # ============================================================
    st.download_button(
        label="📥 Download CSV",
        data=df.to_csv(index=False),
        file_name=f"stock_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

    # ============================================================
    # FOOTER
    # ============================================================
    st.divider()
    st.caption(f"🔄 Data refreshes automatically every hour | Last loaded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    st.caption("📊 Powered by GitHub Actions + Streamlit")

# ============================================================
# TAB 2: PORTFOLIO SIGNALS (NEW)
# ============================================================
with tab2:
    st.title("💼 Multi-Asset Portfolio Signals")
    st.caption("🤖 Automated updates daily at 7:05 PM EST")
    
    # Load portfolio data
    portfolio_df, portfolio_txt, port_error = load_portfolio_data()
    
    if port_error:
        st.error(f"❌ Error loading portfolio data: {port_error}")
        st.info("💡 This data will be available after the portfolio workflow runs for the first time (7:05 PM EST)")
        st.stop()
    
    if portfolio_df is None:
        st.warning("⚠️ Portfolio data not yet available. First run scheduled for 7:05 PM EST.")
        st.stop()
    
    # ============================================================
    # SUMMARY METRICS ROW
    # ============================================================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_danger = portfolio_df['Danger_Score'].mean()
        st.metric(
            label="Average Danger Score",
            value=f"{avg_danger:.0f}/100",
            delta=None
        )
    
    with col2:
        avg_target = portfolio_df['Target_Weight'].mean()
        st.metric(
            label="Average Target Position",
            value=f"{avg_target*100:.0f}%"
        )
    
    with col3:
        avg_sharpe = portfolio_df['Sharpe'].mean()
        st.metric(
            label="Portfolio Avg Sharpe",
            value=f"{avg_sharpe:.2f}"
        )
    
    with col4:
        buy_count = (portfolio_df['Action'].str.contains('BUY')).sum()
        sell_count = (portfolio_df['Action'].str.contains('SELL')).sum()
        st.metric(
            label="Actions Today",
            value=f"{buy_count} Buy | {sell_count} Sell"
        )
    
    st.divider()
    
    # ============================================================
    # SUMMARY TABLE
    # ============================================================
    st.subheader("📊 Portfolio Summary Table")
    
    # Format for display
    display_cols = {
        'Asset': portfolio_df['Asset'],
        'Name': portfolio_df['Name'],
        'Action': portfolio_df['Action_Icon'] + ' ' + portfolio_df['Action'],
        'Current': portfolio_df['Current_Weight'].map(lambda x: f"{x*100:.0f}%"),
        'Target': portfolio_df['Target_Weight'].map(lambda x: f"{x*100:.0f}%"),
        'Δ': portfolio_df['Weight_Change'].map(lambda x: f"{x*100:+.1f}%"),
        'Danger': portfolio_df['Danger_Score'].map(lambda x: f"{x:.0f}"),
        'Zone': portfolio_df['Zone_Icon'] + ' ' + portfolio_df['Zone'],
        'Trend': portfolio_df['Trend'],
        'Sharpe': portfolio_df['Sharpe'].map(lambda x: f"{x:.2f}"),
        'CAGR': portfolio_df['CAGR'].map(lambda x: f"{x:.1f}%"),
        'Max DD': portfolio_df['Max_DD'].map(lambda x: f"{x:.1f}%"),
    }
    
    summary_display_df = pd.DataFrame(display_cols)
    
    st.dataframe(summary_display_df, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # ============================================================
    # DETAILED BREAKDOWN (EXPANDABLE SECTIONS)
    # ============================================================
    st.subheader("📋 Detailed Asset Breakdown")
    
    for _, row in portfolio_df.iterrows():
        with st.expander(f"{row['Asset']} - {row['Name']} | {row['Action_Icon']} {row['Action']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 Position Sizing**")
                st.metric("Current Weight", f"{row['Current_Weight']*100:.0f}%")
                st.metric("Target Weight", f"{row['Target_Weight']*100:.0f}%")
                st.metric("Change", f"{row['Weight_Change']*100:+.1f}%")
            
            with col2:
                st.markdown("**💰 Dollar Amounts**")
                st.metric("Invested", f"${row['Invested_Dollars']:,.0f}")
                st.metric("Cash", f"${row['Cash_Dollars']:,.0f}")
                if abs(row['Dollar_Change']) >= 100:
                    direction = "BUY" if row['Dollar_Change'] > 0 else "SELL"
                    st.metric(f"{direction}", f"${abs(row['Dollar_Change']):,.0f}")
                else:
                    st.info("No trade needed")
            
            with col3:
                st.markdown("**📈 Performance Metrics**")
                st.metric("Sharpe Ratio", f"{row['Sharpe']:.2f}")
                st.metric("CAGR", f"{row['CAGR']:.1f}%")
                st.metric("Max Drawdown", f"{row['Max_DD']:.1f}%")
            
            # Danger & Trend info
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                zone_color = "#28a745" if "SAFE" in row['Zone'] else "#ffc107" if "WATCH" in row['Zone'] else "#dc3545"
                st.markdown(f"""
                    <div style="padding: 10px; background-color: {zone_color}; border-radius: 5px; text-align: center;">
                        <span style="color: white; font-weight: bold;">Danger: {row['Danger_Score']:.0f}/100 | {row['Zone_Icon']} {row['Zone']}</span>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                trend_color = "#28a745" if row['Trend'] == 'BULLISH' else "#dc3545" if row['Trend'] == 'BEARISH' else "#6c757d"
                st.markdown(f"""
                    <div style="padding: 10px; background-color: {trend_color}; border-radius: 5px; text-align: center;">
                        <span style="color: white; font-weight: bold;">Trend: {row['Trend']} | Score: {row['V5B_Score']:.3f}</span>
                    </div>
                """, unsafe_allow_html=True)
    
    st.divider()
    
    # ============================================================
    # FULL TEXT REPORT (COLLAPSIBLE)
    # ============================================================
    with st.expander("📄 View Full Text Report"):
        st.text(portfolio_txt)
    
    # ============================================================
    # DOWNLOAD BUTTONS
    # ============================================================
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download Portfolio CSV",
            data=portfolio_df.to_csv(index=False),
            file_name=f"portfolio_signals_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        st.download_button(
            label="📄 Download Text Report",
            data=portfolio_txt,
            file_name=f"portfolio_signals_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    # ============================================================
    # FOOTER
    # ============================================================
    st.divider()
    
    # Get last update time from portfolio data
    if not portfolio_df.empty:
        last_date = portfolio_df['Last_Date'].max()
        st.caption(f"📅 Portfolio data as of: {last_date}")
    
    st.caption(f"🔄 Portfolio signals update daily at 7:05 PM EST | Dashboard cache refreshes hourly")
    st.caption("📊 Powered by GitHub Actions + Streamlit")

# ============================================================
# TAB 3: RISK RANGE FORECASTS (NEW)
# ============================================================
with tab3:
    st.title("🎯 Daily Risk Range Forecasts")
    st.caption("🤖 Automated updates daily at 6:30 PM EST")
    
    # Create sub-tabs for SPX and Nasdaq
    spx_tab, nasdaq_tab = st.tabs(["📈 S&P 500", "💻 Nasdaq"])
    
    # SPX Tab
    with spx_tab:
        st.subheader("S&P 500 Risk Range Forecast")
        spx_forecast = load_spx_forecast()
        display_risk_range(spx_forecast, "S&P 500")
    
    # Nasdaq Tab
    with nasdaq_tab:
        st.subheader("Nasdaq Composite Risk Range Forecast")
        nasdaq_forecast = load_nasdaq_forecast()
        display_risk_range(nasdaq_forecast, "Nasdaq")
    
    # Footer
    st.divider()
    st.caption("📊 Risk Range forecasts use VIX/VXN regime-aware quantile regression models")
    st.caption("🔄 Forecasts update daily at 6:30 PM EST via GitHub Actions")
    st.caption("💡 Models trained on 5 years of data, calibrated on recent 126 days")

# ============================================================
# TAB 4: DEBT MARKETS
# ============================================================
with tab4:
    st.title("🏦 Debt Market Dashboard")
    st.caption("🤖 Automated updates daily (~6:20 PM EST) | MOVE, Credit Spreads, Treasuries")

    debt, series, debt_err = load_debt_data()

    if debt_err:
        st.error(f"❌ Error loading debt data: {debt_err}")
        st.info("💡 Data appears after the Debt Market workflow runs.")
        st.stop()

    risk = debt['risk']
    panels = debt['panels']
    hl = debt['highlights']

    # ---------- COMPOSITE RISK SCORE GAUGE ----------
    st.subheader("Composite Risk Score")
    score = risk['score']
    regime = risk['regime']

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={'suffix': "/100", 'font': {'size': 40}},
        title={'text': f"<b>{regime}</b>", 'font': {'size': 22}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "rgba(0,0,0,0.7)", 'thickness': 0.25},
            'steps': [
                {'range': [0, 30],  'color': '#2e9e4f'},
                {'range': [30, 45], 'color': '#e8d200'},
                {'range': [45, 70], 'color': '#e07b00'},
                {'range': [70, 100],'color': '#9c0006'},
            ],
            'threshold': {'line': {'color': "black", 'width': 4},
                          'thickness': 0.85, 'value': score},
        }
    ))
    gauge.update_layout(height=280, margin=dict(t=60, b=10, l=30, r=30))
    st.plotly_chart(gauge, use_container_width=True)

    # Component breakdown
    cols = st.columns(len(risk['components']))
    for col, (name, c) in zip(cols, risk['components'].items()):
        short = name.split('(')[0].strip()
        col.metric(short, f"{c['pct']:.0f}", help=f"0–100 stress · weight {c['weight']:.0%}")

    st.caption(f"📅 As of {debt['as_of']} | 🔄 Generated {debt['generated']}")
    st.divider()

    # ---------- HIGHLIGHTS ----------
    st.subheader("🎯 Market Highlights")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🔴 Risk-Off Signals")
        if hl['risk_off']:
            for b in hl['risk_off']:
                st.markdown(f"- {b}")
        else:
            st.markdown("*— none —*")
    with c2:
        st.markdown("#### 🟢 Risk-On / Stable")
        if hl['risk_on']:
            for b in hl['risk_on']:
                st.markdown(f"- {b}")
        else:
            st.markdown("*— none —*")

    st.markdown("#### 📊 Yield Curve")
    for b in (hl['curve'] or ["*— none —*"]):
        st.markdown(f"- {b}")

    st.markdown("#### ⚠️ Trend Changes (sensitive)")
    for b in (hl['trend'] or ["*— none —*"]):
        st.markdown(f"- {b}")

    with st.expander("📖 Glossary"):
        st.markdown("""
        - **OAS** = extra yield over Treasuries (the price of credit risk; **wider = more fear**)
        - **HY** = high-yield "junk" bonds | **BBB** = lowest investment-grade
        - Spreads **WIDEN** = risk-off; **TIGHTEN** = risk-on
        - Curve **INVERTED** (2yr > 10yr) = classic recession warning
        - **Risk Score**: 0 = calm, 100 = most stressed vs last 20 months
        """)

    st.divider()

    # ---------- METRICS TABLE HELPER ----------
    def fmt_delta_row(name, m, is_spread=False):
        def cell(bps, pct):
            return f"{bps:+.0f} bps ({pct:+.1f}%)"
        return {
            'Series': name,
            'Last': f"{m['last']:.2f}",
            '1D Ago': f"{m['d1']:.2f}",
            '1W Ago': f"{m['w1']:.2f}",
            '1M Ago': f"{m['m1']:.2f}",
            'DoD': cell(*m['dod']),
            'WoW': cell(*m['wow']),
            'MoM': cell(*m['mom']),
        }

    def style_debt_table(df, spread_rows=()):
        def color(v, is_spread):
            try:
                bps = float(v.split()[0])
            except:
                return ''
            red = (bps < 0) if is_spread else (bps >= 0)
            return ('background-color: #ffc7ce; color: #9c0006' if red
                    else 'background-color: #c6efce; color: #006100')
        def apply_row(row):
            is_spread = row['Series'] in spread_rows
            return ['', '', '', '', '',
                    color(row['DoD'], is_spread),
                    color(row['WoW'], is_spread),
                    color(row['MoM'], is_spread)]
        return df.style.apply(apply_row, axis=1)

    # ---------- CHART HELPER ----------
    def line_chart(title, traces, y_label, y2_label=None):
        fig = go.Figure()
        for tr in traces:
            fig.add_trace(go.Scatter(
                x=series['date'], y=series[tr['col']],
                name=tr['name'], line=dict(color=tr['color'], width=1.3),
                yaxis=tr.get('yaxis', 'y')
            ))
        layout = dict(
            title=title, height=450, hovermode='x unified',
            yaxis=dict(title=y_label),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=40)
        )
        if y2_label:
            layout['yaxis2'] = dict(title=y2_label, overlaying='y', side='right')
        fig.update_layout(**layout)
        return fig

    # ---------- BOND VOLATILITY (MOVE) ----------
    st.subheader("Bond Volatility (MOVE Index)")
    st.plotly_chart(line_chart("MOVE Index",
        [{'col': 'MOVE', 'name': 'MOVE', 'color': 'black'}],
        "Volatility"), use_container_width=True)
    tbl = pd.DataFrame([fmt_delta_row('MOVE', panels['MOVE']['metrics'])])
    st.dataframe(style_debt_table(tbl), use_container_width=True, hide_index=True)
    tc = panels['MOVE']['trend']
    if tc['change']:
        st.warning(f"⚠️ Trend change: **{tc['trend']}** [{tc['strength']}, {tc['score']}/100]")
    st.divider()

    # ---------- HIGH YIELD CREDIT ----------
    st.subheader("High Yield Credit (OAS vs HYG)")
    st.plotly_chart(line_chart("High Yield OAS vs HYG",
        [{'col': 'HY_OAS', 'name': 'High Yield OAS', 'color': 'black'},
         {'col': 'HYG', 'name': 'HYG (RHS)', 'color': '#1f9ed6', 'yaxis': 'y2'}],
        "OAS (%)", "$HYG"), use_container_width=True)
    tbl = pd.DataFrame([fmt_delta_row('HY OAS', panels['HY_OAS']['metrics'])])
    st.dataframe(style_debt_table(tbl), use_container_width=True, hide_index=True)
    tc = panels['HY_OAS']['trend']
    if tc['change']:
        st.warning(f"⚠️ Trend change: **{tc['trend']}** [{tc['strength']}, {tc['score']}/100]")
    st.divider()

    # ---------- US TREASURIES ----------
    st.subheader("US Treasuries (2yr / 10yr / 2-10 Spread)")
    st.plotly_chart(line_chart("US Treasuries",
        [{'col': 'Y2', 'name': 'US 2yr Yield', 'color': 'black'},
         {'col': 'Y10', 'name': 'US 10Y Yield', 'color': '#999999'},
         {'col': 'SPREAD', 'name': '2-10 Spread (RHS)', 'color': '#1f9ed6', 'yaxis': 'y2'}],
        "Yields (%)", "Spread"), use_container_width=True)
    curve = panels['CURVE']
    tbl = pd.DataFrame([
        fmt_delta_row('2yr Yield', curve['m2']),
        fmt_delta_row('10yr Yield', curve['m10']),
        fmt_delta_row('2-10 Spread', curve['metrics'], is_spread=True),
    ])
    st.dataframe(style_debt_table(tbl, spread_rows=('2-10 Spread',)),
                 use_container_width=True, hide_index=True)
    # Steepener badge
    badge_color = {'Bear Steepener':'#fff3cd','Bull Steepener':'#d4edda',
                   'Bear Flattener':'#f8d7da','Bull Flattener':'#cce5ff'}.get(curve['regime'], '#eee')
    st.markdown(f"""
        <div style="background-color:{badge_color}; padding:12px; border-radius:6px; margin-top:8px;">
        <b>Curve Regime (1Mo): {curve['regime']}</b> — {curve['interp']}
        </div>
    """, unsafe_allow_html=True)
    tc = curve['trend']
    if tc['change']:
        st.warning(f"⚠️ Trend change: **{tc['trend']}** [{tc['strength']}, {tc['score']}/100]")
    st.divider()

    # ---------- INVESTMENT-GRADE (BBB) ----------
    st.subheader("Investment-Grade Credit (BBB OAS)")
    st.plotly_chart(line_chart("BBB - Treasury 10Y Spread",
        [{'col': 'BBB_OAS', 'name': 'BBB OAS', 'color': 'black'}],
        "Spread"), use_container_width=True)
    tbl = pd.DataFrame([fmt_delta_row('BBB Spread', panels['BBB_OAS']['metrics'])])
    st.dataframe(style_debt_table(tbl), use_container_width=True, hide_index=True)
    tc = panels['BBB_OAS']['trend']
    if tc['change']:
        st.warning(f"⚠️ Trend change: **{tc['trend']}** [{tc['strength']}, {tc['score']}/100]")

    st.divider()
    st.caption("📊 Data: FRED (OAS, yields) + Yahoo (MOVE, HYG) | Updated daily via GitHub Actions")
# ============================================================
# TAB 5: CFTC NON-COMMERCIAL POSITIONING
# ============================================================
with tab5:
    st.title("📊 CFTC Non-Commercial Net Long Positioning")
    st.caption("🤖 Updated weekly (Sat) | Legacy / Futures-Only | Source: CFTC")

    cftc, cftc_err = load_cftc_data()
    if cftc_err:
        st.error(f"❌ Error loading CFTC data: {cftc_err}")
        st.info("💡 Data appears after the CFTC workflow runs.")
        st.stop()

    st.caption(f"📅 Report date: {cftc['report_date']} | 🔄 Generated {cftc['generated']}")

    co = cftc.get('callouts', {})

    # ============================================================
    # TOP CALLOUT PANEL (the "what matters this week" summary)
    # ============================================================
    st.subheader("🎯 Positioning Highlights")

    # Quick count cards
    n_extreme = len(co.get('extremes', []))
    n_long = sum(1 for e in co.get('extremes', []) if e['z'] > 0)
    n_short = n_extreme - n_long
    n_flips = len(co.get('flips', []))

    m1, m2, m3 = st.columns(3)
    m1.metric("Crowded Extremes", f"{n_extreme}", help="Instruments with |Z-1Y| ≥ 2")
    m2.metric("Long / Short", f"{n_long} 🟢 / {n_short} 🔴")
    m3.metric("Positioning Flips", f"{n_flips}", help="Crossed net long↔short this week")

    # Extreme positioning
    st.markdown("#### 🚨 Extreme Positioning (|Z| ≥ 2)")
    if co.get('extremes'):
        for e in co['extremes']:
            st.markdown(f"- {e['text']}")
    else:
        st.markdown("*No extremes this week — positioning broadly within normal ranges.*")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### ⚡ Biggest Weekly Shifts")
        for s in co.get('shifts', []):
            st.markdown(f"- {s['text']}")
    with c2:
        st.markdown("#### 🔄 Positioning Flips")
        if co.get('flips'):
            for f in co['flips']:
                st.markdown(f"- {f['text']}")
        else:
            st.markdown("*— none this week —*")

    st.markdown("#### 📊 Sector Tilt")
    for sec in co.get('sector', []):
        st.markdown(f"- {sec['text']}")

    st.divider()

    # ============================================================
    # FULL POSITIONING TABLE
    # ============================================================
    st.subheader("📋 Full Positioning Table")

    inst = pd.DataFrame(cftc['instruments'])

    def fmt_int(x):
        return f"{x:,.0f}" if pd.notna(x) else ""

    disp = pd.DataFrame({
        'Section': inst['section'],
        'Metric':  inst['label'],
        'Latest':  inst['latest'].map(fmt_int),
        'W/W Chg': inst['wow'].map(fmt_int),
        '3M Ave':  inst['ave_3m'].map(fmt_int),
        '6M Ave':  inst['ave_6m'].map(fmt_int),
        '1Y Ave':  inst['ave_1y'].map(fmt_int),
        '3Y Max':  inst['max_3y'].map(fmt_int),
        '3Y Min':  inst['min_3y'].map(fmt_int),
        'Z-1Y':    inst['z_1y'],
        'Z-3Y':    inst['z_3y'],
    })

    # Z-score heatmap: green (long) <-> red (short), intensity by |z|
    def z_color(val):
        if pd.isna(val):
            return ''
        a = min(abs(val) / 3.0, 1.0)
        if val >= 0:
            r = int(220 - a*120); g = int(245 - a*40); b = int(220 - a*120)
            return f'background-color: rgb({r},{g},{b}); color: #0a3d0a'
        else:
            r = int(250 - a*0); g = int(225 - a*140); b = int(225 - a*140)
            return f'background-color: rgb({r},{g},{b}); color: #5c0000'

    def wow_color(val_str):
        try:
            v = float(str(val_str).replace(',', ''))
        except:
            return ''
        if v > 0:
            return 'color: #006100'
        elif v < 0:
            return 'color: #9c0006'
        return ''

    def fmt_z(x):
        return f"{x:+.2f}" if pd.notna(x) else "n/a"

    # Section filter
    sections = ['ALL'] + list(inst['section'].unique())
    pick = st.radio("Filter section", sections, horizontal=True)
    view = disp if pick == 'ALL' else disp[disp['Section'] == pick]

    styled = (view.style
              .map(z_color, subset=['Z-1Y', 'Z-3Y'])
              .map(wow_color, subset=['W/W Chg'])
              .format({'Z-1Y': fmt_z, 'Z-3Y': fmt_z}))

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=min(1000, 80 + len(view) * 35),
        column_config={
            "Section": st.column_config.TextColumn(width="small"),
            "Metric":  st.column_config.TextColumn(width="medium", pinned=True),
        },
    )

    with st.expander("📖 How to read this"):
        st.markdown("""
        - **Non-Commercial Net** = large speculators' Long minus Short positions (futures).
        - **Positive** = net long (bullish positioning); **Negative** = net short (bearish).
        - **W/W Chg** = change vs last week (green = added longs, red = added shorts).
        - **Z-Score** = how stretched current positioning is vs its own history.
          - **+2 or higher** = crowded long (potential reversal/squeeze risk).
          - **−2 or lower** = crowded short.
        - **Note on direction:** Bonds net-long = betting yields *fall*. Currencies are *vs USD*
          (long EUR = bearish USD). VIX net-short = complacency.
        - Contrarian signal: extreme positioning often precedes mean reversion.
        """)

    st.divider()
    st.caption("📊 Source: CFTC Commitments of Traders (Legacy, Futures-Only) | Updated weekly")

# ============================================================
# TAB 6: SECTOR ROTATION (RRG)
# ============================================================
with tab6:
    st.title("🔄 Sector Rotation (RRG)")
    st.caption("🤖 Updated daily | 11 SPDR sectors vs SPY benchmark")

    smeta, sprices, serr = load_sectors_data()
    if serr:
        st.error(f"❌ Error loading sector data: {serr}")
        st.info("💡 Data appears after the Sector RRG workflow runs.")
        st.stop()

    st.caption(f"📅 As of {smeta['as_of']} | 🔄 Generated {smeta['generated']}")

    co = smeta['callouts']
    SECTOR_NAMES = {r['ticker']: r['sector'] for r in smeta['performance']}

    # ============================================================
    # SUMMARY CARDS
    # ============================================================
    qc = co['quad_counts']
    n_rotating = len(co['rotations'])
    m1, m2, m3 = st.columns(3)
    m1.metric("🟢 Leading", qc['Leading'], help="Strong + gaining momentum")
    m2.metric("🔴 Lagging", qc['Lagging'], help="Weak + losing momentum")
    m3.metric("🔄 Rotating", n_rotating, help="Crossed a quadrant this week")

    st.info("📌 Summary callouts below use **fixed weekly** data. The chart further down is interactive (Daily/Weekly/Monthly).")

    # ============================================================
    # CALLOUTS
    # ============================================================
    st.subheader("🎯 Rotation Highlights")

    st.markdown("#### 🔄 Rotation Alerts (this week)")
    if co['rotations']:
        for r in co['rotations']:
            st.markdown(f"- {r['text']}")
    else:
        st.markdown("*No quadrant crossings this week — positioning stable.*")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 💪 Leaders")
        if co['leaders']:
            for tk in co['leaders']:
                st.markdown(f"- 🟢 **{tk}** — {SECTOR_NAMES.get(tk, tk)}")
        else:
            st.markdown("*— none —*")
    with c2:
        st.markdown("#### 🐌 Laggards")
        if co['laggards']:
            for tk in co['laggards']:
                st.markdown(f"- 🔴 **{tk}** — {SECTOR_NAMES.get(tk, tk)}")
        else:
            st.markdown("*— none —*")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown("#### ⚡ Momentum Accelerating")
        for a in co['accel']:
            st.markdown(f"- **{a['ticker']}**  (+{a['delta']:.2f})")
    with c4:
        st.markdown("#### 📉 Momentum Decelerating")
        for d in co['decel']:
            st.markdown(f"- **{d['ticker']}**  ({d['delta']:+.2f})")

    ps = co['perf_snapshot']
    st.markdown("#### 📊 Performance Snapshot")
    st.markdown(
        f"- 🏆 **Best YTD:** {ps['best_ytd']['ticker']} ({ps['best_ytd']['val']:+.1f}%)  |  "
        f"🔻 **Worst YTD:** {ps['worst_ytd']['ticker']} ({ps['worst_ytd']['val']:+.1f}%)  |  "
        f"📈 **Today's leader:** {ps['best_1d']['ticker']} ({ps['best_1d']['val']:+.1f}%)"
    )

    with st.expander("📖 How to read the RRG (quadrant playbook)"):
        st.markdown("""
        Each sector is plotted vs the SPY benchmark. Sectors rotate **clockwise**:
        Improving → Leading → Weakening → Lagging → Improving.

        | Quadrant | Meaning | Typical Action |
        |---|---|---|
        | 🟢 **Leading** (top-right) | Strong & gaining momentum | **Overweight** — riding strength |
        | 🟡 **Weakening** (bottom-right) | Strong but momentum fading | **Trim / take profits** |
        | 🔴 **Lagging** (bottom-left) | Weak & losing momentum | **Underweight / avoid** |
        | 🔵 **Improving** (top-left) | Weak but gaining momentum | **Accumulate / watch** |

        - **RS-Ratio** (x-axis) = relative strength vs benchmark (>100 = outperforming).
        - **RS-Momentum** (y-axis) = rate of change of relative strength.
        - **Tails** show the path over recent periods — direction matters more than position.
        """)

    st.divider()

    # ============================================================
    # INTERACTIVE RRG CHART
    # ============================================================
    st.subheader("📈 Relative Rotation Graph")

    ctrl1, ctrl2 = st.columns([1, 2])
    with ctrl1:
        freq_label = st.radio("Timeframe", ['Daily', 'Weekly', 'Monthly'],
                              index=1, horizontal=True)
    with ctrl2:
        tail = st.slider("Tail length (periods)", 4, 20, 12)

    FREQ_MAP = {'Daily': ('D', 8), 'Weekly': ('W', 4), 'Monthly': ('ME', 2)}
    freq_code, smooth = FREQ_MAP[freq_label]

    # --- compute_rrg (same logic as the script, frequency-aware smoothing) ---
    def compute_rrg(prices, benchmark, tickers, freq='W',
                    rs_win=12, mom_win=10, smooth=4):
        if freq != 'D':
            px = prices.resample(freq).last().dropna(how='all')
        else:
            px = prices.copy()
        bench = px[benchmark]
        out = {}
        for tk in tickers:
            rs = (px[tk] / bench) * 100
            rs_mean = rs.rolling(rs_win).mean()
            rs_std  = rs.rolling(rs_win).std()
            rs_ratio = 100 + ((rs - rs_mean) / rs_std)
            rs_ratio = rs_ratio.rolling(smooth).mean()
            roc = (rs_ratio / rs_ratio.shift(mom_win) - 1) * 100
            roc = roc.rolling(smooth).mean()
            mom_mean = roc.rolling(rs_win).mean()
            mom_std  = roc.rolling(rs_win).std()
            rs_mom = 100 + ((roc - mom_mean) / mom_std)
            rs_mom = rs_mom.rolling(smooth).mean()
            out[tk] = pd.DataFrame({'rs_ratio': rs_ratio,
                                    'rs_momentum': rs_mom}).dropna()
        return out

    SECTOR_TICKERS = [r['ticker'] for r in smeta['performance'] if r['ticker'] != 'SPY']
    rrg = compute_rrg(sprices, 'SPY', SECTOR_TICKERS, freq=freq_code, smooth=smooth)

    # --- determine plot bounds ---
    all_r, all_m = [], []
    for df in rrg.values():
        t = df.tail(tail)
        all_r += t['rs_ratio'].tolist()
        all_m += t['rs_momentum'].tolist()
    if all_r:
        pad = 0.5
        xmin, xmax = min(all_r)-pad, max(all_r)+pad
        ymin, ymax = min(all_m)-pad, max(all_m)+pad
    else:
        xmin, xmax, ymin, ymax = 97, 103, 97, 103

    fig = go.Figure()

    # Quadrant background shading
    fig.add_shape(type="rect", x0=100, y0=100, x1=xmax, y1=ymax,
                  fillcolor="green", opacity=0.06, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=100, y0=ymin, x1=xmax, y1=100,
                  fillcolor="gold", opacity=0.06, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=xmin, y0=ymin, x1=100, y1=100,
                  fillcolor="red", opacity=0.06, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=xmin, y0=100, x1=100, y1=ymax,
                  fillcolor="blue", opacity=0.06, line_width=0, layer="below")
    fig.add_hline(y=100, line_width=1, line_color="black")
    fig.add_vline(x=100, line_width=1, line_color="black")

    # Per-sector tails
    palette = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b',
               '#e377c2','#7f7f7f','#bcbd22','#17becf','#aec7e8']
    for i, tk in enumerate(SECTOR_TICKERS):
        df = rrg.get(tk)
        if df is None or len(df) < 2:
            continue
        t = df.tail(tail)
        color = palette[i % len(palette)]
        # tail line
        fig.add_trace(go.Scatter(
            x=t['rs_ratio'], y=t['rs_momentum'], mode='lines',
            line=dict(color=color, width=1.5), opacity=0.6,
            name=tk, legendgroup=tk, showlegend=False, hoverinfo='skip'))
        # head marker
        fig.add_trace(go.Scatter(
            x=[t['rs_ratio'].iloc[-1]], y=[t['rs_momentum'].iloc[-1]],
            mode='markers+text', marker=dict(color=color, size=12,
                                             line=dict(color='black', width=1)),
            text=[tk], textposition='top center', textfont=dict(size=10),
            name=tk, legendgroup=tk,
            hovertemplate=f"<b>{tk}</b> — {SECTOR_NAMES.get(tk, '')}<br>"
                          f"RS-Ratio: %{{x:.2f}}<br>RS-Mom: %{{y:.2f}}<extra></extra>"))

    # Quadrant labels
    fig.add_annotation(x=xmax, y=ymax, text="Leading", showarrow=False,
                       xanchor="right", yanchor="top", font=dict(color="green", size=14))
    fig.add_annotation(x=xmax, y=ymin, text="Weakening", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(color="goldenrod", size=14))
    fig.add_annotation(x=xmin, y=ymin, text="Lagging", showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(color="red", size=14))
    fig.add_annotation(x=xmin, y=ymax, text="Improving", showarrow=False,
                       xanchor="left", yanchor="top", font=dict(color="blue", size=14))

    fig.update_layout(
        height=650,
        xaxis=dict(title="JdK RS-Ratio", range=[xmin, xmax]),
        yaxis=dict(title="JdK RS-Momentum", range=[ymin, ymax]),
        showlegend=False, hovermode='closest',
        margin=dict(t=30, b=40),
        title=f"{freq_label} · {tail}-period tail"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ============================================================
    # PERFORMANCE TABLE
    # ============================================================
    st.subheader("📋 Sector Performance")

    perf_df = pd.DataFrame(smeta['performance'])
    disp = pd.DataFrame({
        'Sector': perf_df['sector'],
        'Ticker': perf_df['ticker'],
        'Price':  perf_df['price'].map(lambda x: f"${x:,.2f}"),
        '1-Day %': perf_df['d1'],
        'MTD %':   perf_df['mtd'],
        'QTD %':   perf_df['qtd'],
        'YTD %':   perf_df['ytd'],
    })

    def color_pct(v):
        if pd.isna(v):
            return ''
        return ('background-color: #1a7d3c; color: white' if v >= 0
                else 'background-color: #c0392b; color: white')

    styled = (disp.style
              .map(color_pct, subset=['1-Day %', 'MTD %', 'QTD %', 'YTD %'])
              .format({'1-Day %': '{:+.2f}%', 'MTD %': '{:+.2f}%',
                       'QTD %': '{:+.2f}%', 'YTD %': '{:+.2f}%'}))

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=min(600, 80 + len(disp) * 35),
        column_config={
            "Sector": st.column_config.TextColumn(width="large"),
            "Ticker": st.column_config.TextColumn(width="small", pinned=True),
        },
    )

    st.divider()
    st.caption("📊 Source: Yahoo Finance | RRG computed vs SPY | Updated daily via GitHub Actions")

# ============================================================
# TAB 7: CROSS-ASSET VOLATILITY + USD CORRELATIONS
# ============================================================
with tab7:
    st.title("🌐 Cross-Asset Volatility & Flows")
    st.caption("🤖 Updated daily | Vol across equities/commodities + $USD correlations")

    ca_meta, ca_series, ca_err = load_crossasset_data()
    if ca_err:
        st.error(f"❌ Error loading cross-asset data: {ca_err}")
        st.info("💡 Data appears after the Cross-Asset workflow runs.")
        st.stop()

    st.caption(f"📅 As of {ca_meta['as_of']} | 🔄 Generated {ca_meta['generated']}")

    ca_co = ca_meta['callouts']
    ca_vol = ca_meta['vol_metrics']
    ca_corr = ca_meta['correlations']

    # ============================================================
    # SUMMARY CARDS
    # ============================================================
    breadth = ca_co['vol_breadth']
    ca_m1, ca_m2, ca_m3 = st.columns(3)
    ca_m1.metric("Vol Breadth (rising WoW)",
                 f"{breadth['rising']}/{breadth['total']}",
                 help="How many vol indices rose this week")
    gold_30 = ca_corr.get('GOLD', {}).get('30d')
    ca_m2.metric("Gold–USD Corr (30D)",
                 f"{gold_30:+.2f}" if gold_30 is not None else "n/a",
                 help="The classic dollar barometer (negative = inverse)")
    spx_30 = ca_corr.get('SPX', {}).get('30d')
    ca_m3.metric("SPX–USD Corr (30D)",
                 f"{spx_30:+.2f}" if spx_30 is not None else "n/a",
                 help="Risk-on usually = weak dollar (negative)")

    # ============================================================
    # CALLOUTS
    # ============================================================
    st.subheader("🎯 Cross-Asset Highlights")
    st.markdown("#### 🌪️ Volatility")
    for c in ca_co['vol']:
        st.markdown(f"- {c}")
    st.markdown("#### 💵 $USD Correlations")
    for c in ca_co['corr']:
        st.markdown(f"- {c}")

    with st.expander("📖 What am I looking at? (cross-asset vol & 'the flows')"):
        st.markdown("""
        **Why watch volatility across asset classes?**
        Volatility is the market's "fear gauge" — and it shows up everywhere, not just stocks.
        Monitoring it across assets tells you whether stress is **broad** or **localized**:
        - **VIX** = S&P 500 volatility (equity fear)
        - **VXN** = Nasdaq volatility (tech fear — usually higher than VIX)
        - **GVZ** = Gold volatility
        - **OVX** = Oil volatility (usually the highest — oil is jumpy)

        When **all** of these rise together → broad, systemic risk-off (more meaningful).
        When they **diverge** (e.g., equity vol up but oil vol down) → stress is concentrated,
        not a market-wide panic. The **breadth** reading (how many are rising) is the quick tell.

        ---
        **What are "the flows" and why does the dollar matter?**
        The US Dollar is the world's funding currency, so it sits at the center of "flows" —
        how money moves between asset classes. The **rolling correlation** of each asset to the
        dollar reveals the current regime:
        - **Gold –0.5 to –0.9** = classic inverse (strong dollar pressures gold). This is the
          single most-watched "dollar barometer."
        - **SPX negative** = risk-on means money flows *out* of the safe-haven dollar *into* stocks.
        - **Oil's relationship flips** depending on whether it's a growth story or a supply story.

        **The key signal: when a long-standing correlation FLIPS SIGN**, the regime is changing.
        E.g., if Gold suddenly turns *positive* to the dollar, the usual playbook is breaking down —
        worth paying attention to.

        ---
        **"Flows" (volume)** — Hedgeye also watches *volume* as confirmation: a rally on light
        volume = weak conviction; a selloff on heavy volume = real distribution. *(Volume/flows
        analysis is planned as a Tier-2 addition.)*
        """)

    st.divider()

    # ============================================================
    # CROSS-ASSET VOLATILITY CHART (OVX on right axis)
    # ============================================================
    st.subheader("📈 Cross-Asset Volatility")

    ca_fig = go.Figure()
    left_axis = {'VIX': 'black', 'VXN': '#666666', 'GVZ': '#d99000'}
    for col, color in left_axis.items():
        if col in ca_series.columns:
            ca_fig.add_trace(go.Scatter(
                x=ca_series.index, y=ca_series[col], name=col,
                line=dict(color=color, width=1.2), yaxis='y'))
    if 'OVX' in ca_series.columns:
        ca_fig.add_trace(go.Scatter(
            x=ca_series.index, y=ca_series['OVX'], name='OVX (RHS)',
            line=dict(color='#1f9ed6', width=1.2), yaxis='y2'))

    ca_fig.update_layout(
        height=480, hovermode='x unified',
        yaxis=dict(title='Volatility (VIX/VXN/GVZ)'),
        yaxis2=dict(title='OVX (Oil)', overlaying='y', side='right',
                    color='#1f9ed6'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=40)
    )
    st.plotly_chart(ca_fig, use_container_width=True)

    # ---- Vol metrics table ----
    def ca_fmt_vol_row(tk, m):
        def cell(diff, pct):
            return f"{diff:+.2f} ({pct:+.1f}%)" if pct is not None else f"{diff:+.2f}"
        return {
            'Series': m['name'],
            'Last': f"{m['last']:.2f}",
            '1D Ago': f"{m['d1']:.2f}",
            '1W Ago': f"{m['w1']:.2f}",
            '1M Ago': f"{m['m1']:.2f}",
            'DoD': cell(*m['dod']),
            'WoW': cell(*m['wow']),
            'MoM': cell(*m['mom']),
        }

    ca_vol_tbl = pd.DataFrame([ca_fmt_vol_row(tk, m) for tk, m in ca_vol.items()])

    def ca_vol_color(val_str):
        # rising vol = red (risk-off), falling = green
        try:
            pct = float(val_str.split('(')[1].split('%')[0])
        except:
            return ''
        return ('background-color: #ffc7ce; color: #9c0006' if pct >= 0
                else 'background-color: #c6efce; color: #006100')

    ca_vol_styled = ca_vol_tbl.style.map(ca_vol_color, subset=['DoD', 'WoW', 'MoM'])
    st.dataframe(ca_vol_styled, use_container_width=True, hide_index=True)
    st.caption("🌪️ Rising vol = red (risk-off) · Falling vol = green (risk-on)")

    st.divider()

    # ============================================================
    # USD CORRELATION TABLE
    # ============================================================
    st.subheader("💵 Key $USD Correlations")
    st.caption("Rolling correlation of each asset vs the US Dollar Index (DXY). "
               "Negative = inverse to USD.")

    windows = ca_meta['corr_windows']
    corr_rows = []
    for a, row in ca_corr.items():
        d = {'Asset': a}
        for w in windows:
            d[f'{w}D'] = row.get(f'{w}d')
        d['52w Hi'] = row.get('hi_52w')
        d['52w Lo'] = row.get('lo_52w')
        d['% Pos'] = f"{row.get('pct_pos', 0)}%"
        d['% Neg'] = f"{row.get('pct_neg', 0)}%"
        corr_rows.append(d)
    ca_corr_df = pd.DataFrame(corr_rows)

    def corr_color(v):
        if pd.isna(v) or not isinstance(v, (int, float)):
            return ''
        a = min(abs(v), 1.0)
        if v < 0:  # inverse to USD -> red gradient (the "expected" strong inverse)
            r = int(255); g = int(230 - a*140); b = int(230 - a*140)
            return f'background-color: rgb({r},{g},{b}); color: #5c0000'
        else:      # positive corr -> green
            r = int(230 - a*120); g = int(245 - a*40); b = int(230 - a*120)
            return f'background-color: rgb({r},{g},{b}); color: #0a3d0a'

    corr_num_cols = [f'{w}D' for w in windows] + ['52w Hi', '52w Lo']
    ca_corr_styled = (ca_corr_df.style
                      .map(corr_color, subset=corr_num_cols)
                      .format({c: '{:+.2f}' for c in corr_num_cols}, na_rep='n/a'))
    st.dataframe(ca_corr_styled, use_container_width=True, hide_index=True)
    st.caption("🔴 Negative (inverse to USD) · 🟢 Positive (moves with USD) · "
               "Sign flips = regime change")

    st.divider()
    st.caption("📊 Source: Yahoo Finance | VIX/VXN/GVZ/OVX + DXY correlations | Updated daily")

# ============================================================
# TAB 0: DAILY BRIEFING (LANDING PAGE)
# ============================================================
with tab0:
    st.title("📋 Daily Macro Briefing")
    st.caption("🤖 Aggregated from all dashboard signals · reads latest available data")

    # ---- Load all sources defensively (graceful degradation) ----
    sm_df, sm_gamma, _, sm_err = load_data()
    sm_port, _, sm_port_err = load_portfolio_data()
    sm_debt, _, sm_debt_err = load_debt_data()
    sm_cftc, sm_cftc_err = load_cftc_data()
    sm_sect, _, sm_sect_err = load_sectors_data()
    sm_ca, _, sm_ca_err = load_crossasset_data()

    # ---------- Helper: VIX -> stress 0-100 ----------
    def vix_to_stress(vix):
        # ~12 = calm (0), ~40 = max stress (100); clamp
        return float(max(0, min(100, (vix - 12) / (40 - 12) * 100)))

    # ---------- Gather component stress readings ----------
    # MACRO STRESS WEIGHTS (tunable — see expander for rationale)
    MACRO_WEIGHTS = {
        'debt':       0.30,   # credit leads; most forward-looking
        'equity_vol': 0.25,   # VIX — immediate fear gauge
        'cross_vol':  0.25,   # breadth of fear across assets
        'cftc':       0.20,   # positioning fragility (slow-moving)
    }

    components = {}   # name -> (stress_value_0_100, label_text)

    # Debt component
    if sm_debt and not sm_debt_err:
        try:
            ds = sm_debt['risk']['score']
            components['debt'] = (float(ds), f"Debt Risk {ds:.0f}/100")
        except Exception:
            pass

    # Equity vol component (VIX from CRR data)
    vix_val = None
    if sm_df is not None and not sm_err:
        try:
            vix_row = sm_df[sm_df['Ticker'] == '^VIX']
            if not vix_row.empty:
                vix_val = float(vix_row['Close'].values[0])
                components['equity_vol'] = (vix_to_stress(vix_val), f"VIX {vix_val:.1f}")
        except Exception:
            pass

    # Cross-asset vol component (breadth -> stress)
    if sm_ca and not sm_ca_err:
        try:
            br = sm_ca['callouts']['vol_breadth']
            # more rising = more stress
            cv = (br['rising'] / br['total']) * 100 if br['total'] else 0
            components['cross_vol'] = (float(cv), f"Vol breadth {br['rising']}/{br['total']}")
        except Exception:
            pass

    # CFTC crowding component (# extremes -> stress, capped)
    if sm_cftc and not sm_cftc_err:
        try:
            n_ext = len(sm_cftc.get('callouts', {}).get('extremes', []))
            # 0 extremes = 0 stress; ~10+ extremes = high. Scale.
            cc = min(100, n_ext / 10 * 100)
            components['cftc'] = (float(cc), f"{n_ext} crowded extremes")
        except Exception:
            pass

    # ---------- Composite (re-weight over available components) ----------
    avail = {k: v for k, v in components.items() if k in MACRO_WEIGHTS}
    if avail:
        total_w = sum(MACRO_WEIGHTS[k] for k in avail)
        macro_score = sum(avail[k][0] * MACRO_WEIGHTS[k] for k in avail) / total_w
        macro_score = round(macro_score)
        n_used = len(avail)
        if macro_score >= 70:   macro_regime, mc_color = "HIGH STRESS", "#9c0006"
        elif macro_score >= 45: macro_regime, mc_color = "ELEVATED", "#e07b00"
        elif macro_score >= 30: macro_regime, mc_color = "NEUTRAL", "#b5a000"
        else:                   macro_regime, mc_color = "CALM", "#2e9e4f"
    else:
        macro_score, macro_regime, mc_color, n_used = None, "n/a", "#888", 0

    # ============================================================
    # MACRO STRESS GAUGE
    # ============================================================
    st.subheader("🌡️ Macro Stress Composite")
    if macro_score is not None:
        mg = go.Figure(go.Indicator(
            mode="gauge+number",
            value=macro_score,
            number={'suffix': "/100", 'font': {'size': 44},
                    'valueformat': '.0f'},
            title={'text': f"<b>{macro_regime}</b>", 'font': {'size': 22}},
            domain={'x': [0, 1], 'y': [0, 0.85]},   # leave room at bottom for number
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1},
                'bar': {'color': "rgba(0,0,0,0.7)", 'thickness': 0.25},
                'steps': [
                    {'range': [0, 30],  'color': '#2e9e4f'},
                    {'range': [30, 45], 'color': '#e8d200'},
                    {'range': [45, 70], 'color': '#e07b00'},
                    {'range': [70, 100],'color': '#9c0006'},
                ],
                'threshold': {'line': {'color': "black", 'width': 4},
                              'thickness': 0.85, 'value': macro_score},
            }
        ))
        mg.update_layout(height=300, margin=dict(t=60, b=20, l=30, r=30))
        st.plotly_chart(mg, use_container_width=True)
        if n_used < len(MACRO_WEIGHTS):
            st.caption(f"⚠️ Based on {n_used} of {len(MACRO_WEIGHTS)} components "
                       f"(some feeds unavailable — re-weighted proportionally).")

        # Component contributions
        comp_cols = st.columns(len(MACRO_WEIGHTS))
        labels = {'debt': '🏦 Debt', 'equity_vol': '📊 Equity Vol',
                  'cross_vol': '🌐 Cross Vol', 'cftc': '📊 CFTC'}
        for col, key in zip(comp_cols, MACRO_WEIGHTS):
            if key in avail:
                col.metric(labels[key], f"{avail[key][0]:.0f}",
                           help=f"{avail[key][1]} · weight {MACRO_WEIGHTS[key]:.0%}")
            else:
                col.metric(labels[key], "n/a", help="feed unavailable")
    else:
        st.warning("Macro Stress unavailable — no component feeds loaded yet.")

    with st.expander("📖 How the Macro Stress score works (and its limits)"):
        st.markdown("""
        A single 0–100 blend of cross-asset stress signals (**0 = calm, 100 = max stress**).

        | Component | Weight | Why |
        |---|---|---|
        | 🏦 **Debt Risk** | 30% | Credit leads — stress shows in bonds *before* equities |
        | 📊 **Equity Vol (VIX)** | 25% | Real-time fear gauge, but *reactive* |
        | 🌐 **Cross-Asset Vol** | 25% | Breadth — fear across oil/gold/equities = systemic |
        | 📊 **CFTC Crowding** | 20% | Positioning *fragility* (slow-moving) |

        ⚠️ **Important caveats:**
        - These weights are **educated judgment, not backtested** — there's no way to validate
          them here. Someone rates-focused might weight debt 50%.
        - **Watch the TREND, not the absolute number.** "Jumped 35→60 this week" is the signal,
          not whether 60 is objectively "right."
        - It's a **conversation starter** ("why did this move?"), not a trade signal.
        - If a feed is down, the score re-weights over available components.
        """)

    st.divider()

    # ============================================================
    # AT-A-GLANCE SCORECARD
    # ============================================================
    st.subheader("📊 At a Glance")
    sc1, sc2, sc3 = st.columns(3)

    # Equity regime (VIX status + Machine)
    with sc1:
        if vix_val is not None:
            if vix_val <= 19: vstat = "INVESTABLE"
            elif vix_val <= 30: vstat = "CHOP"
            else: vstat = "F-BUCKET"
            st.metric("📊 Equity Regime", vstat, help=f"VIX {vix_val:.1f}")
        else:
            st.metric("📊 Equity Regime", "n/a")

    # Debt risk
    with sc2:
        if 'debt' in avail:
            try:
                st.metric("🏦 Debt Risk", f"{sm_debt['risk']['score']:.0f}/100",
                          help=sm_debt['risk']['regime'])
            except Exception:
                st.metric("🏦 Debt Risk", "n/a")
        else:
            st.metric("🏦 Debt Risk", "n/a")

    # Cross-asset vol
    with sc3:
        if sm_ca and not sm_ca_err:
            try:
                br = sm_ca['callouts']['vol_breadth']
                tone = ("Risk-off" if br['rising'] >= br['total']*0.75
                        else "Calm" if br['rising'] <= 1 else "Mixed")
                st.metric("🌐 Cross-Asset Vol", tone,
                          help=f"{br['rising']}/{br['total']} rising WoW")
            except Exception:
                st.metric("🌐 Cross-Asset Vol", "n/a")
        else:
            st.metric("🌐 Cross-Asset Vol", "n/a")

    sc4, sc5, sc6 = st.columns(3)

    # Sector leaders
    with sc4:
        if sm_sect and not sm_sect_err:
            try:
                leaders = sm_sect['callouts']['leaders']
                st.metric("🔄 Sector Leaders",
                          ", ".join(leaders[:3]) if leaders else "none",
                          help="Leading quadrant (RRG)")
            except Exception:
                st.metric("🔄 Sector Leaders", "n/a")
        else:
            st.metric("🔄 Sector Leaders", "n/a")

    # CFTC extremes
    with sc5:
        if sm_cftc and not sm_cftc_err:
            try:
                n_ext = len(sm_cftc.get('callouts', {}).get('extremes', []))
                st.metric("📊 CFTC Extremes", f"{n_ext}",
                          help="Crowded positions (|Z|≥2)")
            except Exception:
                st.metric("📊 CFTC Extremes", "n/a")
        else:
            st.metric("📊 CFTC Extremes", "n/a")

    # Portfolio actions
    with sc6:
        if sm_port is not None and not sm_port_err:
            try:
                buys = int(sm_port['Action'].str.contains('BUY').sum())
                sells = int(sm_port['Action'].str.contains('SELL').sum())
                st.metric("💼 Portfolio", f"{buys} Buy / {sells} Sell")
            except Exception:
                st.metric("💼 Portfolio", "n/a")
        else:
            st.metric("💼 Portfolio", "n/a")

    st.divider()

    # ============================================================
    # KEY SIGNALS TODAY
    # ============================================================
    st.subheader("🔑 Key Signals Today")
    key_signals = []

    # Top debt highlight (first risk-off, else first risk-on)
    if sm_debt and not sm_debt_err:
        try:
            hloff = sm_debt['highlights']['risk_off']
            hlon = sm_debt['highlights']['risk_on']
            if hloff:
                key_signals.append(f"🏦 {hloff[0]}")
            elif hlon:
                key_signals.append(f"🏦 {hlon[0]}")
        except Exception:
            pass

    # Top sector rotation
    if sm_sect and not sm_sect_err:
        try:
            rots = sm_sect['callouts']['rotations']
            if rots:
                key_signals.append(f"🔄 {rots[0]['text']}")
        except Exception:
            pass

    # Top CFTC extreme
    if sm_cftc and not sm_cftc_err:
        try:
            exts = sm_cftc.get('callouts', {}).get('extremes', [])
            if exts:
                key_signals.append(f"📊 CFTC: {exts[0]['text']}")
        except Exception:
            pass

    # Cross-asset vol read
    if sm_ca and not sm_ca_err:
        try:
            volc = sm_ca['callouts']['vol']
            if volc:
                key_signals.append(f"🌐 {volc[0]}")
        except Exception:
            pass

    # Gold-USD correlation note
    if sm_ca and not sm_ca_err:
        try:
            g30 = sm_ca['correlations'].get('GOLD', {}).get('30d')
            if g30 is not None:
                key_signals.append(
                    f"💵 Gold–USD correlation at {g30:+.2f} (30D) — "
                    f"{'strong inverse intact' if g30 < -0.4 else 'watch for shift'}")
        except Exception:
            pass

    if key_signals:
        for s in key_signals:
            st.markdown(f"- {s}")
    else:
        st.markdown("*No signals loaded — check that workflows have run.*")

    st.divider()

    # ============================================================
    # WHAT CHANGED (trend changes / rotations / flips)
    # ============================================================
    st.subheader("⚠️ What Changed")
    changes = []

    # Debt trend changes
    if sm_debt and not sm_debt_err:
        try:
            for panel_key, panel in sm_debt['panels'].items():
                tc = panel.get('trend', {})
                if tc.get('change'):
                    nm = panel.get('name', panel_key)
                    changes.append(
                        f"🏦 **{nm}** trend change: {tc['trend']} "
                        f"[{tc['strength']}, {tc['score']}/100]")
        except Exception:
            pass

    # Sector rotations (all this week)
    if sm_sect and not sm_sect_err:
        try:
            for r in sm_sect['callouts']['rotations']:
                changes.append(f"🔄 {r['text']}")
        except Exception:
            pass

    # CFTC positioning flips
    if sm_cftc and not sm_cftc_err:
        try:
            for f in sm_cftc.get('callouts', {}).get('flips', []):
                changes.append(f"📊 CFTC: {f['text']}")
        except Exception:
            pass

    # USD correlation flips
    if sm_ca and not sm_ca_err:
        try:
            for a, row in sm_ca['correlations'].items():
                if row.get('flipped'):
                    c30 = row.get('30d')
                    changes.append(
                        f"💵 **{a}–USD correlation flipped** (30D {c30:+.2f}) — possible regime shift")
        except Exception:
            pass

    if changes:
        for c in changes:
            st.markdown(f"- {c}")
    else:
        st.markdown("*No notable changes detected — conditions stable.*")

    st.divider()

    # ============================================================
    # DATA FRESHNESS
    # ============================================================
    st.subheader("🕐 Data Freshness")
    freshness = []
    if sm_debt and not sm_debt_err:
        freshness.append(("Debt Markets", sm_debt.get('as_of', '?')))
    if sm_cftc and not sm_cftc_err:
        freshness.append(("CFTC", sm_cftc.get('report_date', '?')))
    if sm_sect and not sm_sect_err:
        freshness.append(("Sector RRG", sm_sect.get('as_of', '?')))
    if sm_ca and not sm_ca_err:
        freshness.append(("Cross-Asset", sm_ca.get('as_of', '?')))

    if freshness:
        fcols = st.columns(len(freshness))
        for col, (name, date) in zip(fcols, freshness):
            col.markdown(
                f"<div style='font-size:13px; color:#666; font-weight:600;'>{name}</div>"
                f"<div style='font-size:18px; color:#262730;'>{date}</div>",
                unsafe_allow_html=True
            )

    st.caption("📋 Daily Briefing aggregates all dashboard tabs. "
               "Click any tab above for full detail.")
    st.caption("⚠️ Macro Stress is a heuristic, not a validated model — watch the trend.")
