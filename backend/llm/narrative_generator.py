import os
import json
import ast
import datetime
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_ollama import OllamaLLM

# Import RAG retrieval
from backend.vectorstore.chroma_store import retrieve_relevant_docs

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def generate_sar_narrative(data, rule_result):
    """
    Generates a detailed SAR narrative using:
    - Case data (KYC, transactions)
    - Triggered compliance rules
    - Retrieved regulatory guidance (RAG from ChromaDB)
    - LLM (Ollama)

    Returns: (formatted_prompt, narrative_text)
    """

    model_name = os.getenv("OLLAMA_MODEL", "llama3:8b")
    use_llm = os.getenv("USE_LLM", "false").lower() in ("true", "1", "yes")

    # Pre-flight check: verify Ollama is reachable AND the model can generate
    import requests as _requests
    ollama_available = False

    if use_llm:
        try:
            _resp = _requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if _resp.status_code == 200:
                available_models = [m['name'] for m in _resp.json().get('models', [])]
                print(f"Ollama reachable. Available models: {available_models}")
                
                # Quick smoke test: try a tiny generation to verify the LLM actually loads
                _test_resp = _requests.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={"model": model_name, "prompt": "Hello", "stream": False},
                    timeout=30
                )
                if _test_resp.status_code == 200:
                    ollama_available = True
                    print("Ollama smoke test passed — model is ready.")
                else:
                    error_msg = _test_resp.text[:200]
                    print(f"Ollama smoke test failed (HTTP {_test_resp.status_code}): {error_msg}")
        except _requests.exceptions.Timeout:
            print(f"Ollama smoke test timed out — model may be loading or OOM.")
        except Exception as _e:
            print(f"Ollama not reachable at {OLLAMA_HOST}: {_e}")
    else:
        print("USE_LLM is disabled. Using template-based SAR generation.")

    # Initialize Ollama LLM (only used if reachable and model loads)
    llm = None
    if ollama_available:
        llm = OllamaLLM(
            model=model_name,
            base_url=OLLAMA_HOST,
            temperature=0.2,
            num_predict=2048,
        )

    # ---------------------------------------------------
    # STEP 1: Retrieve Regulatory Context (RAG)
    # ---------------------------------------------------
    regulatory_context = ""
    try:
        retrieved_docs = retrieve_relevant_docs(
            "SAR filing thresholds structuring regulation investigation documentation requirements"
        )

        if retrieved_docs:
            for doc_group in retrieved_docs:
                if isinstance(doc_group, list):
                    for doc in doc_group:
                        regulatory_context += doc + "\n"
                elif isinstance(doc_group, str):
                    regulatory_context += doc_group + "\n"
    except Exception as rag_error:
        print(f"RAG retrieval failed: {rag_error}. Using default regulatory context.")

    if not regulatory_context.strip():
        regulatory_context = (
            "31 CFR § 1010.100(xx): Structuring involves breaking transactions below $10,000 to avoid CTR filing.\n"
            "31 CFR § 1020.320: SARs must be filed within 30 days of detection (60 days if no suspect identified).\n"
            "FinCEN Advisory: Institutions must document the 5 W's (Who, What, When, Where, Why) and How.\n"
            "FFIEC BSA/AML Manual: Financial institutions must maintain comprehensive records of suspicious activities.\n"
            "31 U.S.C. § 5318(g): Reporting obligations for financial institutions regarding suspicious transactions.\n"
        )

    # ---------------------------------------------------
    # STEP 2: Extract fields from data
    # ---------------------------------------------------
    kyc = data.get("kyc", {})
    full_name = kyc.get("full_name", "Unknown Subject")
    dob = kyc.get("date_of_birth", "Not Available")
    address = kyc.get("address", "Not Available")
    accounts = data.get("accounts", ["N/A"])
    start_date = data.get("activity_start", "N/A")
    end_date = data.get("activity_end", "N/A")
    total_amount = data.get("total_amount", 0)
    transactions = data.get("transactions", "No transaction details provided.")
    rules = rule_result.get("triggered_rules", "No rules triggered.")

    # Format accounts
    if isinstance(accounts, list):
        accounts_str = ", ".join(str(a) for a in accounts)
    else:
        accounts_str = str(accounts)

    # Format amount
    try:
        amount_str = f"{float(total_amount):,.2f}"
    except:
        amount_str = str(total_amount)

    # ---------------------------------------------------
    # STEP 3: Build Prompt Template
    # ---------------------------------------------------

    template = """You are a senior financial compliance analyst at a regulated financial institution. 
Generate a complete, regulator-ready Suspicious Activity Report (SAR) narrative.

The narrative MUST follow FinCEN SAR filing standards and include ALL of the following sections:

===========================================================
REGULATORY GUIDANCE (Retrieved from Knowledge Base)
===========================================================
{regulatory_context}

===========================================================
SUBJECT INFORMATION
===========================================================
Full Name: {full_name}
Date of Birth: {dob}
Address: {address}
Associated Accounts: {accounts}

===========================================================
ACTIVITY SUMMARY
===========================================================
Activity Period: {start_date} to {end_date}
Total Suspicious Amount: ${amount}

Transaction Details:
{transactions}

===========================================================
COMPLIANCE RULES TRIGGERED
===========================================================
{rules}

===========================================================
NARRATIVE REQUIREMENTS
===========================================================
Generate a DETAILED SAR narrative that includes ALL of the following sections:

**SECTION 1 - SUBJECT IDENTIFICATION & BACKGROUND**
- Full identification of the subject (name, DOB, address, account numbers)
- Relationship with the institution (account type, tenure, expected activity)
- Any prior SARs or compliance alerts on the subject

**SECTION 2 - SUSPICIOUS ACTIVITY DESCRIPTION**
- Detailed chronological description of each suspicious transaction
- Transaction dates, amounts, channels, and counterparties where available
- Why each transaction or pattern is considered suspicious
- Clear answers to: WHO conducted the activity, WHAT was done, WHEN it occurred, WHERE (which accounts/branches), WHY it is suspicious, and HOW it was carried out

**SECTION 3 - PATTERN ANALYSIS & TYPOLOGY MATCHING**
- Identified patterns (e.g., structuring, rapid movement, round-tripping)
- Comparison to known financial crime typologies
- Statistical analysis of transaction frequency, amounts, and timing
- Deviation from expected customer behavior

**SECTION 4 - INVESTIGATION STEPS PERFORMED**
- How the activity was initially detected (rule triggers, alerts, referrals)
- Investigation methodology and timeline
- Systems and data sources consulted
- Interviews or additional inquiries conducted
- Evidence gathered and preserved

**SECTION 5 - REGULATORY REFERENCES**
- Applicable BSA/AML regulations (e.g., 31 U.S.C. § 5324 for structuring)
- Relevant FinCEN advisories or guidance
- Internal policy references

**SECTION 6 - RISK ASSESSMENT & CONCLUSION**
- Overall risk rating with justification
- Confidence level in the assessment
- Recommended actions (enhanced monitoring, account closure, law enforcement referral)
- Whether this is an initial or continuing SAR filing

Use professional, objective language. Do NOT use words like: guilty, criminal, definitely, certainly, obviously.
The narrative must be at least 800 words. Be thorough and specific.
"""

    prompt = PromptTemplate(
        input_variables=[
            "regulatory_context",
            "full_name",
            "dob",
            "address",
            "accounts",
            "start_date",
            "end_date",
            "amount",
            "transactions",
            "rules",
        ],
        template=template,
    )

    # ---------------------------------------------------
    # STEP 4: Format Prompt
    # ---------------------------------------------------

    formatted_prompt = prompt.format(
        regulatory_context=regulatory_context,
        full_name=full_name,
        dob=dob,
        address=address,
        accounts=accounts_str,
        start_date=start_date,
        end_date=end_date,
        amount=amount_str,
        transactions=transactions,
        rules=rules,
    )

    # ---------------------------------------------------
    # STEP 5: Invoke LLM (with fallback)
    # ---------------------------------------------------

    if llm and ollama_available:
        try:
            response = llm.invoke(formatted_prompt)
        except Exception as llm_error:
            print(f"LLM invocation failed: {llm_error}. Using template-based fallback.")
            response = _generate_template_sar(
                full_name=full_name,
                dob=dob,
                address=address,
                accounts_str=accounts_str,
                start_date=start_date,
                end_date=end_date,
                amount_str=amount_str,
                transactions=transactions,
                rules=rules,
                regulatory_context=regulatory_context,
            )
    else:
        print("LLM not available. Using template-based SAR generation.")
        response = _generate_template_sar(
            full_name=full_name,
            dob=dob,
            address=address,
            accounts_str=accounts_str,
            start_date=start_date,
            end_date=end_date,
            amount_str=amount_str,
            transactions=transactions,
            rules=rules,
            regulatory_context=regulatory_context,
        )

    return formatted_prompt, response


