import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE = "http://localhost:8000/v1"

st.set_page_config(page_title="Financial Recommender", layout="wide")
st.title("Financial Recommender Dashboard")

with st.sidebar:
    symbol = st.text_input("Symbol", value="AAPL").upper()
    asset_type = st.selectbox("Asset Type", ["stock", "crypto", "etf"], index=0)
    risk_profile = st.selectbox("Risk Profile", ["conservative", "balanced", "aggressive"], index=1)

col1, col2, col3 = st.columns(3)

if col1.button("Ingest Market Data"):
    response = requests.post(f"{API_BASE}/market/ingest/{symbol}", params={"asset_type": asset_type}, timeout=60)
    if response.ok:
        st.success(response.json())
    else:
        st.error(response.text)

if col2.button("Run Analysis"):
    response = requests.get(f"{API_BASE}/analysis/{symbol}", timeout=60)
    if response.ok:
        st.json(response.json())
    else:
        st.error(response.text)

if col3.button("Get Recommendation"):
    payload = {"symbol": symbol, "risk_profile": risk_profile, "asset_type": asset_type}
    response = requests.post(f"{API_BASE}/recommendations", json=payload, timeout=60)
    if response.ok:
        st.json(response.json())
    else:
        st.error(response.text)

st.subheader("Local Price Preview")
try:
    analysis_response = requests.get(f"{API_BASE}/analysis/{symbol}", timeout=60)
    if analysis_response.ok:
        data = analysis_response.json()
        frame = pd.DataFrame(
            {
                "metric": ["latest_close", "sma_20", "sma_50", "volatility_30d", "momentum_30d"],
                "value": [
                    data["latest_close"],
                    data["sma_20"],
                    data["sma_50"],
                    data["volatility_30d"],
                    data["momentum_30d"],
                ],
            }
        )
        fig = px.bar(frame, x="metric", y="value", title=f"Technical snapshot: {symbol}")
        st.plotly_chart(fig, use_container_width=True)
except requests.RequestException:
    st.info("API not reachable yet. Start backend with `make run-api`.")
