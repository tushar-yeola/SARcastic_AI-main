import streamlit as st
import json

from auth.auth import authenticate
from rules.suspicious_rules import evaluate_rules
from llm.narrative_generator import generate_sar_narrative
from services.sar_service import (
    create_sar_case,
    update_edited_narrative,
    approve_sar
)
from services.audit_service import save_audit_log

st.set_page_config(page_title="SARcastic AI Narrative Generator")

# ---------------------------------------------
# Session Storage
# ---------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if "sar_id" not in st.session_state:
    st.session_state.sar_id = None

# ---------------------------------------------
# LOGIN SCREEN
# ---------------------------------------------
if not st.session_state.user:

    st.title("🔐 SARcastic AI Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = authenticate(username, password)
        if user:
            st.session_state.user = user
            st.success("Login successful")
        else:
            st.error("Invalid credentials")

# ---------------------------------------------
# MAIN APPLICATION
# ---------------------------------------------
else:

    st.sidebar.write(f"Logged in as: {st.session_state.user.username}")
    st.sidebar.write(f"Role: {st.session_state.user.role}")

    # -----------------------------------------
    # ANALYST PANEL
    # -----------------------------------------
    if st.session_state.user.role == "analyst":

        st.title("📝 Create SAR Case")

        full_name = st.text_input("Full Name")
        dob = st.text_input("Date of Birth (MM/DD/YYYY)")
        address = st.text_input("Address")

        account_number = st.text_input("Account Number")
        account_type = st.text_input("Account Type")

        start_date = st.text_input("Activity Start Date (MM/DD/YYYY)")
        end_date = st.text_input("Activity End Date (MM/DD/YYYY)")

        total_amount = st.number_input("Total Suspicious Amount", min_value=0.0)

        st.subheader("Transactions (JSON Format)")
        st.code('[{"amount": 9500, "type": "cash"}]')
        tx_input = st.text_area("Paste Transactions JSON")

        if st.button("Generate SAR"):

            transactions = json.loads(tx_input)

            data = {
                "kyc": {
                    "full_name": full_name,
                    "date_of_birth": dob,
                    "address": address
                },
                "accounts": [
                    {"account_number": account_number, "type": account_type}
                ],
                "transactions": transactions,
                "activity_start": start_date,
                "activity_end": end_date,
                "total_amount": total_amount,
                "subject_identified": True
            }

            # Run Rule Engine
            rule_result = evaluate_rules(data)

            if rule_result["errors"]:
                st.error("Validation Errors:")
                for e in rule_result["errors"]:
                    st.write("-", e)
            else:
                # Generate Narrative
                prompt, narrative = generate_sar_narrative(data, rule_result)

                # Save SAR
                sar_id = create_sar_case(
                    st.session_state.user.id,
                    data,
                    narrative
                )

                # Save Audit
                save_audit_log(
                    sar_id,
                    rule_result["triggered_rules"],
                    prompt,
                    narrative
                )

                st.session_state.sar_id = sar_id
                st.session_state.generated_narrative = narrative

                st.success("SAR Generated Successfully!")

        if "generated_narrative" in st.session_state:

            edited_text = st.text_area(
                "Edit Narrative Before Submission",
                st.session_state.generated_narrative,
                height=300
            )

            if st.button("Submit For Review"):
                update_edited_narrative(
                    st.session_state.sar_id,
                    edited_text
                )
                st.success("Submitted for Review")

    # -----------------------------------------
    # REVIEWER PANEL
    # -----------------------------------------
    elif st.session_state.user.role == "reviewer":

        st.title("🔎 Reviewer Panel")

        sar_id = st.number_input("Enter SAR ID to Approve", min_value=1)

        if st.button("Approve SAR"):
            approve_sar(sar_id)
            st.success("SAR Approved")
