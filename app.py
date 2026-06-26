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
                            'Hedgeye': [
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
    plot_data = live_preds.tail(days).copy()
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
        name='Hedgeye High',
        line=dict(color='blue', width=1, dash='dash'),
        mode='lines'
    ))
    
    fig.add_trace(go.Scatter(
        x=plot_data['date'],
        y=plot_data['hedgeye_low'],
        name='Hedgeye Low',
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
    
    plot_data = live_preds.tail(days).copy()
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
        name='Hedgeye Total Error',
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
# Change from 2 tabs to 3 tabs
tab1, tab2, tab3 = st.tabs(["📊 CRR Analysis", "💼 Portfolio Signals", "🎯 Risk Range"])

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
    # FILTERS (OPTIONAL - IN SIDEBAR)
    # ============================================================
    st.sidebar.header("🔍 Filters")

    # Filter by Trade signal
    trade_filter = st.sidebar.multiselect(
        "Trade Signal",
        options=df['Trade'].unique(),
        default=df['Trade'].unique()
    )

    # Filter by Trend signal
    trend_filter = st.sidebar.multiselect(
        "Trend Signal",
        options=df['Trend'].unique(),
        default=df['Trend'].unique()
    )

    # Filter by Warning Level
    warning_filter = st.sidebar.slider(
        "Max Warning Level",
        min_value=0,
        max_value=3,
        value=3
    )

    # Apply filters
    filtered_df = df[
        (df['Trade'].isin(trade_filter)) &
        (df['Trend'].isin(trend_filter)) &
        (df['Warn_Lvl'] <= warning_filter)
    ]

    st.sidebar.divider()
    st.sidebar.metric("Filtered Results", len(filtered_df))

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
    st.sidebar.divider()
    st.sidebar.download_button(
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
