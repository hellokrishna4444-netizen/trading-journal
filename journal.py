import streamlit as st
import pandas as pd
import os
from datetime import datetime

DATA_FILE = "trades.csv"
IMG_DIR = "screenshots"
os.makedirs(IMG_DIR, exist_ok=True)

ALL_COLUMNS = [
    "Date", "Pair", "Session", "Timeframe", "Order_Type", "Setup", 
    "Direction", "Risk_Pct", "Planned_RR", "Achieved_RR", "Max_Potential_RR",
    "Partial_Booking", "Outcome", "PnL", "Rule_Followed", "Mistake_Tag", 
    "Mindset", "Notes", "Before_Img", "After_Img"
]

if not os.path.exists(DATA_FILE):
    df = pd.DataFrame(columns=ALL_COLUMNS)
    df.to_csv(DATA_FILE, index=False)
else:
    # Purani CSV ko naye columns ke saath safely sync karein
    df = pd.read_csv(DATA_FILE)
    for col in ALL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df.to_csv(DATA_FILE, index=False)

st.set_page_config(page_title="Pro Trading Journal", layout="wide")
st.title("Local Trading Journal & Edge Analyzer")

# Sidebar: Log New Trade
with st.sidebar:
    st.header("Log New Trade")
    
    c_a, c_b = st.columns(2)
    with c_a:
        date = st.date_input("Date", datetime.today())
        pair = st.selectbox("Pair", ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "INDIAN EQUITY"])
        timeframe = st.selectbox("Entry TF", ["M1", "M3", "M5", "M15", "H1", "H4"])
    with c_b:
        session = st.selectbox("Session", ["London", "New York", "Tokyo", "Mumbai"])
        order_type = st.selectbox("Order Type", ["Limit Order", "Market Execution", "Stop Order"])
        direction = st.radio("Direction", ["Long", "Short"], horizontal=True)
        
    setup = st.text_input("Setup & Confluence (e.g., 5m OB + 3m FVG + Asian Sweep)")
    
    st.markdown("---")
    st.subheader("Risk & Partial Booking")
    r1, r2 = st.columns(2)
    with r1:
        risk_pct = st.number_input("Risk (%)", value=1.0, step=0.25)
        planned_rr = st.number_input("Planned RR", value=3.0, step=0.5)
    with r2:
        achieved_rr = st.number_input("Achieved RR", value=0.0, step=0.5)
        max_rr = st.number_input("Max Potential RR", value=0.0, step=0.5)
        
    partial_booking = st.selectbox("Partial Booking", [
        "No Partial (Full TP / SL)", 
        "50% at 1:2, Rest BE", 
        "50% at 1:2, Rest Full TP",
        "70% Booked Early, Runner BE",
        "Custom Partial (See Notes)"
    ])
    
    o1, o2 = st.columns(2)
    with o1:
        outcome = st.selectbox("Outcome", ["Win", "Partial Win", "Loss", "Breakeven", "Missed Setup"])
    with o2:
        pnl = st.number_input("Net PnL ($ / INR)", value=0.0, step=10.0)
        
    st.markdown("---")
    st.subheader("Discipline & Psychology")
    rule_followed = st.checkbox("Followed All Trading Rules?", value=True)
    mistake_tag = st.selectbox("Execution / Mistake Tag", [
        "None (Clean Execution)", "Missed by Few Pips", "Exited Too Early", 
        "Moved SL / No SL", "FOMO / Chased Entry", "Overtraded Session"
    ])
    mindset = st.selectbox("Pre-Trade Mindset", ["Calm & Focused", "Hesitant / Fearful", "FOMO / Rushed", "Overconfident"])
    notes = st.text_area("Detailed Notes (Sweep, Pips Missed, Logic)")
    
    before_img = st.file_uploader("Upload Entry Chart", type=["png", "jpg", "jpeg"])
    after_img = st.file_uploader("Upload Exit / Result Chart", type=["png", "jpg", "jpeg"])
    
    if st.button("Save Trade", use_container_width=True):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        before_path, after_path = "", ""
        
        if before_img:
            before_path = os.path.join(IMG_DIR, f"{timestamp}_before_{before_img.name}")
            with open(before_path, "wb") as f:
                f.write(before_img.getbuffer())
                
        if after_img:
            after_path = os.path.join(IMG_DIR, f"{timestamp}_after_{after_img.name}")
            with open(after_path, "wb") as f:
                f.write(after_img.getbuffer())
        
        new_row = pd.DataFrame([{
            "Date": str(date), "Pair": pair, "Session": session, "Timeframe": timeframe,
            "Order_Type": order_type, "Setup": setup, "Direction": direction,
            "Risk_Pct": risk_pct, "Planned_RR": planned_rr, "Achieved_RR": achieved_rr,
            "Max_Potential_RR": max_rr, "Partial_Booking": partial_booking,
            "Outcome": outcome, "PnL": pnl, "Rule_Followed": "Yes" if rule_followed else "No",
            "Mistake_Tag": mistake_tag, "Mindset": mindset, "Notes": notes,
            "Before_Img": before_path, "After_Img": after_path
        }])
        
        df = pd.read_csv(DATA_FILE)
        df = pd.concat([new_row, df], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        st.success("Trade Saved Successfully!")

# Main Dashboard
df = pd.read_csv(DATA_FILE)

# Filter Bar
f1, f2, f3 = st.columns(3)
with f1:
    filter_pair = st.multiselect("Filter by Pair", options=df["Pair"].dropna().unique(), default=df["Pair"].dropna().unique())
with f2:
    filter_session = st.multiselect("Filter by Session", options=df["Session"].dropna().unique(), default=df["Session"].dropna().unique())
with f3:
    filter_outcome = st.multiselect("Filter by Outcome", options=df["Outcome"].dropna().unique(), default=df["Outcome"].dropna().unique())

filtered_df = df[
    (df["Pair"].isin(filter_pair)) & 
    (df["Session"].isin(filter_session)) & 
    (df["Outcome"].isin(filter_outcome))
]

# Top Metrics
col1, col2, col3, col4, col5 = st.columns(5)
executed = filtered_df[filtered_df["Outcome"].isin(["Win", "Partial Win", "Loss", "Breakeven"])]
wins = len(filtered_df[filtered_df["Outcome"].isin(["Win", "Partial Win"])])
win_rate = (wins / len(executed) * 100) if len(executed) > 0 else 0
rule_score = (len(filtered_df[filtered_df["Rule_Followed"] == "Yes"]) / len(filtered_df) * 100) if len(filtered_df) > 0 else 0

col1.metric("Executed Trades", len(executed))
col2.metric("Win Rate (Incl. Partial)", f"{win_rate:.1f}%")
col3.metric("Net PnL", f"{filtered_df['PnL'].sum():.2f}")
col4.metric("Rule Discipline", f"{rule_score:.0f}%")
col5.metric("Missed Setups", len(filtered_df[filtered_df["Outcome"] == "Missed Setup"]))

# Cumulative PnL Chart
if len(executed) > 0:
    st.subheader("Cumulative PnL Curve")
    chart_df = executed.iloc[::-1].copy()
    chart_df["Cumulative_PnL"] = chart_df["PnL"].cumsum()
    st.line_chart(chart_df.set_index("Date")["Cumulative_PnL"])

st.divider()

# Trade History Cards
st.subheader("Trade History & Chart Previews")
for idx, row in filtered_df.iterrows():
    header_text = f"{row['Date']} | {row['Pair']} ({row['Direction']} - {row.get('Timeframe', '')}) | {row['Outcome']} | PnL: {row['PnL']}"
    with st.expander(header_text):
        c1, c2, c3 = st.columns([1.2, 2, 2])
        with c1:
            st.write(f"**Session / Order:** {row['Session']} ({row.get('Order_Type', '')})")
            st.write(f"**Setup:** {row['Setup']}")
            st.write(f"**RR (Plan / Ach / Max):** {row.get('Planned_RR', '')}R / {row.get('Achieved_RR', '')}R / {row.get('Max_Potential_RR', '')}R")
            st.write(f"**Partial:** {row.get('Partial_Booking', '')}")
            st.write(f"**Rule Followed:** {row.get('Rule_Followed', '')} | **Mindset:** {row.get('Mindset', '')}")
            st.write(f"**Tag:** {row.get('Mistake_Tag', '')}")
            st.write(f"**Notes:** {row['Notes']}")
        with c2:
            st.caption("Entry Chart")
            if pd.notna(row["Before_Img"]) and os.path.exists(str(row["Before_Img"])):
                st.image(row["Before_Img"], use_container_width=True)
            else:
                st.info("No Entry Image")
        with c3:
            st.caption("Exit / Result Chart")
            if pd.notna(row["After_Img"]) and os.path.exists(str(row["After_Img"])):
                st.image(row["After_Img"], use_container_width=True)
            else:
                st.info("No Exit Image")