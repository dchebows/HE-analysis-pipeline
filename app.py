import streamlit as st
import pandas as pd
from datetime import datetime
import json
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

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
# TAB NAVIGATION
# ============================================================
tab1, tab2 = st.tabs(["📊 CRR Analysis", "💼 Portfolio Signals"])

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
    display_df = df.copy()
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

    # Display styled table
    st.dataframe(styled_df, use_container_width=True, height=600)

    # Add data refresh timestamp at bottom
    if spx_gamma and 'timestamp' in spx_gamma:
        data_timestamp = spx_gamma['timestamp']
    else:
        data_timestamp = "Unknown"

    st.caption(f"🔄 Data generated: {data_timestamp} UTC | GitHub Actions runs daily at 7:00 PM EST")
    st.caption(f"📊 Dashboard cache refreshes hourly from GitHub")

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
