import streamlit as st
import pandas as pd
import os
import requests
import base64
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Institutional Multi-Account Trading Journal", layout="wide")

# --- CUSTOM CSS FOR COLOURFUL BADGES & CARDS ---
st.markdown("""
<style>
.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}
.badge {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    display: inline-block;
}
.b-blue { background-color: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; }
.b-purple { background-color: #f3e8ff; color: #6b21a8; border: 1px solid #d8b4fe; }
.b-green { background-color: #dcfce7; color: #166534; border: 1px solid #86efac; }
.b-red { background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
.b-amber { background-color: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.b-teal { background-color: #ccfbf1; color: #115e59; border: 1px solid #5eead4; }
.b-gray { background-color: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }

.info-box {
    background-color: #f8fafc;
    border-left: 4px solid #3b82f6;
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #1e293b;
}
.psych-box {
    background-color: #f5f3ff;
    border-left: 4px solid #8b5cf6;
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #3b0764;
}
.learning-box {
    background-color: #fffbeb;
    border-left: 4px solid #f59e0b;
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 8px;
    font-size: 13px;
    color: #78350f;
}
.notes-box {
    background-color: #f1f5f9;
    border: 1px solid #e2e8f0;
    padding: 10px 12px;
    border-radius: 6px;
    font-size: 13px;
    color: #334155;
}
</style>
""", unsafe_allow_html=True)

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
            st.error("Incorrect PIN.")
    st.stop()

