from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import traceback

from backend.services import sar_service, audit_service
from backend.core.deps import get_current_user
from backend.llm.narrative_generator import generate_sar_from_case

router = APIRouter()

class CaseBase(BaseModel):
    customer_name: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    created_at: Optional[datetime] = None
    analyst_id: Optional[int] = None
    generated_narrative: Optional[str] = None
    kyc_data: Optional[str] = None
    transaction_data: Optional[str] = None
    edited_narrative: Optional[str] = None

class CaseCreate(BaseModel):
    customer_name: str
    kyc_data: dict
    transaction_data: List[dict]

class CaseResponse(CaseBase):
    id: int

    class Config:
        from_attributes = True

class NarrativeResponse(BaseModel):
    case_id: int
    narrative: str
    prompt: str
    status: str

@router.get("/", response_model=List[CaseResponse])
def read_cases(limit: int = 100, current_user = Depends(get_current_user)):
    cases = sar_service.get_all_cases(limit=limit)
    return cases

@router.get("/{case_id}", response_model=CaseResponse)
def read_case(case_id: int, current_user = Depends(get_current_user)):
    case = sar_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@router.post("/", response_model=CaseResponse)
def create_case(case_in: CaseCreate, current_user = Depends(get_current_user)):
    analyst_id = current_user.id if hasattr(current_user, 'id') else 1

    data = {
        "kyc": {"full_name": case_in.customer_name, **case_in.kyc_data},
        "transactions": case_in.transaction_data
    }

    new_id = sar_service.create_sar_case(analyst_id, data, "Pending Generation...")

    # Audit
    audit_service.save_audit_log(new_id, "Rule Engine", "Case Auto-Created", "Status: Draft")

    return sar_service.get_case_by_id(new_id)

@router.post("/{case_id}/generate_narrative", response_model=NarrativeResponse)
def generate_narrative(case_id: int, current_user = Depends(get_current_user)):
    """
    Generates a detailed Suspicious Activity Report (SAR) narrative for the given case.
    Uses the LLM (Ollama) with RAG context from the vector store.
    Updates the case record with the generated narrative.
    """
    case = sar_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    try:
        # Generate SAR narrative via LLM
        prompt, narrative = generate_sar_from_case(case)

        # Update the case with the generated narrative
        sar_service.update_generated_narrative(case_id, narrative)

        # Audit the generation event
        audit_service.save_audit_log(
            case_id,
            "LLM SAR Generation",
            prompt[:500],  # Store first 500 chars of prompt
            narrative[:500]  # Store first 500 chars of response
        )

        return NarrativeResponse(
            case_id=case_id,
            narrative=narrative,
            prompt=prompt,
            status="generated"
        )

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"SAR Generation Error for case {case_id}: {error_detail}")
        
        # Audit the failure
        audit_service.save_audit_log(
            case_id,
            "LLM SAR Generation Failed",
            "Generation attempted",
            str(e)[:500]
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"SAR narrative generation failed: {str(e)}"
        )

@router.put("/{case_id}/approve")
def approve_case(case_id: int, current_user = Depends(get_current_user)):
    role = getattr(current_user, 'role', 'Analyst')
    if role not in ['Reviewer', 'MLRO', 'Compliance Head']:
        raise HTTPException(status_code=403, detail="Not authorized")

    sar_service.approve_sar(case_id)
    audit_service.save_audit_log(case_id, "Manual Review", "User Approved SAR", "Status: Approved")
    return {"status": "approved"}

@router.get("/{case_id}/audit")
def get_case_audit(case_id: int, current_user = Depends(get_current_user)):
    return audit_service.get_case_audit_history(case_id)

@router.get("/{case_id}/details")
def get_case_details(case_id: int, current_user = Depends(get_current_user)):
    return sar_service.get_sar_details_full(case_id)

class SARSectionUpdate(BaseModel):
    section: str
    # data can be dict or list depending on section (e.g. part_d is list, part_a is dict)
    # Using Any or relaxed validation
    data: object

@router.put("/{case_id}/details")
def update_case_details(case_id: int, update: SARSectionUpdate, current_user = Depends(get_current_user)):
    sar_service.update_sar_section(case_id, update.section, update.data)
    return {"status": "success"}

@router.post("/import-csv")
def import_csv(file: UploadFile = File(...), current_user = Depends(get_current_user)):
    user_id = current_user.id if hasattr(current_user, 'id') else 1
    try:
        content = file.file.read()
        result = sar_service.process_csv_upload(content, file.filename, user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"CSV Import Critical Error: {error_detail}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
