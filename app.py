import streamlit as st
import pandas as pd
from datetime import datetime

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

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_data():
    """Load data from GitHub CSV"""
    try:
        df = pd.read_csv(CSV_URL)
        return df, None
    except Exception as e:
        return None, str(e)

# ============================================================
# MAIN APP
# ============================================================
st.title("📊 Daily CRR Analysis Dashboard")
st.caption("🤖 Automated updates daily at 7pm UTC")

# Load data
df, error = load_data()

if error:
    st.error(f"❌ Error loading data: {error}")
    st.stop()

if df is None:
    st.warning("⚠️ No data available")
    st.stop()

# ============================================================
# SUMMARY METRICS
# ============================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Tickers", len(df))

with col2:
    bullish_count = df[df['Trade'] == 'Bullish'].shape[0]
    st.metric("Bullish Signals", bullish_count)

with col3:
    bearish_count = df[df['Trade'] == 'Bearish'].shape[0]
    st.metric("Bearish Signals", bearish_count)

with col4:
    avg_ss_score = df['SS_Score'].mean()
    st.metric("Avg Signal Strength", f"{avg_ss_score:.1f}")

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
# FULL DATA TABLE
# ============================================================
st.subheader("📋 Full Analysis Table")

# Create column configuration for better display
column_config = {
    "Ticker": st.column_config.TextColumn("Ticker", width="small"),
    "Close": st.column_config.NumberColumn("Close", format="%.2f"),
    "SS_Score": st.column_config.NumberColumn("SS Score", format="%.0f"),
    "SS_Status": st.column_config.TextColumn("Status", width="medium"),
    "Trade": st.column_config.TextColumn("Trade", width="small"),
    "Trend": st.column_config.TextColumn("Trend", width="small"),
    "RSI": st.column_config.NumberColumn("RSI", format="%.1f"),
}

# Display full table
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config=column_config
)

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
