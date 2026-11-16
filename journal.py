import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Pro Trading Journal & Cloud Vault", layout="wide")

# --- 1. PASSWORD PROTECTION ---
APP_PASSWORD = st.secrets.get("app_password", "1234")
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Locked Trading Journal")
    pwd = st.text_input("Enter Access PIN / Password", type="password")
    if st.button("Unlock Journal"):
        if pwd == str(APP_PASSWORD):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect PIN. Default PIN is 1234 (Change in Streamlit Secrets).")
    st.stop()

# --- 2. COLUMNS & STORAGE SETUP ---
ALL_COLUMNS = [
    "Date", "Pair", "Session", "Timeframe", "Order_Type", "Setup",
    "Direction", "Risk_Pct", "Planned_RR", "Achieved_RR", "Max_Potential_RR",
    "Partial_Booking", "Outcome", "PnL", "Checklist_Score", "Rule_Followed",
    "Mistake_Tag", "Mindset", "Notes", "Before_Img", "After_Img"
]

LOCAL_CSV = "trades.csv"
IMG_DIR = "screenshots"
os.makedirs(IMG_DIR, exist_ok=True)

USE_CLOUD = "gcp_service_account" in st.secrets and "sheet_url" in st.secrets

@st.cache_resource
def get_gsheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["sheet_url"]).sheet1
    return sheet

def load_data():
    if USE_CLOUD:
        try:
            sheet = get_gsheet()
            records = sheet.get_all_records()
            if not records:
                sheet.append_row(ALL_COLUMNS)
                return pd.DataFrame(columns=ALL_COLUMNS)
            df = pd.DataFrame(records)
            for col in ALL_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[ALL_COLUMNS]
        except Exception as e:
            st.error(f"Google Sheets Connection Error: {e}")
            return pd.DataFrame(columns=ALL_COLUMNS)
    else:
        if not os.path.exists(LOCAL_CSV):
            df = pd.DataFrame(columns=ALL_COLUMNS)
            df.to_csv(LOCAL_CSV, index=False)
            return df
        df = pd.read_csv(LOCAL_CSV)
        for col in ALL_COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[ALL_COLUMNS]

def save_new_trade(row_dict):
    if USE_CLOUD:
        sheet = get_gsheet()
        if not sheet.row_values(1):
            sheet.append_row(ALL_COLUMNS)
        row_values = [str(row_dict.get(col, "")) for col in ALL_COLUMNS]
        sheet.append_row(row_values)
    else:
        df = load_data()
        new_df = pd.DataFrame([row_dict])
        df = pd.concat([new_df, df], ignore_index=True)
        df.to_csv(LOCAL_CSV, index=False)