# --- 2. COLUMNS & GOOGLE SHEETS SETUP ---
ALL_COLUMNS = [
    "Account_Name", "Trade_No", "Date", "Entry_Time", "Pair", "Session",
    "Timeframe", "Order_Type", "Setup", "Direction", "Lot_Size", "Entry_Price",
    "SL_Price", "TP_Price", "Trailing_SL", "Exit_Price", "MAE", "MFE",
    "Risk_Pct", "Planned_RR", "Achieved_RR", "Partial_Booking", "Outcome",
    "Commission", "PnL", "Checklist_Score", "Rule_Followed", "Mistake_Tag",
    "Mindset", "In_Trade_Psychology", "Key_Learning", "Notes", "Before_Img", "After_Img"
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
    return client.open_by_url(st.secrets["sheet_url"]).sheet1

def load_data():
    if USE_CLOUD:
        try:
            sheet = get_gsheet()
            all_vals = sheet.get_all_values()
            if not all_vals:
                sheet.append_row(ALL_COLUMNS)
                return pd.DataFrame(columns=ALL_COLUMNS)
            headers = all_vals[0]
            if headers != ALL_COLUMNS:
                sheet.update("A1", [ALL_COLUMNS])
            rows = all_vals[1:]
            if not rows:
                return pd.DataFrame(columns=ALL_COLUMNS)
            padded_rows = [r + [""] * (len(ALL_COLUMNS) - len(r)) for r in rows]
            df = pd.DataFrame(padded_rows, columns=ALL_COLUMNS)
            df["_sheet_row"] = range(2, len(df) + 2)
            return df
        except Exception as e:
            st.error(f"Google Sheets Error: {e}")
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
        df["_sheet_row"] = range(len(df))
        return df

def save_or_update_trade(row_dict, sheet_row=None):
    row_values = [str(row_dict.get(col, "")) for col in ALL_COLUMNS]
    if USE_CLOUD:
        sheet = get_gsheet()
        if sheet_row:
            sheet.update(f"A{sheet_row}", [row_values])
        else:
            sheet.append_row(row_values)
    else:
        df = load_data()
        if "_sheet_row" in df.columns:
            df = df.drop(columns=["_sheet_row"])
        if sheet_row is not None and sheet_row < len(df):
            for col in ALL_COLUMNS:
                df.loc[sheet_row, col] = row_dict.get(col, "")
        else:
            df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
        df.to_csv(LOCAL_CSV, index=False)

def upload_image(uploaded_file, prefix, existing_url=""):
    if uploaded_file is None:
        return existing_url
    if "imgbb_api_key" in st.secrets:
        try:
            b64_img = base64.b64encode(uploaded_file.getvalue()).decode("utf-8")
            res = requests.post(
                "https://api.imgbb.com/1/upload",
                data={"key": st.secrets["imgbb_api_key"], "image": b64_img},
                timeout=15
            )
            data = res.json()
            if data.get("success"):
                return data["data"]["url"]
        except Exception as e:
            st.warning(f"Cloud upload failed, saved locally: {e}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_path = os.path.join(IMG_DIR, f"{timestamp}_{prefix}_{uploaded_file.name}")
    with open(local_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return local_path

df = load_data()
if not df.empty:
    num_cols = ["Lot_Size", "Entry_Price", "SL_Price", "TP_Price", "Trailing_SL", "Exit_Price", "MAE", "MFE", "Risk_Pct", "Planned_RR", "Achieved_RR", "Commission", "PnL"]
    for num_col in num_cols:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0.0)
    df["Account_Name"] = df["Account_Name"].replace("", "Default Account")

# --- 3. TOP ACCOUNT SELECTOR & CREATE NEW JOURNAL ---
st.title("Multi-Account Trading Journal & Edge System")

existing_accounts = df["Account_Name"].dropna().unique().tolist() if not df.empty else []
default_accounts = ["Maven 5K - Phase 1", "Maven 5K - Phase 2", "Personal Capital"]
all_account_options = list(dict.fromkeys(existing_accounts + default_accounts))

top_c1, top_c2, top_c3 = st.columns([2, 2, 1.5])
with top_c1:
    selected_account = st.selectbox("Select Active Journal / Account", ["ALL ACCOUNTS"] + all_account_options)
with top_c2:
    custom_new_acc = st.text_input("Or Type New Custom Journal Name (e.g., Funded 10K P1)", "")
with top_c3:
    st.write("")
    st.write("")
    if USE_CLOUD:
        st.success("Cloud Sync: LIVE")
    else:
        st.warning("Local Mode")

active_acc_for_entry = custom_new_acc.strip() if custom_new_acc.strip() else (
    selected_account if selected_account != "ALL ACCOUNTS" else all_account_options[0]
)

if not df.empty and active_acc_for_entry in df["Account_Name"].values:
    acc_trades = df[df["Account_Name"] == active_acc_for_entry]
    next_trade_no = len(acc_trades) + 1
else:
    next_trade_no = 1

# --- 4. SIDEBAR: LOG NEW OR EDIT EXISTING TRADE ---
with st.sidebar:
    mode = st.radio("Action Mode", ["Log New Trade", "Edit / Update Existing Trade (Re-entry)"], horizontal=True)
    
    edit_row_data = {}
    target_sheet_row = None
    
    if mode == "Edit / Update Existing Trade (Re-entry)":
        if df.empty:
            st.warning("No trades available to edit.")
        else:
            df["label"] = df["Account_Name"] + " | #" + df["Trade_No"].astype(str) + " | " + df["Pair"] + " (" + df["Date"] + ")"
            selected_label = st.selectbox("Select Trade to Update / Re-enter", df["label"].tolist()[::-1])
            edit_row_data = df[df["label"] == selected_label].iloc[0].to_dict()
            target_sheet_row = int(edit_row_data["_sheet_row"])
            st.info(f"Editing Trade #{edit_row_data['Trade_No']} in {edit_row_data['Account_Name']}")

    st.markdown("---")
    acc_display = edit_row_data.get("Account_Name", active_acc_for_entry)
    t_no_display = edit_row_data.get("Trade_No", next_trade_no)
    st.subheader(f"Account: {acc_display} | Trade #{t_no_display}")

    c1, c2 = st.columns(2)
    with c1:
        try:
            default_date = datetime.strptime(str(edit_row_data["Date"]), "%Y-%m-%d").date() if edit_row_data.get("Date") else datetime.today()
        except Exception:
            default_date = datetime.today()
        date = st.date_input("Date", default_date)
        pair_opts = ["XAUUSD", "XAGUSD (Silver)", "USOIL (Crude)", "EURUSD", "GBPUSD", "BTCUSD", "INDIAN EQUITY"]
        curr_pair = edit_row_data.get("Pair", "XAUUSD")
        if curr_pair not in pair_opts:
            pair_opts.insert(0, curr_pair)
        pair = st.selectbox("Pair / Instrument", pair_opts, index=pair_opts.index(curr_pair))
        
        tf_opts = ["M1", "M3", "M5", "M15", "H1", "H4", "D1"]
        curr_tf = edit_row_data.get("Timeframe", "M5")
        timeframe = st.selectbox("Entry TF", tf_opts, index=tf_opts.index(curr_tf) if curr_tf in tf_opts else 2)
        
    with c2:
        entry_time = st.text_input("Entry Time (IST/Session)", value=str(edit_row_data.get("Entry_Time", datetime.now().strftime("%H:%M"))))
        sess_opts = ["London", "New York", "Tokyo", "Mumbai"]
        curr_sess = edit_row_data.get("Session", "London")
        session = st.selectbox("Session", sess_opts, index=sess_opts.index(curr_sess) if curr_sess in sess_opts else 0)
        
        dir_opts = ["Long", "Short"]
        curr_dir = edit_row_data.get("Direction", "Long")
        direction = st.radio("Direction", dir_opts, index=dir_opts.index(curr_dir) if curr_dir in dir_opts else 0, horizontal=True)

    ord_opts = ["Limit Order", "Market Execution", "Re-Entry / Scale-In", "Stop Order"]
    curr_ord = edit_row_data.get("Order_Type", "Limit Order")
    order_type = st.selectbox("Order Type", ord_opts, index=ord_opts.index(curr_ord) if curr_ord in ord_opts else 0)
    
    # Expanded Multi-line Setup & Confluence Box
    setup = st.text_area(
        "Setup & Confluence (HTF Bias, Liquidity Sweep, OB/FVG, VSA, Hora/Timing)",
        value=str(edit_row_data.get("Setup", "")),
        height=100
    )

    st.markdown("---")
    st.subheader("Lot Size, Exact Prices, MAE & MFE")
    l1, l2 = st.columns(2)
    with l1:
        lot_size = st.number_input("Lot Size", value=float(edit_row_data.get("Lot_Size", 0.01)), step=0.01, format="%.2f")
    with l2:
        risk_pct = st.number_input("Risk (%)", value=float(edit_row_data.get("Risk_Pct", 1.0)), step=0.25)

    p1, p2 = st.columns(2)
    with p1:
        entry_price = st.number_input("Entry / Avg Price", value=float(edit_row_data.get("Entry_Price", 0.0)), format="%.4f")
        tp_price = st.number_input("Take Profit (TP)", value=float(edit_row_data.get("TP_Price", 0.0)), format="%.4f")
        exit_price = st.number_input("Actual Exit Price", value=float(edit_row_data.get("Exit_Price", 0.0)), format="%.4f")
        mae_val = st.number_input("MAE (Max Adverse Pips/$)", value=float(edit_row_data.get("MAE", 0.0)), step=1.0)
    with p2:
        sl_price = st.number_input("Stop Loss (SL)", value=float(edit_row_data.get("SL_Price", 0.0)), format="%.4f")
        trailing_sl = st.number_input("Trailing SL Price", value=float(edit_row_data.get("Trailing_SL", 0.0)), format="%.4f")
        commission = st.number_input("Commission / Swap ($)", value=float(edit_row_data.get("Commission", 0.0)), step=0.5)
        mfe_val = st.number_input("MFE (Max Favorable Pips/$)", value=float(edit_row_data.get("MFE", 0.0)), step=1.0)

    # Live Estimated PnL Preview
    if entry_price > 0 and exit_price > 0 and lot_size > 0:
        diff = (exit_price - entry_price) if direction == "Long" else (entry_price - exit_price)
        mult = 100.0 if "XAU" in pair else (5000.0 if "XAG" in pair else (1000.0 if "OIL" in pair else 100000.0))
        est_gross = diff * lot_size * mult
        st.caption(f"Live Price Move: {diff:+.4f} | Est. Gross PnL (Standard Contract): ${est_gross:+.2f}")

    r1, r2 = st.columns(2)
    with r1:
        planned_rr = st.number_input("Planned RR", value=float(edit_row_data.get("Planned_RR", 3.0)), step=0.5)
    with r2:
        achieved_rr = st.number_input("Achieved RR", value=float(edit_row_data.get("Achieved_RR", 0.0)), step=0.5)

    pb_opts = [
        "No Partial (Full TP / SL)", "50% at 1:2, Rest BE",
        "50% at 1:2, Rest Full TP", "Trailing SL Hit",
        "Re-Entry Added (Avg Updated)", "Custom Partial (See Notes)"
    ]
    curr_pb = edit_row_data.get("Partial_Booking", pb_opts[0])
    partial_booking = st.selectbox("Trade Management / Partial", pb_opts, index=pb_opts.index(curr_pb) if curr_pb in pb_opts else 0)

    o1, o2 = st.columns(2)
    with o1:
        out_opts = ["Running / Open", "Win", "Partial Win", "Trailing SL Win", "Loss", "Breakeven", "Missed Setup"]
        curr_out = edit_row_data.get("Outcome", "Running / Open")
        outcome = st.selectbox("Outcome", out_opts, index=out_opts.index(curr_out) if curr_out in out_opts else 0)
    with o2:
        pnl = st.number_input("Final Net PnL ($)", value=float(edit_row_data.get("PnL", 0.0)), step=10.0)

    st.markdown("---")
    st.subheader("Checklist, Psychology & Learning")
    chk1 = st.checkbox("HTF Bias & Structure Clear?", value=True)
    chk2 = st.checkbox("Liquidity Swept Before Entry?", value=True)
    chk3 = st.checkbox("Valid POI / Limit Order?", value=True)
    chk4 = st.checkbox("Within Session Risk Limit?", value=True)
    checklist_score = f"{sum([chk1, chk2, chk3, chk4])}/4"

    rule_followed = st.checkbox("Followed All Rules Strictly?", value=(edit_row_data.get("Rule_Followed", "Yes") == "Yes"))
    tag_opts = ["None (Clean Execution)", "Missed by Few Pips", "Trailing SL Hit Early", "Exited Too Early", "Moved SL", "FOMO / Overtraded"]
    curr_tag = edit_row_data.get("Mistake_Tag", tag_opts[0])
    mistake_tag = st.selectbox("Execution Tag", tag_opts, index=tag_opts.index(curr_tag) if curr_tag in tag_opts else 0)

    mind_opts = ["Calm & Focused", "Hesitant / Fearful", "FOMO / Rushed", "Overconfident"]
    curr_mind = edit_row_data.get("Mindset", mind_opts[0])
    mindset = st.selectbox("Pre-Trade Mindset", mind_opts, index=mind_opts.index(curr_mind) if curr_mind in mind_opts else 0)

    in_trade_psych = st.text_area(
        "IN-TRADE PSYCHOLOGY (Trade Ke Dauran Kya Feel Hua - Fear, Patience, Urge to Close Early?)",
        value=str(edit_row_data.get("In_Trade_Psychology", "")),
        height=100
    )
    key_learning = st.text_area(
        "KEY LEARNING FROM THIS TRADE (Mandatory Takeaway)",
        value=str(edit_row_data.get("Key_Learning", "")),
        height=80
    )
    notes = st.text_area(
        "Execution & Re-entry Technical Notes",
        value=str(edit_row_data.get("Notes", "")),
        height=80
    )

    before_img = st.file_uploader("Upload Entry Chart", type=["png", "jpg", "jpeg"])
    after_img = st.file_uploader("Upload Exit / Result Chart", type=["png", "jpg", "jpeg"])

    btn_label = "Update Existing Trade" if mode == "Edit / Update Existing Trade (Re-entry)" else "Save New Trade"
    if st.button(btn_label, use_container_width=True):
        with st.spinner("Syncing to Cloud Vault..."):
            b_url = upload_image(before_img, "before", str(edit_row_data.get("Before_Img", "")))
            a_url = upload_image(after_img, "after", str(edit_row_data.get("After_Img", "")))
            row_data = {
                "Account_Name": acc_display, "Trade_No": t_no_display, "Date": str(date),
                "Entry_Time": entry_time, "Pair": pair, "Session": session,
                "Timeframe": timeframe, "Order_Type": order_type, "Setup": setup,
                "Direction": direction, "Lot_Size": lot_size, "Entry_Price": entry_price,
                "SL_Price": sl_price, "TP_Price": tp_price, "Trailing_SL": trailing_sl,
                "Exit_Price": exit_price, "MAE": mae_val, "MFE": mfe_val,
                "Risk_Pct": risk_pct, "Planned_RR": planned_rr, "Achieved_RR": achieved_rr,
                "Partial_Booking": partial_booking, "Outcome": outcome,
                "Commission": commission, "PnL": pnl,
                "Checklist_Score": checklist_score, "Rule_Followed": "Yes" if rule_followed else "No",
                "Mistake_Tag": mistake_tag, "Mindset": mindset,
                "In_Trade_Psychology": in_trade_psych, "Key_Learning": key_learning,
                "Notes": notes, "Before_Img": b_url, "After_Img": a_url
            }
            save_or_update_trade(row_data, target_sheet_row)
            st.success("Trade Synced & Live Dashboard Updated!")
            st.rerun()

# --- 5. FILTER DATA BY ACTIVE ACCOUNT ---
if selected_account == "ALL ACCOUNTS" or df.empty:
    acc_df = df.copy()
else:
    acc_df = df[df["Account_Name"] == selected_account].copy()

# --- 6. MULTI-ASSET TABS ON SAME PAGE ---
asset_tabs = st.tabs([
    "All Instruments", "XAUUSD (Gold)", "XAGUSD (Silver)",
    "USOIL (Crude)", "Key Learnings Vault", "Analytics, Position Calc & Funded Tracker"
])

def get_outcome_badge_class(outcome_str):
    if outcome_str in ["Win", "Partial Win", "Trailing SL Win"]:
        return "b-green"
    elif outcome_str == "Loss":
        return "b-red"
    elif outcome_str == "Missed Setup":
        return "b-amber"
    return "b-gray"

def render_trade_list(sub_df, section_key):
    if sub_df.empty:
        st.info("No trades logged in this category yet.")
        return

    exec_df = sub_df[sub_df["Outcome"].isin(["Win", "Partial Win", "Trailing SL Win", "Loss", "Breakeven"])]
    wins = len(sub_df[sub_df["Outcome"].isin(["Win", "Partial Win", "Trailing SL Win"])])
    wr = (wins / len(exec_df) * 100) if len(exec_df) > 0 else 0
    total_lots = exec_df["Lot_Size"].sum() if len(exec_df) > 0 else 0
    avg_mfe = exec_df["MFE"].mean() if len(exec_df) > 0 else 0

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Executed Trades", len(exec_df))
    m2.metric("Win Rate", f"{wr:.1f}%")
    m3.metric("Net PnL ($)", f"{sub_df['PnL'].sum():.2f}")
    m4.metric("Total Lots Traded", f"{total_lots:.2f}")
    m5.metric("Avg MFE", f"{avg_mfe:.1f}")
    m6.metric("Missed Setups", len(sub_df[sub_df["Outcome"] == "Missed Setup"]))

    st.divider()
    display_df = sub_df.iloc[::-1]
    for idx, row in display_df.iterrows():
        header = (
            f"[{row['Account_Name']} | #{row['Trade_No']}] {row['Date']} ({row['Entry_Time']}) | "
            f"{row['Pair']} {row['Direction']} ({row['Lot_Size']} Lots) | {row['Outcome']} | PnL: ${row['PnL']}"
        )
        with st.expander(header):
            c1, c2, c3 = st.columns([1.4, 2, 2])
            with c1:
                dir_cls = "b-green" if row["Direction"] == "Long" else "b-red"
                out_cls = get_outcome_badge_class(str(row["Outcome"]))
                rule_cls = "b-green" if row["Rule_Followed"] == "Yes" else "b-red"
                
                badges_html = f"""
                <div class="badge-row">
                    <span class="badge b-blue">{row['Session']} Session</span>
                    <span class="badge b-purple">{row['Order_Type']}</span>
                    <span class="badge b-teal">{row['Timeframe']} | {row['Lot_Size']} Lots</span>
                    <span class="badge {dir_cls}">{row['Direction']}</span>
                    <span class="badge {out_cls}">{row['Outcome']}</span>
                    <span class="badge {rule_cls}">Rules: {row['Rule_Followed']} ({row['Checklist_Score']})</span>
                    <span class="badge b-amber">{row['Mindset']}</span>
                    <span class="badge b-gray">{row['Partial_Booking']}</span>
                </div>
                """
                st.markdown(badges_html, unsafe_allow_html=True)

                prices_html = f"""
                <div class="info-box">
                    <b>Setup & Confluence:</b> {row['Setup']}<br><br>
                    <b>Entry:</b> {row['Entry_Price']} &nbsp;|&nbsp; <b>Exit:</b> {row['Exit_Price']} &nbsp;|&nbsp; <b>Comm:</b> ${row['Commission']}<br>
                    <b>SL:</b> {row['SL_Price']} &nbsp;|&nbsp; <b>TP:</b> {row['TP_Price']} &nbsp;|&nbsp; <b>Trail SL:</b> {row['Trailing_SL']}<br>
                    <b>MAE:</b> {row['MAE']} &nbsp;|&nbsp; <b>MFE:</b> {row['MFE']} &nbsp;|&nbsp; <b>RR:</b> {row['Planned_RR']}R &rarr; {row['Achieved_RR']}R<br>
                    <b>Tag:</b> {row['Mistake_Tag']}
                </div>
                """
                st.markdown(prices_html, unsafe_allow_html=True)

                if str(row["In_Trade_Psychology"]).strip():
                    st.markdown(f'<div class="psych-box"><b>In-Trade Psychology:</b> {row["In_Trade_Psychology"]}</div>', unsafe_allow_html=True)

                if str(row["Key_Learning"]).strip():
                    st.markdown(f'<div class="learning-box"><b>Key Learning:</b> {row["Key_Learning"]}</div>', unsafe_allow_html=True)

                if str(row["Notes"]).strip():
                    st.markdown(f'<div class="notes-box"><b>Technical Notes:</b> {row["Notes"]}</div>', unsafe_allow_html=True)

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

with asset_tabs[0]:
    render_trade_list(acc_df, "all")

with asset_tabs[1]:
    render_trade_list(acc_df[acc_df["Pair"].str.contains("XAUUSD", case=False, na=False)] if not acc_df.empty else acc_df, "gold")

with asset_tabs[2]:
    render_trade_list(acc_df[acc_df["Pair"].str.contains("XAGUSD|Silver", case=False, na=False)] if not acc_df.empty else acc_df, "silver")

with asset_tabs[3]:
    render_trade_list(acc_df[acc_df["Pair"].str.contains("USOIL|Crude", case=False, na=False)] if not acc_df.empty else acc_df, "crude")

with asset_tabs[4]:
    st.subheader("Master Key Learnings & Psychology Revision Vault")
    if acc_df.empty:
        st.info("No learnings recorded yet.")
    else:
        learnings_df = acc_df[acc_df["Key_Learning"].astype(str).str.strip() != ""].iloc[::-1]
        if learnings_df.empty:
            st.info("Add 'Key Learning' while logging trades to build your revision list.")
        else:
            for _, r in learnings_df.iterrows():
                st.markdown(f"- **[{r['Account_Name']} #{r['Trade_No']} | {r['Pair']} | {r['Outcome']}]:** {r['Key_Learning']}")

with asset_tabs[5]:
    st.subheader("Built-In Position Size (Lot) Calculator")
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        calc_bal = st.number_input("Balance ($)", value=5000.0, step=500.0)
    with pc2:
        calc_risk = st.number_input("Risk per Trade (%)", value=1.0, step=0.25)
    with pc3:
        calc_sl_pips = st.number_input("Stop Loss (Pips)", value=30.0, step=5.0)
    with pc4:
        calc_pip_val = st.number_input("Pip Value per 1.0 Lot ($)", value=10.0, step=1.0)
        
    risk_dollars = calc_bal * (calc_risk / 100.0)
    rec_lots = risk_dollars / (calc_sl_pips * calc_pip_val) if (calc_sl_pips * calc_pip_val) > 0 else 0.0
    st.success(f"Max Risk Amount: **${risk_dollars:.2f}** | Recommended Lot Size: **{rec_lots:.2f} Lots**")

    st.divider()
    st.subheader(f"Funded Account Risk & Drawdown Monitor ({selected_account})")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        acc_size = st.number_input("Challenge Account Size ($)", value=5000.0, step=1000.0)
    with fc2:
        target_pct = st.number_input("Profit Target (%)", value=8.0, step=1.0)
    with fc3:
        max_dd_pct = st.number_input("Max Drawdown (%)", value=8.0, step=1.0)
    with fc4:
        daily_dd_pct = st.number_input("Daily Drawdown (%)", value=4.0, step=0.5)

    net_pnl = acc_df["PnL"].sum() if not acc_df.empty else 0.0
    target_amt = acc_size * (target_pct / 100.0)
    max_loss_amt = acc_size * (max_dd_pct / 100.0)
    today_str = str(datetime.today().date())
    today_pnl = acc_df[acc_df["Date"] == today_str]["PnL"].sum() if not acc_df.empty else 0.0
    daily_limit = acc_size * (daily_dd_pct / 100.0)

    if today_pnl <= -(daily_limit * 0.8) and daily_limit > 0:
        st.error(f"WARNING: Today's Loss (${today_pnl:.2f}) has reached 80%+ of your Daily Drawdown Limit (${daily_limit:.2f}). Stop trading for today!")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Account Balance", f"${acc_size + net_pnl:,.2f}", f"${net_pnl:,.2f}")
    k2.metric("Target Remaining", f"${max(0.0, target_amt - net_pnl):,.2f}")
    k3.metric("Total DD Left", f"${max_loss_amt + net_pnl:,.2f}")
    k4.metric("Daily DD Left", f"${daily_limit + today_pnl:,.2f}")

    if not acc_df.empty:
        exec_chart = acc_df[acc_df["Outcome"].isin(["Win", "Partial Win", "Trailing SL Win", "Loss", "Breakeven"])].copy()
        if not exec_chart.empty:
            exec_chart["Cumulative_PnL"] = exec_chart["PnL"].cumsum()
            st.line_chart(exec_chart.set_index("Trade_No")["Cumulative_PnL"])
            
            csv_export = acc_df.drop(columns=["_sheet_row"], errors="ignore").to_csv(index=False).encode("utf-8")
            st.download_button("Download Account Journal (CSV Backup)", csv_export, f"{selected_account}_journal.csv", "text/csv")
