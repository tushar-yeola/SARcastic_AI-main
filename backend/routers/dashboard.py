from fastapi import APIRouter, Depends
from backend.services.sar_service import get_dashboard_metrics, generate_regulatory_report
from backend.services.audit_service import get_audit_logs
from backend.vectorstore.chroma_store import retrieve_relevant_docs
from backend.core.deps import get_current_user
from backend.models.auth_models import UserLogin
from pydantic import BaseModel

class RAGQuery(BaseModel):
    query: str

router = APIRouter()

@router.get("/metrics")
def read_metrics(current_user: UserLogin = Depends(get_current_user)):
    return get_dashboard_metrics()

@router.get("/report")
def get_report(current_user: UserLogin = Depends(get_current_user)):
    report_text = generate_regulatory_report()
    return {"report": report_text}

@router.get("/audit-logs")
def read_audit_logs(limit: int = 50, current_user = Depends(get_current_user)):
    logs = get_audit_logs(limit=limit)
    return logs

@router.post("/explain")
def explain_query(query: RAGQuery, current_user = Depends(get_current_user)):
    docs = retrieve_relevant_docs(query.query)
    return {"docs": docs}