def upload_image(uploaded_file, prefix):
    if uploaded_file is None:
        return ""
    if "imgbb_api_key" in st.secrets:
        try:
            img_bytes = uploaded_file.getvalue()
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            res = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": st.secrets["imgbb_api_key"], "image": b64_img},
                timeout=15
            )
            data = res.json()
            if data.get("success"):
                return data["data"]["url"]
        except Exception as e:
            st.warning(f"Cloud image upload failed, saving locally: {e}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_path = os.path.join(IMG_DIR, f"{timestamp}_{prefix}_{uploaded_file.name}")
    with open(local_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return local_path

df = load_data()
if not df.empty:
    for num_col in ["Risk_Pct", "Planned_RR", "Achieved_RR", "Max_Potential_RR", "PnL"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0.0)

# --- 3. HEADER & SYNC STATUS ---
st.title("Pro Trading Journal & Cloud Edge Vault")
if USE_CLOUD:
    st.caption("Cloud Sync Status: ACTIVE (Connected to Google Sheets & Cloud Image Vault)")
else:
    st.info("Running in Local Mode. Add Google Sheets & ImgBB keys in Streamlit Secrets for 100% Permanent Cloud Sync.")

# --- 4. SIDEBAR: LOG NEW TRADE ---
with st.sidebar:
    st.header("Log New Trade")
    
    c1, c2 = st.columns(2)
    with c1:
        date = st.date_input("Date", datetime.today())
        pair = st.selectbox("Pair", ["XAUUSD", "EURUSD", "GBPUSD", "BTCUSD", "INDIAN EQUITY"])
        timeframe = st.selectbox("Entry TF", ["M1", "M3", "M5", "M15", "H1", "H4"])
    with c2:
        session = st.selectbox("Session", ["London", "New York", "Tokyo", "Mumbai"])
        order_type = st.selectbox("Order Type", ["Limit Order", "Market Execution", "Stop Order"])
        direction = st.radio("Direction", ["Long", "Short"], horizontal=True)
        
    setup = st.text_input("Setup & Confluence (e.g., 5m OB + 3m FVG + Sweep)")
    
    st.markdown("---")
    st.subheader("Pre-Trade Checklist")
    chk1 = st.checkbox("HTF Bias & Structure Clear?", value=True)
    chk2 = st.checkbox("Liquidity Swept Before Entry?", value=True)
    chk3 = st.checkbox("Limit Order / Valid POI?", value=True)
    chk4 = st.checkbox("Within Max 1 Trade/Session Limit?", value=True)
    checklist_score = f"{sum([chk1, chk2, chk3, chk4])}/4"
    
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
        pnl = st.number_input("Net PnL ($)", value=0.0, step=10.0)
        
    st.markdown("---")
    st.subheader("Discipline & Psychology")
    rule_followed = st.checkbox("Followed All Rules Strictly?", value=True)
    mistake_tag = st.selectbox("Execution Tag", [
        "None (Clean Execution)", "Missed by Few Pips", "Exited Too Early",
        "Moved SL / No SL", "FOMO / Chased Entry", "Overtraded Session"
    ])
    mindset = st.selectbox("Mindset", ["Calm & Focused", "Hesitant / Fearful", "FOMO / Rushed", "Overconfident"])
    notes = st.text_area("Notes (Liquidity, Pips Missed, Logic)")
    
    before_img = st.file_uploader("Upload Entry Chart", type=["png", "jpg", "jpeg"])
    after_img = st.file_uploader("Upload Exit / Result Chart", type=["png", "jpg", "jpeg"])
    
    if st.button("Save Trade to Vault", use_container_width=True):
        with st.spinner("Uploading charts and saving trade..."):
            b_url = upload_image(before_img, "before")
            a_url = upload_image(after_img, "after")
            row_data = {
                "Date": str(date), "Pair": pair, "Session": session, "Timeframe": timeframe,
                "Order_Type": order_type, "Setup": setup, "Direction": direction,
                "Risk_Pct": risk_pct, "Planned_RR": planned_rr, "Achieved_RR": achieved_rr,
                "Max_Potential_RR": max_rr, "Partial_Booking": partial_booking,
                "Outcome": outcome, "PnL": pnl, "Checklist_Score": checklist_score,
                "Rule_Followed": "Yes" if rule_followed else "No",
                "Mistake_Tag": mistake_tag, "Mindset": mindset, "Notes": notes,
                "Before_Img": b_url, "After_Img": a_url
            }
            save_new_trade(row_data)
            st.success("Trade Saved Permanently!")
            st.rerun()

# --- 5. NAVIGATION TABS ---
tab1, tab2, tab3 = st.tabs(["Trade Vault & History", "Edge & Session Analytics", "Funded Account Tracker"])

with tab1:
    if df.empty:
        st.info("No trades logged yet. Use the left sidebar to log your first trade!")
    else:
        f1, f2, f3 = st.columns(3)
        with f1:
            pairs = df["Pair"].dropna().unique().tolist()
            f_pair = st.multiselect("Filter Pair", pairs, default=pairs)
        with f2:
            sessions = df["Session"].dropna().unique().tolist()
            f_sess = st.multiselect("Filter Session", sessions, default=sessions)
        with f3:
            outcomes = df["Outcome"].dropna().unique().tolist()
            f_out = st.multiselect("Filter Outcome", outcomes, default=outcomes)
            
        fdf = df[(df["Pair"].isin(f_pair)) & (df["Session"].isin(f_sess)) & (df["Outcome"].isin(f_out))]
        
        m1, m2, m3, m4, m5 = st.columns(5)
        exec_df = fdf[fdf["Outcome"].isin(["Win", "Partial Win", "Loss", "Breakeven"])]
        wins = len(fdf[fdf["Outcome"].isin(["Win", "Partial Win"])])
        wr = (wins / len(exec_df) * 100) if len(exec_df) > 0 else 0
        disc = (len(fdf[fdf["Rule_Followed"] == "Yes"]) / len(fdf) * 100) if len(fdf) > 0 else 0
        
        m1.metric("Executed Trades", len(exec_df))
        m2.metric("Win Rate", f"{wr:.1f}%")
        m3.metric("Net PnL ($)", f"{fdf['PnL'].sum():.2f}")
        m4.metric("Rule Discipline", f"{disc:.0f}%")
        m5.metric("Missed Setups", len(fdf[fdf["Outcome"] == "Missed Setup"]))
        
        st.divider()
        st.subheader("Trade History & Chart Previews")
        
        # Show latest trades first
        display_df = fdf.iloc[::-1] if USE_CLOUD else fdf
        for idx, row in display_df.iterrows():
            title = f"{row['Date']} | {row['Pair']} ({row['Direction']} - {row['Timeframe']}) | {row['Outcome']} | PnL: ${row['PnL']}"
            with st.expander(title):
                c1, c2, c3 = st.columns([1.2, 2, 2])
                with c1:
                    st.write(f"**Session / Order:** {row['Session']} ({row['Order_Type']})")
                    st.write(f"**Setup:** {row['Setup']}")
                    st.write(f"**Checklist:** {row['Checklist_Score']} | **Rule Followed:** {row['Rule_Followed']}")
                    st.write(f"**RR (Plan / Ach / Max):** {row['Planned_RR']}R / {row['Achieved_RR']}R / {row['Max_Potential_RR']}R")
                    st.write(f"**Partial:** {row['Partial_Booking']}")
                    st.write(f"**Mindset / Tag:** {row['Mindset']} | {row['Mistake_Tag']}")
                    st.write(f"**Notes:** {row['Notes']}")
                with c2:
                    st.caption("Entry Chart")
                    b_img = str(row["Before_Img"]).strip()
                    if b_img and (b_img.startswith("http") or os.path.exists(b_img)):
                        st.image(b_img, use_container_width=True)
                    else:
                        st.info("No Entry Image")
                with c3:
                    st.caption("Exit / Result Chart")
                    a_img = str(row["After_Img"]).strip()
                    if a_img and (a_img.startswith("http") or os.path.exists(a_img)):
                        st.image(a_img, use_container_width=True)
                    else:
                        st.info("No Exit Image")

with tab2:
    st.subheader("Performance & Edge Analytics")
    if df.empty:
        st.info("Log trades to see Session, Setup, and Equity Curve analytics.")
    else:
        exec_all = df[df["Outcome"].isin(["Win", "Partial Win", "Loss", "Breakeven"])].copy()
        if not exec_all.empty:
            if not USE_CLOUD:
                exec_all = exec_all.iloc[::-1]
            exec_all["Cumulative_PnL"] = exec_all["PnL"].cumsum()
            st.write("**Cumulative PnL Growth Curve ($)**")
            st.line_chart(exec_all.set_index("Date")["Cumulative_PnL"])
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("**PnL by Session ($)**")
                sess_pnl = exec_all.groupby("Session")["PnL"].sum()
                st.bar_chart(sess_pnl)
            with col_b:
                st.write("**Execution & Mistake Breakdown**")
                tag_counts = df["Mistake_Tag"].value_counts()
                st.bar_chart(tag_counts)
                
            st.write("**RR Efficiency (Average Planned vs Achieved vs Max Potential)**")
            rr_avg = pd.DataFrame({
                "Metric": ["Planned RR", "Achieved RR", "Max Potential RR"],
                "Average R": [
                    exec_all["Planned_RR"].mean(),
                    exec_all["Achieved_RR"].mean(),
                    exec_all["Max_Potential_RR"].mean()
                ]
            })
            st.bar_chart(rr_avg.set_index("Metric"))

with tab3:
    st.subheader("Funded Challenge Risk & Drawdown Monitor")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        acc_size = st.number_input("Account Size ($)", value=5000.0, step=1000.0)
    with fc2:
        profit_target_pct = st.number_input("Profit Target (%)", value=8.0, step=1.0)
    with fc3:
        max_dd_pct = st.number_input("Max Total Drawdown (%)", value=8.0, step=1.0)
    with fc4:
        daily_dd_pct = st.number_input("Max Daily Drawdown (%)", value=4.0, step=0.5)
        
    net_pnl = df["PnL"].sum() if not df.empty else 0.0
    current_bal = acc_size + net_pnl
    target_amt = acc_size * (profit_target_pct / 100.0)
    max_loss_amt = acc_size * (max_dd_pct / 100.0)
    
    today_str = str(datetime.today().date())
    today_pnl = df[df["Date"] == today_str]["PnL"].sum() if not df.empty else 0.0
    daily_loss_limit = acc_size * (daily_dd_pct / 100.0)
    
    st.divider()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Current Balance", f"${current_bal:,.2f}", f"${net_pnl:,.2f}")
    k2.metric("Profit Target Remaining", f"${max(0.0, target_amt - net_pnl):,.2f}", f"Target: ${target_amt:,.2f}")
    k3.metric("Total DD Buffer Left", f"${max_loss_amt + net_pnl:,.2f}", f"Max Loss: -${max_loss_amt:,.2f}")
    k4.metric("Today's Daily DD Buffer", f"${daily_loss_limit + today_pnl:,.2f}", f"Today PnL: ${today_pnl:,.2f}")
    
    if target_amt > 0:
        prog = min(1.0, max(0.0, net_pnl / target_amt))
        st.write(f"**Challenge Target Progress: {prog*100:.1f}%**")
        st.progress(prog)