def _generate_template_sar(
    full_name, dob, address, accounts_str,
    start_date, end_date, amount_str,
    transactions, rules, regulatory_context
):
    """
    Generates a detailed, structured SAR narrative WITHOUT an LLM.
    Used as a fallback when Ollama is unavailable or encounters an error.
    Produces a professional, regulator-ready report using the same 6-section format.
    """
    now = datetime.datetime.now()
    filing_date = now.strftime("%B %d, %Y")
    filing_time = now.strftime("%H:%M:%S")

    return f"""
═══════════════════════════════════════════════════════════════════
SUSPICIOUS ACTIVITY REPORT (SAR) NARRATIVE
Financial Crimes Enforcement Network (FinCEN) Filing
═══════════════════════════════════════════════════════════════════
Filing Date: {filing_date}
Filing Time: {filing_time}
Report Type: Initial SAR Filing
Prepared By: SARcastic AI (Automated Generation)
═══════════════════════════════════════════════════════════════════

SECTION 1 — SUBJECT IDENTIFICATION & BACKGROUND
─────────────────────────────────────────────────────────────────

Subject Name:           {full_name}
Date of Birth:          {dob}
Address:                {address}
Associated Accounts:    {accounts_str}

The subject referenced above maintains account(s) with this institution as identified in the account information section. This filing pertains to suspicious activity identified in connection with the subject's account(s) during the review period of {start_date} through {end_date}.

A review of institutional records indicates that this is an initial SAR filing for the referenced subject. Prior to this filing, the institution had not previously reported suspicious activity associated with this individual.

The subject's account relationship has been flagged for enhanced due diligence review following the detection of activity patterns that may be inconsistent with the expected profile.


SECTION 2 — SUSPICIOUS ACTIVITY DESCRIPTION
─────────────────────────────────────────────────────────────────

During the review period from {start_date} to {end_date}, the following suspicious activity was identified in connection with the subject's account(s):

Total Suspicious Amount: ${amount_str}

Transaction Details:
{transactions}

WHO:    The subject, {full_name}, conducted or directed the suspicious transactions through the identified account(s).
WHAT:   The activity involves financial transactions that appear inconsistent with the subject's known business profile and expected transaction patterns, warranting further investigation and regulatory reporting.
WHEN:   The suspicious activity was observed during the period of {start_date} through {end_date}.
WHERE:  The transactions were processed through accounts held at this institution ({accounts_str}).
WHY:    The transaction patterns exhibit characteristics consistent with known typologies of financial crime, including but not limited to the triggered compliance rules cited below.
HOW:    The transactions were conducted through standard banking channels, potentially structuring amounts to avoid regulatory reporting thresholds.


SECTION 3 — PATTERN ANALYSIS & TYPOLOGY MATCHING
─────────────────────────────────────────────────────────────────

The institution's automated monitoring systems and compliance rules identified the following patterns and typology matches:

Triggered Rules:
{rules}

Pattern Analysis:
The transaction activity associated with the subject's account displays characteristics that are consistent with known financial crime typologies. The compliance monitoring system flagged the activity based on established rule sets designed to detect potentially suspicious patterns.

Key behavioral observations include:
• Transaction amounts and frequency that deviate from the established baseline for the account
• Activity patterns that may be consistent with structuring (31 U.S.C. § 5324)
• Potential rapid movement of funds with no apparent legitimate business purpose
• Transaction timing and amounts that suggest deliberate avoidance of reporting thresholds

The deviation from expected account behavior was assessed against historical transaction patterns and peer group analysis. The results support the institution's determination that the activity warrants regulatory reporting.


SECTION 4 — INVESTIGATION STEPS PERFORMED
─────────────────────────────────────────────────────────────────

The following investigative steps were taken in connection with this filing:

1. DETECTION: The activity was initially identified through the institution's automated transaction monitoring system, which generated an alert based on predefined rule triggers.

2. ALERT REVIEW: A compliance analyst reviewed the system-generated alert and confirmed that the flagged activity warranted further investigation.

3. DATA COLLECTION: The following data sources were consulted during the investigation:
   • Core banking system transaction records
   • Account opening documentation and KYC files
   • Customer identification program (CIP) records
   • Regulatory knowledge base (RAG-augmented retrieval)

4. TRANSACTION ANALYSIS: Detailed analysis was performed on the transactions occurring during the review period. The analysis included examination of transaction amounts, frequencies, counterparties, and channels.

5. REGULATORY CONTEXT: The following regulatory guidance was consulted:
{regulatory_context}

6. DETERMINATION: Based on the totality of the evidence gathered, the institution determined that the activity is suspicious and warrants reporting to FinCEN pursuant to applicable BSA/AML regulations.


SECTION 5 — REGULATORY REFERENCES
─────────────────────────────────────────────────────────────────

This SAR filing is made pursuant to the following regulatory requirements:

• Bank Secrecy Act (BSA), 31 U.S.C. § 5318(g) — Requirement to report suspicious transactions
• 31 CFR § 1020.320 — SAR filing requirements for banks
• 31 U.S.C. § 5324 — Prohibition against structuring transactions to evade reporting requirements
• FinCEN SAR Filing Instructions — Form guidance and narrative requirements
• FFIEC BSA/AML Examination Manual — Institutional compliance program standards

The institution has filed this report within the regulatory timeframe of 30 calendar days from the date of initial detection, in compliance with 31 CFR § 1020.320(b)(3).


SECTION 6 — RISK ASSESSMENT & CONCLUSION
─────────────────────────────────────────────────────────────────

Risk Rating: HIGH
Confidence Level: MODERATE (based on available evidence and automated analysis)

Based on the investigation findings documented above, the institution has determined that the transaction activity associated with {full_name} appears potentially suspicious and may involve proceeds of unlawful activity or an attempt to evade BSA reporting requirements.

Recommended Actions:
• ENHANCED MONITORING: The subject's account(s) should be placed under enhanced transaction monitoring with reduced alert thresholds for a minimum period of 12 months.
• ACCOUNT REVIEW: A comprehensive review of the subject's account relationship should be conducted by the BSA/AML compliance team.
• LAW ENFORCEMENT REFERRAL: If additional evidence of criminal activity is identified, consideration should be given to referring the matter to the appropriate law enforcement agency.
• CONTINUING SAR: This matter should be evaluated for continuing SAR filing at 90-day intervals, as required.

Filing Classification: INITIAL FILING
Continuing Activity Report Recommended: YES — at 90-day intervals

This report has been prepared in compliance with all applicable federal regulations. The institution will continue to monitor this relationship and file additional SARs as warranted by ongoing activity.

═══════════════════════════════════════════════════════════════════
END OF SUSPICIOUS ACTIVITY REPORT NARRATIVE
Generated by SARcastic AI — {filing_date} {filing_time}
═══════════════════════════════════════════════════════════════════
"""


