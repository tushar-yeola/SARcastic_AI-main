from sqlalchemy import text
from backend.database import engine

def save_audit_log(sar_id, rules_triggered, llm_prompt, llm_response):
    """
    Saves audit information into audit_logs table
    """
    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO audit_logs 
                (sar_id, rules_triggered, llm_prompt, llm_response)
                VALUES (:sar_id, :rules, :prompt, :response)
            """),
            {
                "sar_id": sar_id,
                "rules": str(rules_triggered),
                "prompt": llm_prompt,
                "response": llm_response
            }
        )

def get_audit_logs(limit=100):
    """
    Retrieves latest audit logs, joined with SAR case info if available.
    """
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT 
                    a.id, 
                    a.rules_triggered, 
                    a.created_at, 
                    a.llm_prompt, 
                    a.llm_response,
                    s.customer_name 
                FROM audit_logs a
                LEFT JOIN sar_cases s ON a.sar_id = s.id
                ORDER BY a.created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        return result.mappings().all()

def get_case_audit_history(sar_id):
    """
    Retrieves the full audit history for a specific case,
    formatted for the timeline view.
    """
    with engine.connect() as connection:
        # Get DB logs
        result = connection.execute(
            text("""
                SELECT 
                    created_at, 
                    rules_triggered,
                    llm_prompt
                FROM audit_logs 
                WHERE sar_id = :sar_id
                ORDER BY created_at DESC
            """),
            {"sar_id": sar_id}
        )
        db_logs = result.mappings().all()
        
        # Get Case Creation info for the 'Created' event
        case_result = connection.execute(
            text("SELECT created_at, status, analyst_id FROM sar_cases WHERE id = :sar_id"),
            {"sar_id": sar_id}
        )
        case_info = case_result.mappings().first()
        
        history = []
        
        # 1. Add Creation Event
        if case_info:
            history.append({
                "timestamp": case_info.created_at,
                "user": f"Analyst {case_info.analyst_id}",
                "action": "Case Created",
                "risk_version": "v1.0",
                "model_version": "N/A",
                "details": f"Initial Status: {case_info.status}"
            })

        # 2. Add System Logs
        for log in db_logs:
            history.append({
                "timestamp": log.created_at,
                "user": "System (SARcastic AI)",
                "action": "Risk Assessment & Narrative Generation",
                "risk_version": "v1.2",
                "model_version": "RegLLM-Pro-24b",
                "details": f"Rules: {log.rules_triggered[:50]}..."
            })
            
        # Sort by timestamp desc
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        return history

