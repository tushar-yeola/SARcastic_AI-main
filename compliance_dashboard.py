import streamlit as st
import pandas as pd
import altair as alt
import datetime
import json
import time
import os

# --- Backend Integrations ---
import requests

# Connection Config
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# Wrapper Functions to Bridge Frontend -> Backend API
def get_token():
    return st.session_state.get("token")

def get_headers():
    token = get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}

def login_user(username, password):
    try:
        resp = requests.post(f"{API_URL}/auth/login", data={"username": username, "password": password})
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

def get_all_cases(limit=100):
    try:
        resp = requests.get(f"{API_URL}/cases/", params={"limit": limit}, headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"API Error: {e}")
    return []

def get_case_by_id(sar_id):
    try:
        resp = requests.get(f"{API_URL}/cases/{sar_id}", headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Case fetch error: {e}")
    except Exception as e:
        print(f"Case fetch error: {e}")
    return None

def get_sar_details(case_id):
    try:
        resp = requests.get(f"{API_URL}/cases/{case_id}/details", headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Details Error: {e}")
    return {}

def update_sar_section(case_id, section, data):
    try:
        resp = requests.put(
            f"{API_URL}/cases/{case_id}/details", 
            json={"section": section, "data": data},
            headers=get_headers()
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"Update Error: {e}")
        return False

def create_sar_case(analyst_id, data, generated_narrative):
    kyc = data.get("kyc", {})
    payload = {
        "customer_name": kyc.get("full_name", "Unknown"),
        "kyc_data": kyc,
        "transaction_data": [{"raw": data.get("transactions", "")}]
    }
    try:
        resp = requests.post(f"{API_URL}/cases/", json=payload, headers=get_headers())
        if resp.status_code == 200:
            return resp.json()['id']
    except Exception as e:
        print(f"Create Error: {e}")
    return None

def generate_sar_for_case(case_id):
    """
    Calls the backend to generate a detailed SAR narrative for the given case.
    The backend invokes the LLM with RAG context and returns the full SAR.
    """
    try:
        resp = requests.post(
            f"{API_URL}/cases/{case_id}/generate_narrative",
            headers=get_headers(),
            timeout=120  # LLM generation can take time
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            error_detail = resp.json().get("detail", "Unknown error")
            return {"error": error_detail}
    except requests.exceptions.Timeout:
        return {"error": "SAR generation timed out. The LLM may need more time."}
    except Exception as e:
        return {"error": str(e)}

def get_dashboard_metrics():
    try:
        resp = requests.get(f"{API_URL}/dashboard/metrics", headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Metrics Error: {e}")
    return {
        "sar_filed_month": 0,
        "avg_time_to_file": 0,
        "sla_breach_pct": 0.0,
        "backlog_30_days": 0,
        "continuing_sar": 0
    }

def generate_regulatory_report():
    try:
        resp = requests.get(f"{API_URL}/dashboard/report", headers=get_headers())
        if resp.status_code == 200:
            return resp.json().get('report', "")
    except Exception as e:
        print(f"Report Error: {e}")
    return "Report generation failed — backend unreachable."

def retrieve_relevant_docs(query):
    try:
        resp = requests.post(f"{API_URL}/dashboard/explain", json={"query": query}, headers=get_headers())
        if resp.status_code == 200:
            return resp.json().get('docs', [])
    except Exception as e:
        print(f"RAG Error: {e}")
    return []

def save_audit_log(sar_id, rules, prompt, response):
    # Audit logging is handled automatically by the backend on write operations.
    pass

def get_audit_logs(limit=50):
    try:
        resp = requests.get(f"{API_URL}/dashboard/audit-logs", params={"limit": limit}, headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Audit Logs Error: {e}")
    return []

def get_case_audit_history(sar_id):
    try:
        resp = requests.get(f"{API_URL}/cases/{sar_id}/audit", headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Case Audit Error: {e}")
    return []

def upload_csv_case(file):
    try:
        files = {"file": (file.name, file, "text/csv")}
        resp = requests.post(f"{API_URL}/cases/import-csv", headers=get_headers(), files=files)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            try:
                detail = resp.json().get('detail')
            except:
                detail = resp.text
            return {"error": f"Validation Error: {detail}"}
        else:
            return {"error": f"Upload failed: {resp.status_code} {resp.text}"}
    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

def seed_regulatory_knowledge_base():
    pass  # Backend handles this on startup


# -----------------------------------------------------------------------------
# Page Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SARcastic AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

# Initialize Knowledge Base
if "kb_seeded" not in st.session_state:
    try:
        seed_regulatory_knowledge_base()
        st.session_state.kb_seeded = True
    except Exception as e:
        print(f"Vector Store Error: {e}")

# -----------------------------------------------------------------------------
# Authentication Logic
# -----------------------------------------------------------------------------
def verify_password(email, password):
    data = login_user(email, password)
    if data:
        st.session_state.token = data["access_token"]
        return {"role": data.get("role", "Analyst")}
    return None

# -----------------------------------------------------------------------------
# Views
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Login View
# -----------------------------------------------------------------------------
def render_login():
    st.markdown("""
    <style>
        .login-container { max-width: 400px; margin: 100px auto; padding: 32px; background-color: #102A43; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 1px solid #2A3F55; }
        .login-header { text-align: center; margin-bottom: 24px; }
        .login-title { font-size: 1.8rem; font-weight: 700; color: #FFFFFF; font-family: 'Inter', sans-serif; }
        .login-sub { color: #B0B8C1; font-size: 0.9rem; margin-top: 5px; font-family: 'Inter', sans-serif; }
        .stButton > button { width: 100%; background-color: #C9A227; color: #0B1F3A; border-radius: 6px; padding: 8px 0; font-weight: 600; }
        .stButton > button:hover { background-color: #E3B42A; color: #000000; }
        div[data-testid="column"]:nth-of-type(2) { display: flex; flex-direction: column; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        st.markdown('<div class="login-header"><div class="login-title">SARcastic AI</div><div class="login-sub">Secure Professional Access</div></div>', unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("Email Address", placeholder="name@company.com")
            password = st.text_input("Password", type="password", placeholder="••••••••")
            if st.form_submit_button("Sign In"):
                with st.spinner("Authenticating..."):
                    time.sleep(0.8)
                user_info = verify_password(email, password)
                if user_info:
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.session_state.user_role = user_info["role"]
                    st.success(f"Login successful. Welcome {user_info['role']}")
                    st.rerun()
                else:
                    st.error("Invalid email or password")
        st.markdown('<div style="text-align: center; margin-top: 20px; font-size: 0.8rem; color: #999;">Forgot password? Contact IT Support.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Design System
# -----------------------------------------------------------------------------
def load_design_system():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root { --primary-gold: #C9A227; --bg-color: #0B1F3A; --card-bg: #102A43; --text-primary: #FFFFFF; --text-secondary: #B0B8C1; --border-color: #2A3F55; --success: #0D9488; --danger: #B91C1C; --warning: #D97706; }
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text-primary); background-color: var(--bg-color); }
        section[data-testid="stSidebar"] { background-color: #0E243D; border-right: 1px solid var(--border-color); }
        .kpi-card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 6px; padding: 19px; box-shadow: 0 1px 3px rgba(0,0,0,0.3); display: flex; flex-direction: column; height: 100%; }
        .kpi-title { font-size: 0.85rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; margin-bottom: 6px; }
        .kpi-value { font-size: 1.8rem; font-weight: 700; color: var(--primary-gold); margin-bottom: 3px; }
        .content-card { background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 6px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.3); margin-bottom: 16px; }
        .card-header { font-size: 1.1rem; font-weight: 600; color: var(--primary-gold); margin-bottom: 12px; border-bottom: 1px solid var(--border-color); padding-bottom: 8px; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; display: inline-block; }
        .badge-high { background-color: rgba(185, 28, 28, 0.2); color: #B91C1C; border: 1px solid #B91C1C; }
        .badge-medium { background-color: rgba(217, 119, 6, 0.2); color: #D97706; border: 1px solid #D97706; }
        .badge-low { background-color: rgba(13, 148, 136, 0.2); color: #0D9488; border: 1px solid #0D9488; }
        .badge-closed { background-color: #2A3F55; color: #B0B8C1; }
        .badge-open { background-color: rgba(201, 162, 39, 0.2); color: #C9A227; }
        .stButton button { background-color: var(--primary-gold); color: #0B1F3A; border: none; border-radius: 6px; font-weight: 600; }
        .stButton button:hover { background-color: #E3B42A; color: #000000; }
        #MainMenu, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Components
# -----------------------------------------------------------------------------
def kpi_card(title, value, trend=None, trend_direction="up"):
    trend_html = ""
    if trend:
        color = "var(--success)" if trend_direction == "good" else ("var(--danger)" if trend_direction == "bad" else "var(--text-secondary)")
        arrow = "↑" if trend_direction == "bad" else "↓"
        if trend_direction == "good": arrow="↑" if "+" in trend else "↓"
        trend_html = f'<span style="color: {color}; font-size: 0.8rem; font-weight: 500;">{arrow} {trend} vs last month</span>'
    st.markdown(f'<div class="kpi-card"><div class="kpi-title">{title}</div><div class="kpi-value">{value}</div>{trend_html}</div>', unsafe_allow_html=True)

def risk_chart(data=None):
    if data is None or data.empty:
        st.info("No risk data available.")
        return

    base = alt.Chart(data).encode(
        theta=alt.Theta("Cases", stack=True),
        radius=alt.Radius("Cases", scale=alt.Scale(type="sqrt", zero=True, rangeMin=20)),
        color=alt.Color("Risk Level", scale=alt.Scale(
            domain=['Low Risk', 'Medium Risk', 'High Risk', 'Critical'],
            range=['#0D9488', '#D97706', '#B91C1C', '#8B0000']
        )),
        tooltip=["Risk Level", "Cases"]
    )
    pie = base.mark_arc(outerRadius=100, innerRadius=60)
    text = base.mark_text(radius=120).encode(text="Cases", color=alt.value("#FFFFFF"))
    st.altair_chart((pie + text).properties(height=250), use_container_width=True)

def case_aging_heatmap(cases_data=None):
    if not cases_data:
        st.info("No case data for aging heatmap.")
        return

    now = datetime.datetime.now()
    processed_rows = []

    for case in cases_data:
        created_at = case.get('created_at')
        risk = case.get('risk_level', 'Medium')

        if created_at:
            if isinstance(created_at, str):
                try:
                    c_date = datetime.datetime.fromisoformat(created_at)
                except:
                    try:
                        c_date = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S.%f")
                    except:
                        try:
                            c_date = datetime.datetime.strptime(created_at, "%Y-%m-%d")
                        except:
                            continue
            else:
                c_date = created_at

            days_old = (now - c_date).days

            bucket = "60+ Days"
            if days_old <= 7: bucket = "0-7 Days"
            elif days_old <= 15: bucket = "8-15 Days"
            elif days_old <= 30: bucket = "16-30 Days"
            elif days_old <= 60: bucket = "31-60 Days"

            processed_rows.append({"Risk": risk, "Bucket": bucket})

    if not processed_rows:
        st.info("No aging data to display.")
        return

    df = pd.DataFrame(processed_rows)
    data = df.groupby(['Risk', 'Bucket']).size().reset_index(name='Count')

    bucket_order = ["0-7 Days", "8-15 Days", "16-30 Days", "31-60 Days", "60+ Days"]
    risk_order = ["Low", "Medium", "High", "Critical"]

    base = alt.Chart(data).encode(
        x=alt.X('Bucket', sort=bucket_order, title="Aging Bucket", axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Risk', sort=risk_order, title="Risk Level"),
    )

    heatmap = base.mark_rect().encode(
        color=alt.Color('Count', scale=alt.Scale(range=['#1E3A5F', '#C9A227']), title="Case Count"),
        tooltip=['Risk', 'Bucket', 'Count']
    )

    text = base.mark_text(baseline='middle').encode(
        text='Count',
        color=alt.condition(
            alt.datum.Count > 10,
            alt.value('black'),
            alt.value('white')
        )
    )

    st.altair_chart((heatmap + text).properties(height=250), use_container_width=True)

def funnel_chart(df=None):
    if df is None or df.empty:
        st.info("No data for funnel chart.")
        return

    cases_opened = len(df)
    investigations = len(df[df['status'].isin(['Review', 'Pending Review', 'Escalated'])])
    sar_drafted = len(df[df['status'].isin(['Draft', 'Pending Review'])])
    sar_filed = len(df[df['status'].isin(['Approved', 'Filed'])])
    alerts_generated = int(cases_opened * 2.5)

    if alerts_generated == 0:
        st.info("No funnel data.")
        return

    funnel_data = pd.DataFrame({
        'Stage': ['Alerts Generated', 'Cases Opened', 'Investigations', 'SAR Drafted', 'SAR Filed'],
        'Value': [alerts_generated, cases_opened, investigations, sar_drafted, sar_filed],
        'SortColor': ['#2A3F55', '#2A3F55', '#2A3F55', '#C9A227', '#0D9488']
    })

    base = alt.Chart(funnel_data).encode(
        y=alt.Y('Stage', sort=['Alerts Generated', 'Cases Opened', 'Investigations', 'SAR Drafted', 'SAR Filed'], axis=None),
        x=alt.X('Value', axis=None, scale=alt.Scale(domain=[0, alerts_generated * 1.1]))
    )

    bar = base.mark_bar(cornerRadius=4).encode(
        color=alt.Color('SortColor', scale=None),
        tooltip=['Stage', 'Value']
    )

    text_value = base.mark_text(align='left', dx=5, color='#FFFFFF', fontWeight=600).encode(
        text='Value'
    )

    text_label = base.mark_text(align='right', dx=-5, color='#B0B8C1').encode(
        text='Stage'
    )

    st.altair_chart((bar + text_value + text_label).properties(height=200), use_container_width=True)

def render_lifecycle_progress(current_status):
    stages = ["Alert Generated", "Under Review", "Escalated", "SAR Drafted", "Filed", "Closed"]

    status_map = {
        "Open": 0,
        "Review": 1, "Pending Review": 1,
        "High": 2, "Critical": 2,
        "Escalated": 2,
        "Draft": 3,
        "Approved": 4, "Filed": 4,
        "Closed": 5
    }

    current_idx = status_map.get(current_status, 0)

    html = '<div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0;">'

    for i, stage in enumerate(stages):
        if i < current_idx:
            color = "#0D9488"
            icon = "✓"
            weight = "600"
            opacity = "1"
        elif i == current_idx:
            color = "#C9A227"
            icon = "●"
            weight = "700"
            opacity = "1"
        else:
            color = "#2A3F55"
            icon = "○"
            weight = "400"
            opacity = "0.6"

        line = ""
        if i < len(stages) - 1:
            line_color = "#0D9488" if i < current_idx else "#2A3F55"
            line = f'<div style="flex-grow: 1; height: 2px; background-color: {line_color}; margin: 0 10px;"></div>'

        step_html = f'''
        <div style="display: flex; flex-direction: column; align-items: center; min-width: 60px;">
            <div style="color: {color}; font-size: 1.2rem; margin-bottom: 5px;">{icon}</div>
            <div style="color: {color if i <= current_idx else '#B0B8C1'}; font-size: 0.75rem; text-align: center; font-weight: {weight}; opacity: {opacity};">{stage}</div>
        </div>
        {line}
        '''
        html += step_html

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Dialog Views
# -----------------------------------------------------------------------------

@st.dialog("Audit Trail & Timeline")
def handle_audit_view(case_id, row_data):
    st.markdown(f"**Case ID:** `{case_id}`")

    current_status = row_data.get('Status', 'Open')
    render_lifecycle_progress(current_status)

    st.markdown("---")

    try:
        # Parse case_id to numeric if needed
        try:
            numeric_id = int(str(case_id).replace('CAS-', ''))
        except:
            numeric_id = case_id

        history = get_case_audit_history(numeric_id)

        if not history:
            st.info("No audit history found for this case.")
        else:
            for event in history:
                with st.container():
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        ts = event.get('timestamp', '')
                        if isinstance(ts, datetime.datetime):
                            st.caption(ts.strftime("%H:%M"))
                            st.caption(ts.strftime("%Y-%m-%d"))
                        else:
                            st.caption(str(ts))
                    with c2:
                        st.markdown(f"**{event.get('action', 'N/A')}**")
                        st.markdown(f"User: `{event.get('user', 'N/A')}` | Model: `{event.get('model_version', 'N/A')}`")
                        st.markdown(f"Risk Version: `{event.get('risk_version', 'N/A')}`")
                        if event.get('details'):
                            with st.expander("Details"):
                                st.text(event['details'])
                    st.divider()

    except Exception as e:
        st.error(f"Could not load history: {e}")

    # Role-Based Action: Filing Controls
    user_role = st.session_state.get('user_role', 'Analyst')
    if user_role not in ['Analyst']:
        st.markdown("### Actions")
        c_act1, c_act2 = st.columns(2)
        with c_act1:
            if st.button("✅ Approve & File SAR", type="primary", use_container_width=True):
                st.toast(f"SAR {case_id} Filed with FinCEN by {user_role}", icon="✅")
        with c_act2:
            if st.button("↩️ Return for Rework", use_container_width=True):
                st.toast(f"SAR {case_id} returned to Analyst", icon="↩️")
    else:
        st.info("ℹ️ Filing controls are restricted to Reviewers and MLROs.")

@st.dialog("Risk Analysis Breakdown")
def handle_risk_view(case_id, row_data):
    st.markdown(f"### Case: `{case_id}`")

    risk_level = row_data.get('Risk', 'High')
    risk_score = 88 if risk_level == 'High' else (65 if risk_level == 'Medium' else 25)
    confidence = 0.94

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Risk Score", f"{risk_score}/100", delta="Critical" if risk_score > 80 else "Normal", delta_color="inverse")
    with c2: st.metric("Model Confidence", f"{int(confidence*100)}%")
    with c3: st.metric("Typologies Matches", "2")

    st.markdown("---")

    st.caption("Feature Contribution to Risk Score")
    feat_data = pd.DataFrame({
        'Feature': ['Structured Cash', 'Velocity > 3 Days', 'High Risk Geo', 'New Account', 'Round Amounts'],
        'Impact': [35, 25, 15, 10, 5]
    })

    bar_chart = alt.Chart(feat_data).encode(
        x=alt.X('Impact', title='Contribution Points'),
        y=alt.Y('Feature', sort='-x', title=None),
        color=alt.Color('Impact', scale=alt.Scale(scheme='reds'), legend=None),
        tooltip=['Feature', 'Impact']
    ).mark_bar().properties(height=200)

    st.altair_chart(bar_chart, use_container_width=True)

    c_left, c_right = st.columns(2)
    with c_left:
        st.markdown("**Triggered Rules**")
        st.warning("⚠️ R-102: Cumulative Cash > $10k")
        st.warning("⚠️ R-205: Rapid Movement of Funds")
        st.info("ℹ️ R-001: KYC Update Recent")

    with c_right:
        st.markdown("**Suspected Typologies**")
        st.markdown("- **Structuring / Smurfing** (95% Match)")
        st.markdown("- **Money Laundering** (70% Match)")

    user_role = st.session_state.get('user_role', 'Analyst')
    if user_role in ['MLRO', 'Compliance Head']:
        st.markdown("---")
        st.markdown("🔒 **MLRO Controls**")
        c_risk, c_btn = st.columns([3, 1])
        with c_risk:
            new_risk = st.selectbox("Override Risk Level", ["Low", "Medium", "High", "Critical"], index=2, key=f"risk_override_{case_id}")
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Update Risk"):
                st.toast(f"Risk updated to {new_risk} by {user_role}", icon="🛡️")

def render_dashboard():
    # Header & Export Actions
    h_c1, h_c2 = st.columns([2, 1])
    with h_c1:
        st.title("SARcastic AI Dashboard")
    with h_c2:
        st.markdown('<div style="display: flex; gap: 10px; justify-content: flex-end; align-items: center; height: 100%;">', unsafe_allow_html=True)
        report_text = generate_regulatory_report()
        st.download_button(
            "📄 Gen. Report",
            data=report_text,
            file_name=f"SAR_Summary_{datetime.date.today()}.txt",
            mime="text/plain",
            help="Generate Regulatory SAR Summary Report (Text)"
        )

        try:
            all_cases = get_all_cases(limit=1000)
            if all_cases:
                csv_data = pd.DataFrame(all_cases).to_csv(index=False)
                st.download_button(
                    "📊 Export CSV",
                    data=csv_data,
                    file_name=f"cases_export_{datetime.date.today()}.csv",
                    mime="text/csv"
                )
            else:
                st.button("📊 Export CSV", disabled=True)
        except:
            st.button("📊 Export CSV", disabled=True)

        if st.button("🖨️ PDF", help="Export Dashboard View as PDF"):
            st.toast("Processing PDF Export... (Sent to print queue)", icon="🖨️")

        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Global Filters
    # -------------------------------------------------------------------------
    with st.expander("🔍 Filter Dashboard", expanded=True):
        f_c1, f_c2, f_c3, f_c4, f_c5 = st.columns(5)
        with f_c1:
            date_range = st.date_input("Date Range", [datetime.date.today() - datetime.timedelta(days=30), datetime.date.today()])
        with f_c2:
            risk_filter = st.multiselect("Risk Level", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
        with f_c3:
            analyst_filter = st.multiselect("Analyst", ["Sarah J.", "Mike R.", "David C.", "System"], default=[])
        with f_c4:
            typology_filter = st.multiselect("Typology", ["Structuring", "Money Laundering", "Human Trafficking"], default=[])
        with f_c5:
            status_filter = st.multiselect("Status", ["Open", "Review", "Closed", "Approved", "Draft", "Filed", "Pending Review"], default=["Open", "Review", "Draft"])

        apply_filters = st.button("Apply Filters", type="primary")

    # -------------------------------------------------------------------------
    # Data Fetching — ALWAYS from Database via Backend API
    # -------------------------------------------------------------------------
    try:
        cases = get_all_cases(limit=1000)
        if cases:
            df = pd.DataFrame(cases)
            # Map Analyst IDs to Names
            analyst_map = {1: "Admin", 2: "Sarah J.", 3: "Mike R.", 4: "Jane M.", 5: "David C.", 6: "Emma L.", 7: "Lucas R.", 8: "System", 9: "Test User", 10: "Auditor"}
            if not df.empty:
                df['analyst_name'] = df['analyst_id'].map(analyst_map).fillna("Unknown")
                df['typology'] = df['generated_narrative'].apply(
                    lambda x: "Structuring" if "structuring" in str(x).lower() else (
                        "Money Laundering" if "laundering" in str(x).lower() else "General"
                    )
                )
        else:
            df = pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        df = pd.DataFrame()

    if df.empty:
        st.warning("No cases found in the database. Create cases via Case Management.")
        return

    # -------------------------------------------------------------------------
    # Filter Logic
    # -------------------------------------------------------------------------
    if len(date_range) == 2:
        start_date, end_date = date_range
        if not pd.api.types.is_datetime64_any_dtype(df['created_at']):
            df['created_at'] = pd.to_datetime(df['created_at'])

        mask = (df['created_at'].dt.date >= start_date) & (df['created_at'].dt.date <= end_date)
        df = df.loc[mask]

    if risk_filter:
        df = df[df['risk_level'].isin(risk_filter)]
    if analyst_filter:
        df = df[df['analyst_name'].isin(analyst_filter)]
    if typology_filter:
        df = df[df['typology'].isin(typology_filter)]
    if status_filter:
        df = df[df['status'].isin(status_filter)]

    # -------------------------------------------------------------------------
    # KPIs Calculation (Dynamic from real data)
    # -------------------------------------------------------------------------
    metrics = {
        "sar_filed_month": 0,
        "avg_time_to_file": 0,
        "sla_breach_pct": 0.0,
        "backlog_30_days": 0,
        "continuing_sar": 0
    }

    if not df.empty:
        if not pd.api.types.is_datetime64_any_dtype(df['created_at']):
            df['created_at'] = pd.to_datetime(df['created_at'])

        current_month = datetime.datetime.now().month
        current_year = datetime.datetime.now().year

        metrics["sar_filed_month"] = len(df[
            (df['created_at'].dt.month == current_month) &
            (df['created_at'].dt.year == current_year)
        ])

        now = pd.Timestamp.now()
        breaches = df[
            (df['status'] != 'Closed') &
            (df['status'] != 'Approved') &
            (df['status'] != 'Filed') &
            (df['created_at'] < (now - pd.Timedelta(days=30)))
        ]
        metrics["backlog_30_days"] = len(breaches)
        if len(df) > 0:
            metrics["sla_breach_pct"] = round((len(breaches) / len(df)) * 100, 1)

        if 'generated_narrative' in df.columns:
            continuing = df[df['generated_narrative'].astype(str).str.contains('continuing', case=False, na=False)]
            metrics["continuing_sar"] = len(continuing)

    # 0. Top Level KPIs
    t_c1, t_c2, t_c3, t_c4, t_c5 = st.columns(5)
    with t_c1: kpi_card("SAR Filed (Period)", f"{metrics['sar_filed_month']}")
    with t_c2: kpi_card("Avg File Time", f"{metrics['avg_time_to_file']} Days")
    with t_c3: kpi_card("SLA Breach %", f"{metrics['sla_breach_pct']}%")
    with t_c4: kpi_card("Backlog > 30 Days", f"{metrics['backlog_30_days']}")
    with t_c5: kpi_card("Continuing SARs", f"{metrics['continuing_sar']}")

    st.markdown("<div style='margin-bottom: 20px'></div>", unsafe_allow_html=True)

    # 1. Metrics (Second Row)
    total_cases_count = len(df)
    high_risk_count = len(df[df['risk_level'] == 'High'])
    pending_count = len(df[df['status'].isin(['Review', 'Pending Review'])])
    flagged_count = len(df[df['risk_level'].isin(['High', 'Critical'])])

    col1, col2, col3, col4 = st.columns(4)
    with col1: kpi_card("Total Cases", f"{total_cases_count}")
    with col2: kpi_card("High Risk Cases", f"{high_risk_count}")
    with col3: kpi_card("Pending Review", f"{pending_count}")
    with col4: kpi_card("Flagged Alerts", f"{flagged_count}")

    st.write("")

    # 2. Charts & Activity
    m_col1, m_col2 = st.columns([2, 1])
    with m_col1:
        st.markdown('<div class="content-card"><div class="card-header">Recent Activity</div>', unsafe_allow_html=True)

        if not df.empty:
            display_df = df[['id', 'analyst_name', 'risk_level', 'status', 'created_at']].copy()
            display_df.columns = ['ID', 'Analyst', 'Risk', 'Status', 'Date']

            display_df['Risk Breakdown'] = False
            display_df['Audit View'] = False

            edited_df = st.data_editor(
                display_df.head(10),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Risk Breakdown": st.column_config.CheckboxColumn(
                        "Risk Details",
                        help="View detailed risk analysis",
                        default=False,
                    ),
                    "Audit View": st.column_config.CheckboxColumn(
                        "Audit Trail",
                        help="View timeline and history",
                        default=False,
                    )
                },
                disabled=['ID', 'Analyst', 'Risk', 'Status', 'Date'],
                key="case_table_editor"
            )

            risk_triggered = edited_df[edited_df['Risk Breakdown'] == True]
            if not risk_triggered.empty:
                row = risk_triggered.iloc[0]
                handle_risk_view(row['ID'], row)

            elif not edited_df[edited_df['Audit View'] == True].empty:
                audit_triggered = edited_df[edited_df['Audit View'] == True]
                row = audit_triggered.iloc[0]
                handle_audit_view(row['ID'], row)

        else:
            st.info("No cases match the selected filters.")

        st.markdown('</div>', unsafe_allow_html=True)

        # Funnel Chart Row
        st.markdown('<div class="content-card"><div class="card-header">Conversion Funnel</div>', unsafe_allow_html=True)
        funnel_chart(df if not df.empty else None)
        st.markdown('</div>', unsafe_allow_html=True)

    with m_col2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Risk Distribution</div>', unsafe_allow_html=True)

        if not df.empty:
            risk_counts = df['risk_level'].value_counts().reset_index()
            risk_counts.columns = ['Risk Level', 'Cases']
            risk_chart(risk_counts)
        else:
            st.info("No data")

        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-header">Case Aging Heatmap</div>', unsafe_allow_html=True)
        if not df.empty:
            valid_records = df[['created_at', 'risk_level']].to_dict('records')
            case_aging_heatmap(valid_records)
        else:
            st.info("No aging data.")
        st.markdown('</div>', unsafe_allow_html=True)

def render_case_creation():
    st.title("Create New SAR Case")

    tab_manual, tab_csv = st.tabs(["📝 Manual Entry", "📂 CSV Batch Upload"])

    with tab_manual:
        st.markdown('<div class="content-card"><div class="card-header">Case Information</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            customer_name = st.text_input("Customer Entity Name", value="")
            risk_category = st.selectbox("Risk Category", ["Structuring", "Money Laundering", "Human Trafficking"])
        with c2:
            account_numb = st.text_input("Account Number", value="")
            case_priority = st.selectbox("Priority", ["Standard", "Urgent", "Critical"])

        st.markdown("### Transaction Analysis")
        tx_details = st.text_area("Transaction Details", height=150, value="",
                                  placeholder="Enter transaction details: dates, amounts, channels, counterparties...")

        col_submit, col_generate = st.columns(2)

        with col_submit:
            if st.button("📁 Create Case Only", type="secondary", use_container_width=True):
                if not customer_name.strip():
                    st.error("Customer name is required.")
                elif not tx_details.strip():
                    st.error("Transaction details are required.")
                else:
                    with st.spinner("Creating case..."):
                        data_payload = {
                            "kyc": {"full_name": customer_name, "date_of_birth": "N/A", "address": "N/A"},
                            "accounts": [account_numb],
                            "transactions": tx_details
                        }
                        new_id = create_sar_case(1, data_payload, "")
                        if new_id:
                            st.success(f"✅ Case #{new_id} created successfully. Use 'Generate SAR' to create the narrative.")
                        else:
                            st.error("Failed to create case. Check backend connection.")

        with col_generate:
            if st.button("🤖 Create Case & Generate SAR", type="primary", use_container_width=True):
                if not customer_name.strip():
                    st.error("Customer name is required.")
                elif not tx_details.strip():
                    st.error("Transaction details are required.")
                else:
                    # Step 1: Create the case
                    with st.spinner("📁 Step 1/2 — Creating case record..."):
                        data_payload = {
                            "kyc": {"full_name": customer_name, "date_of_birth": "N/A", "address": "N/A"},
                            "accounts": [account_numb],
                            "transactions": tx_details
                        }
                        new_id = create_sar_case(1, data_payload, "")

                    if not new_id:
                        st.error("Failed to create case. Check backend connection.")
                    else:
                        st.success(f"✅ Case #{new_id} created.")

                        # Step 2: Generate SAR Narrative via LLM
                        with st.spinner("🤖 Step 2/2 — AI generating detailed SAR narrative... (this may take 30-90 seconds)"):
                            result = generate_sar_for_case(new_id)

                        if "error" in result:
                            st.error(f"SAR generation failed: {result['error']}")
                        else:
                            narrative = result.get("narrative", "")
                            prompt = result.get("prompt", "")

                            st.markdown("---")

                            # SAR Report Header
                            st.markdown(f"""
                            <div style="background-color:#102A43; border:1px solid #2A3F55; border-radius:6px; padding:20px; margin-bottom:16px;">
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                                    <div>
                                        <span style="font-size:1.4rem; font-weight:700; color:#C9A227;">📄 Suspicious Activity Report</span>
                                        <span style="margin-left:12px; padding:3px 8px; border-radius:4px; font-size:0.75rem; font-weight:600; background-color:rgba(13,148,136,0.2); color:#0D9488; border:1px solid #0D9488;">GENERATED</span>
                                    </div>
                                    <div style="color:#B0B8C1; font-size:0.85rem;">Case #{new_id} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
                                </div>
                                <div style="display:flex; gap:24px; font-size:0.85rem; color:#B0B8C1; border-top:1px solid #2A3F55; padding-top:8px;">
                                    <span><strong>Subject:</strong> {customer_name}</span>
                                    <span><strong>Category:</strong> {risk_category}</span>
                                    <span><strong>Priority:</strong> {case_priority}</span>
                                    <span><strong>Account:</strong> {account_numb or 'N/A'}</span>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

                            # SAR Narrative Body
                            st.markdown(f"""
                            <div style="background-color:#1E3A5F; border-left:4px solid #C9A227; padding:20px; border-radius:4px; color:#E0E0E0; line-height:1.75; font-size:0.95rem; white-space:pre-wrap;">
{narrative}
                            </div>
                            """, unsafe_allow_html=True)

                            # Expandable Details
                            with st.expander("📋 View LLM Prompt Used"):
                                st.code(prompt, language="text")

                            # Download SAR as text file
                            sar_header = f"SUSPICIOUS ACTIVITY REPORT\nCase ID: {new_id}\nSubject: {customer_name}\nGenerated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nCategory: {risk_category}\nPriority: {case_priority}\n{'='*60}\n\n"
                            st.download_button(
                                "⬇️ Download SAR Report (.txt)",
                                data=sar_header + narrative,
                                file_name=f"SAR_Case_{new_id}_{datetime.date.today()}.txt",
                                mime="text/plain"
                            )

        st.markdown('</div>', unsafe_allow_html=True)

    with tab_csv:
        st.markdown('<div class="content-card"><div class="card-header">Upload Transaction Data</div>', unsafe_allow_html=True)
        st.info("Upload a CSV file with columns: customer_id, amount, transaction_date. Logic will automatically create a case, assess risk, and prepare it for SAR generation.")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            if st.button("🚀 Upload & Analyze", type="primary"):
                with st.spinner("Processing CSV and Running Risk Engine..."):
                    result = upload_csv_case(uploaded_file)
                
                if "error" in result:
                    st.error(result['error'])
                else:
                    st.session_state.csv_case_id = result.get('case_id')
                    st.session_state.csv_result = result
                    st.success("File Processed Successfully!")
            
            # Show results if we have them in session
            if "csv_result" in st.session_state and st.session_state.csv_result:
                result = st.session_state.csv_result
                new_case_id = result.get('case_id')
                risk_score = result.get('risk_score')
                risk_level = result.get('risk_level')
                tx_count = result.get('tx_count')
                triggered_rules = result.get('triggered_rules', [])

                # Display Results
                r1, r2, r3, r4 = st.columns(4)
                with r1: st.metric("New Case ID", f"#{new_case_id}")
                with r2: st.metric("Risk Score", f"{risk_score}/100")
                with r3: st.metric("Risk Level", risk_level, delta="High" if risk_level in ['High', 'Critical'] else "Normal", delta_color="inverse")
                with r4: st.metric("Transactions", tx_count)
                
                if triggered_rules:
                    st.warning(f"⚠️ Triggered Rules: {len(triggered_rules)}")
                    for rule in triggered_rules:
                        st.caption(f"- {rule}")
                
                st.divider()
                
                col_gen_sar, col_view = st.columns(2)
                with col_gen_sar:
                    if st.button("🤖 Generate SAR Narrative Now", key="csv_gen_sar"):
                        with st.spinner("Generating SAR Narrative..."):
                            gen_result = generate_sar_for_case(new_case_id)
                            
                        if "error" in gen_result:
                            st.error(gen_result['error'])
                        else:
                            narrative = gen_result.get("narrative", "")
                            st.success("SAR Narrative Generated!")
                            st.markdown(f"""
                            <div style="background-color:#1E3A5F; border-left:4px solid #C9A227; padding:20px; border-radius:4px; color:#E0E0E0; line-height:1.75; font-size:0.95rem; white-space:pre-wrap;">
{narrative}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.download_button(
                                "⬇️ Download SAR (.txt)",
                                data=narrative,
                                file_name=f"SAR_Case_{new_case_id}.txt",
                                mime="text/plain"
                            )

        st.markdown('</div>', unsafe_allow_html=True)

def render_case_repository():
    st.title("Case Repository")

    cases = get_all_cases(limit=50)
    if not cases:
        st.info("No cases in repository. Create one in Case Management!")
        return

    df = pd.DataFrame(cases)

    # Summary stats
    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1: kpi_card("Total Cases", str(len(df)))
    with sc2: kpi_card("Draft", str(len(df[df['status'] == 'Draft'])))
    with sc3: kpi_card("In Review", str(len(df[df['status'].isin(['Review', 'Pending Review'])])))
    with sc4: kpi_card("Filed", str(len(df[df['status'].isin(['Filed', 'Approved'])])))

    st.write("")

    st.markdown(f'<div class="content-card"><div class="card-header">Case List ({len(df)})</div>', unsafe_allow_html=True)
    st.dataframe(df[['id', 'customer_name', 'status', 'risk_level', 'created_at', 'analyst_id']], use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Generate SAR for specific case
    st.markdown('<div class="content-card"><div class="card-header">Generate SAR for Existing Case</div>', unsafe_allow_html=True)

    case_ids = df['id'].tolist()
    selected_case = st.selectbox("Select Case ID", case_ids, format_func=lambda x: f"Case #{x} — {df[df['id']==x]['customer_name'].values[0]} ({df[df['id']==x]['status'].values[0]})")

    if st.button("🤖 Generate Detailed SAR", type="primary"):
        with st.spinner("🤖 Generating detailed SAR narrative via LLM... (this may take 30-90 seconds)"):
            result = generate_sar_for_case(selected_case)

        if "error" in result:
            st.error(f"SAR generation failed: {result['error']}")
        else:
            narrative = result.get("narrative", "")
            prompt = result.get("prompt", "")
            case_row = df[df['id'] == selected_case].iloc[0]

            st.success(f"✅ SAR generated for Case #{selected_case}")

            st.markdown(f"""
            <div style="background-color:#102A43; border:1px solid #2A3F55; border-radius:6px; padding:20px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <span style="font-size:1.4rem; font-weight:700; color:#C9A227;">📄 Suspicious Activity Report</span>
                    <span style="color:#B0B8C1; font-size:0.85rem;">Case #{selected_case} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
                </div>
                <div style="display:flex; gap:24px; font-size:0.85rem; color:#B0B8C1; border-top:1px solid #2A3F55; padding-top:8px;">
                    <span><strong>Subject:</strong> {case_row.get('customer_name', 'N/A')}</span>
                    <span><strong>Status:</strong> {case_row.get('status', 'N/A')}</span>
                    <span><strong>Risk:</strong> {case_row.get('risk_level', 'N/A')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div style="background-color:#1E3A5F; border-left:4px solid #C9A227; padding:20px; border-radius:4px; color:#E0E0E0; line-height:1.75; font-size:0.95rem; white-space:pre-wrap;">
{narrative}
            </div>
            """, unsafe_allow_html=True)

            with st.expander("📋 View LLM Prompt Used"):
                st.code(prompt, language="text")

            st.download_button(
                "⬇️ Download SAR Report (.txt)",
                data=f"SAR REPORT — Case #{selected_case}\nSubject: {case_row.get('customer_name', 'N/A')}\nGenerated: {datetime.datetime.now()}\n{'='*60}\n\n{narrative}",
                file_name=f"SAR_Case_{selected_case}_{datetime.date.today()}.txt",
                mime="text/plain"
            )

    st.markdown('</div>', unsafe_allow_html=True)

def render_audit_trail():
    st.title("Audit Trail")

    logs = get_audit_logs(limit=50)
    if not logs:
        st.info("No audit logs found.")
        return

    df = pd.DataFrame(logs)
    st.markdown('<div class="content-card"><div class="card-header">System Logs</div>', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

def render_model_explainability():
    st.title("Model Explainability")
    st.info("This section queries the ChromaDB Vector Store for regulatory context.")

    query = st.text_input("Test RAG Query", "structuring threshold")
    if st.button("Retrieve Context"):
        docs = retrieve_relevant_docs(query)
        if docs:
            for d in docs:
                if isinstance(d, list):
                    for item in d:
                        st.markdown(f"> {item}")
                else:
                    st.markdown(f"> {d}")
        else:
            st.warning("No documents found.")

            st.warning("No documents found.")

def render_sar_report_page():
    st.title("📄 Suspicious Activity Report (SAR) Module")
    
    # Select Case
    cases = get_all_cases(50)
    if not cases:
        st.warning("No cases available.")
        return
        
    df_cases = pd.DataFrame(cases)
    case_opts = df_cases['id'].tolist()
    
    # Auto-select if passed from another page
    default_idx = 0
    if "selected_case_id" in st.session_state:
        if st.session_state.selected_case_id in case_opts:
            default_idx = case_opts.index(st.session_state.selected_case_id)
            
    selected_id = st.selectbox("Select Case for SAR Filing", case_opts, index=default_idx, format_func=lambda x: f"Case #{x}")
    st.session_state.selected_case_id = selected_id
    
    # Fetch Data
    details = get_sar_details(selected_id)
    if not details:
        st.error("Failed to load SAR details. Initialize the case first.")
        return
        
    # Tabs for Annexure II
    tab_header, tab_a, tab_b, tab_c, tab_d, tab_e, tab_f, tab_export = st.tabs([
        "🔐 Header", 
        "🟦 Part A (Entity)", 
        "🟦 Part B (Narrative)", 
        "🟦 Part C (Action)", 
        "🟦 Part D (Indicators)", 
        "🟦 Part E (Subjects)", 
        "🟦 Part F (Goods)", 
        "📄 Export"
    ])
    
    with tab_header:
        st.markdown(f"### SAR Reference: `{details.get('internal_ref_id')}`")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Risk Score", details.get('risk_score', 'Medium'))
            st.metric("Generated Date", details.get('created_at', 'N/A')[:10])
        with c2:
            st.metric("Case ID", f"#{selected_id}")
            st.metric("Status", "Draft") # Could fetch real status
            
    with tab_a:
        st.subheader("Part A: Particulars of Reporting Entity")
        part_a = details.get('part_a', {})
        if isinstance(part_a, str): part_a = json.loads(part_a)
        
        with st.form("part_a_form"):
            col1, col2 = st.columns(2)
            with col1:
                entity_name = st.text_input("Reporting Entity Name", value=part_a.get('entity_name', 'SARcastic AI Financial Services'))
                reg_number = st.text_input("Registration Number", value=part_a.get('reg_number', ''))
                business_type = st.selectbox("Nature of Business", ["Bank", "FinTech", "Casino", "Dealer", "Other"], index=0)
            with col2:
                street = st.text_input("Street Address", value=part_a.get('street', ''))
                city = st.text_input("City", value=part_a.get('city', 'New York'))
                country = st.text_input("Country", value=part_a.get('country', 'USA'))
            
            st.markdown("#### Compliance Officer")
            co_col1, co_col2 = st.columns(2)
            with co_col1:
                co_first = st.text_input("First Name", value=part_a.get('co_first', ''))
                co_last = st.text_input("Last Name", value=part_a.get('co_last', ''))
                co_phone = st.text_input("Telephone", value=part_a.get('co_phone', ''))
            with co_col2:
                co_email = st.text_input("Email", value=part_a.get('co_email', ''))
                co_desi = st.text_input("Designation", value=part_a.get('co_designation', 'MLRO'))
            
            if st.form_submit_button("Save Part A"):
                new_data = {
                    "entity_name": entity_name, "reg_number": reg_number, "business_type": business_type,
                    "street": street, "city": city, "country": country,
                    "co_first": co_first, "co_last": co_last, "co_phone": co_phone,
                    "co_email": co_email, "co_designation": co_desi
                }
                if update_sar_section(selected_id, "part_a", new_data):
                    st.success("Part A Saved")

    with tab_b:
        st.subheader("Part B: Description of Suspicious Activity")
        current_narrative = details.get('part_b_narrative', '') or details.get('generated_narrative', '')
        
        st.info("💡 AI Generated Narrative based on Transactions and Rule Triggers.")
        
        if st.button("✨ Regenerate Narrative (LLM)"):
             with st.spinner("Generating..."):
                 res = generate_sar_for_case(selected_id)
                 if "narrative" in res:
                     current_narrative = res['narrative']
                     # Update details immediately (though generate_sar writes to DB, details dict is stale)
                     st.experimental_rerun()
        
        new_narrative = st.text_area("Narrative Content", value=current_narrative, height=600)
        
        if st.button("Save Part B"):
            # Update generated_narrative in main table and part_b in details
            # Currently sar_service updates generated_narrative. 
            # We should probably sync them or just use generated_narrative.
            # But the requirement is strict Part B.
            if update_sar_section(selected_id, "part_b_narrative", new_narrative):
                st.success("Part B Saved")

    with tab_c:
        st.subheader("Part C: Action Taken")
        part_c = details.get('part_c', {})
        if isinstance(part_c, str): part_c = json.loads(part_c)
        
        with st.form("part_c_form"):
            c1, c2 = st.columns(2)
            with c1:
                action = st.selectbox("Action Taken", ["Allowed", "Blocked", "Frozen", "Delayed"], index=0)
                account_flagged = st.checkbox("Account Flagged?", value=part_c.get('flagged', False))
                edd_init = st.checkbox("EDD Initiated?", value=part_c.get('edd', False))
            with c2:
                contacted = st.radio("Customer Contacted?", ["Yes", "No"], index=1)
                escalation_ref = st.text_input("Internal Escalation Ref", value=part_c.get('escalation_ref', ''))
            
            notes = st.text_area("Internal Case Notes", value=part_c.get('notes', ''))
            
            if st.form_submit_button("Save Part C"):
                data_c = {
                    "action": action, "flagged": account_flagged, "edd": edd_init,
                    "contacted": contacted, "escalation_ref": escalation_ref, "notes": notes,
                    "officer": st.session_state.get('user_email', 'Unknown')
                }
                if update_sar_section(selected_id, "part_c", data_c):
                    st.success("Part C Saved")

    with tab_d:
        st.subheader("Part D: Indicators")
        part_d = details.get('part_d', [])
        if isinstance(part_d, str): part_d = json.loads(part_d)
        
        indicators_list = [
            "Activity does not match client profile", "Money Laundering", "Fraud", "Structuring",
            "Smurfing", "Corruption / Bribery", "Terrorism", "Human Trafficking", "Tax Evasion",
            "PEP Involvement", "Adverse Media", "OFAC/Watchlist hit", "Hawala", "Environmental Crime",
            "Insider Trading", "Drug Trafficking", "Arms Trafficking", "Proliferation", "Other"
        ]
        
        selected_indicators = st.multiselect("Select all that apply", indicators_list, default=part_d)
        
        if st.button("Save Part D"):
            if update_sar_section(selected_id, "part_d", selected_indicators):
                st.success("Part D Saved")

    with tab_e:
        st.subheader("Part E: Persons, Entities, and Accounts")
        
        st.markdown("**1. Person Details**")
        part_e1 = details.get('part_e1_person', {})
        if isinstance(part_e1, str): part_e1 = json.loads(part_e1)
        
        with st.expander("Edit Person Details", expanded=True):
            pe_c1, pe_c2 = st.columns(2)
            with pe_c1:
                p_first = st.text_input("First Name", value=part_e1.get('first', ''))
                p_id = st.text_input("ID / Passport", value=part_e1.get('id_num', ''))
                p_nat = st.text_input("Nationality", value=part_e1.get('nationality', ''))
            with pe_c2:
                p_last = st.text_input("Last Name", value=part_e1.get('last', ''))
                p_occ = st.text_input("Occupation", value=part_e1.get('occupation', ''))
                is_pep = st.checkbox("Is PEP?", value=part_e1.get('is_pep', False))
            
            if st.button("Save Person"):
                pe_data = {"first": p_first, "last": p_last, "id_num": p_id, "nationality": p_nat, "occupation": p_occ, "is_pep": is_pep}
                update_sar_section(selected_id, "part_e1_person", pe_data)
                st.toast("Person saved")

        st.markdown("**2. Accounts Involved**")
        part_e2 = details.get('part_e2_accounts', [])
        if isinstance(part_e2, str): part_e2 = json.loads(part_e2)
        if not part_e2: part_e2 = [{"account_number": "", "bank": "", "balance": 0.0}]
        
        df_acc = pd.DataFrame(part_e2)
        edited_acc = st.data_editor(df_acc, num_rows="dynamic", key="acc_editor")
        
        if st.button("Save Accounts"):
            acc_list = edited_acc.to_dict('records')
            update_sar_section(selected_id, "part_e2_accounts", acc_list)
            st.toast("Accounts saved")

    with tab_f:
        st.subheader("Part F: Goods / Services")
        part_f = details.get('part_f_goods', {})
        if isinstance(part_f, str): part_f = json.loads(part_f)
        
        disposition = st.multiselect("Disposition of Funds", 
            ["Property", "Shares", "EFT", "Vehicle", "Jewelry", "Firearm", "Land", "Equipment", "Other"],
            default=part_f.get('disposition', []))
            
        st.markdown("**Items Involved**")
        goods_list = part_f.get('items', [{"description": "", "value": 0.0, "country": ""}])
        df_goods = pd.DataFrame(goods_list)
        edited_goods = st.data_editor(df_goods, num_rows="dynamic", key="goods_editor")
        
        if st.button("Save Part F"):
            f_data = {
                "disposition": disposition,
                "items": edited_goods.to_dict('records')
            }
            update_sar_section(selected_id, "part_f_goods", f_data)
            st.success("Part F Saved")

    with tab_export:
        st.subheader("Export & Submit")
        st.warning("Ensure all parts are completed before export.")
        
        if st.button("📄 Generate Regulator-Ready PDF"):
            st.toast("Generating PDF... (Mock)", icon="📄")
            time.sleep(1)
            st.success("PDF Generated Successfully")
            
        st.json(details) # Preview raw data
def main():
    if not st.session_state.authenticated:
        render_login()
        return

    load_design_system()
    with st.sidebar:
        st.markdown('<div style="font-size: 1.2rem; font-weight: 700; color: #C9A227; margin-bottom: 20px;">SARcastic AI</div>', unsafe_allow_html=True)
        st.caption(f"User: {st.session_state.user_email}")
        st.caption(f"Role: {st.session_state.get('user_role', 'Analyst')}")
        if st.button("Dashboard", use_container_width=True): st.session_state.page = "Dashboard"; st.rerun()
        if st.button("Case Management", use_container_width=True): st.session_state.page = "Case Creation"; st.rerun()
        if st.button("Case Repository", use_container_width=True): st.session_state.page = "Case Repository"; st.rerun()
        if st.button("SAR Reporting", use_container_width=True): st.session_state.page = "SAR Reporting"; st.rerun()
        if st.button("Audit Trail", use_container_width=True): st.session_state.page = "Audit Trail"; st.rerun()
        if st.button("Explainability", use_container_width=True): st.session_state.page = "Model Explainability"; st.rerun()
        st.markdown("---")
        if st.button("Logout"): st.session_state.authenticated = False; st.rerun()

    if st.session_state.page == "Dashboard": render_dashboard()
    elif st.session_state.page == "Case Creation": render_case_creation()
    elif st.session_state.page == "Case Repository": render_case_repository()
    elif st.session_state.page == "SAR Reporting": render_sar_report_page()
    elif st.session_state.page == "Audit Trail": render_audit_trail()
    elif st.session_state.page == "Model Explainability": render_model_explainability()

if __name__ == "__main__":
    main()