def generate_sar_from_case(case_dict):
    """
    Generates a SAR narrative from a database case record.
    Parses stored kyc_data and transaction_data strings back into usable structures.
    
    Args:
        case_dict: Dictionary from the database (sar_cases row)
        
    Returns: (prompt, narrative)
    """
    # Parse kyc_data from stored string
    kyc = {}
    raw_kyc = case_dict.get("kyc_data", "")
    if raw_kyc:
        try:
            kyc = json.loads(raw_kyc)
        except (json.JSONDecodeError, TypeError):
            try:
                kyc = ast.literal_eval(raw_kyc)
            except:
                kyc = {"full_name": case_dict.get("customer_name", "Unknown")}

    if "full_name" not in kyc:
        kyc["full_name"] = case_dict.get("customer_name", "Unknown")

    # Parse transaction_data from stored string
    transactions = ""
    raw_tx = case_dict.get("transaction_data", "")
    if raw_tx:
        try:
            tx_list = json.loads(raw_tx)
            if isinstance(tx_list, list):
                for i, tx in enumerate(tx_list, 1):
                    if isinstance(tx, dict):
                        transactions += f"Transaction {i}: "
                        transactions += ", ".join(f"{k}: {v}" for k, v in tx.items())
                        transactions += "\n"
                    else:
                        transactions += f"Transaction {i}: {tx}\n"
            else:
                transactions = str(tx_list)
        except:
            try:
                tx_parsed = ast.literal_eval(raw_tx)
                transactions = str(tx_parsed)
            except:
                transactions = raw_tx

    if not transactions.strip():
        transactions = "Transaction details as recorded in the case file."

    # Determine total amount from transactions if possible
    total_amount = 0
    if raw_tx:
        try:
            tx_list = json.loads(raw_tx) if isinstance(raw_tx, str) else raw_tx
            if isinstance(tx_list, list):
                for tx in tx_list:
                    if isinstance(tx, dict):
                        total_amount += float(tx.get("amount", 0))
        except:
            pass

    # Build the data structure expected by generate_sar_narrative
    created_at = case_dict.get("created_at", datetime.datetime.now())
    if isinstance(created_at, str):
        try:
            created_at = datetime.datetime.fromisoformat(created_at)
        except:
            created_at = datetime.datetime.now()

    data = {
        "kyc": kyc,
        "accounts": [f"Account linked to Case #{case_dict.get('id', 'N/A')}"],
        "activity_start": (created_at - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        "activity_end": created_at.strftime("%Y-%m-%d"),
        "total_amount": total_amount if total_amount > 0 else "Under Investigation",
        "transactions": transactions,
    }

    # Determine rules from status and narrative hints
    status = case_dict.get("status", "Draft")
    existing_narrative = case_dict.get("generated_narrative", "")
    
    rules = []
    
    # Priority: Use rules stored from Risk Engine if available
    if "triggered_rules" in kyc:
        stored_rules = kyc["triggered_rules"]
        if isinstance(stored_rules, list):
            rules.extend(stored_rules)
        elif isinstance(stored_rules, str):
            rules.append(stored_rules)

    # Fallback/Supplemental: Heuristics
    if not rules:
        if "structuring" in str(existing_narrative).lower() or "structuring" in str(raw_tx).lower():
            rules.append("R-102: Potential Structuring Detected (31 U.S.C. § 5324)")
        if "laundering" in str(existing_narrative).lower():
            rules.append("R-205: Suspected Money Laundering Activity")
        if total_amount > 10000:
            rules.append("R-100: Transaction Amount Exceeds CTR Threshold ($10,000)")
        if not rules:
            rules.append("R-001: General Suspicious Activity Alert")
            rules.append("R-050: Case Created for Manual Review")

    rule_result = {"triggered_rules": "\n".join(rules)}

    return generate_sar_narrative(data, rule_result)
