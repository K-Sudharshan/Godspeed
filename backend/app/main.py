import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.database import db
from backend.app.schemas import (
    InvoiceCreate, InvoiceResponse,
    VendorCreate, VendorResponse, VendorBankAccountCreate, VendorBankAccountResponse,
    RiskAssessmentResponse,
    InvestigationCommentCreate, InvestigationCommentResponse,
    InvestigationResolveRequest, InvestigationResponse,
    HumanOverrideRequest, ApprovalResponse,
    PaymentRunCreate, PaymentRunResponse,
    AuditEventResponse
)
from backend.app.modules.risk_engine.firewall import run_risk_firewall

app = FastAPI(
    title="AuditTrail AP — Explainable, Real-Time Payment Integrity Platform",
    description="Pre-payment risk firewall combining deterministic rules, statistical analysis, duplicate/split pattern detection, dynamic vendor trust, and grounded AI reasoning.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Invoice Endpoints ---

@app.post("/api/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_and_analyze_invoice(invoice_in: InvoiceCreate, idempotency_key: Optional[str] = Header(None)):
    """
    Ingests a structured JSON invoice and immediately triggers the complete Risk Firewall pipeline.
    """
    # 1. Match or Create Vendor
    vendor = None
    if invoice_in.gstin:
        vendor = db.find_vendor_by_gstin(invoice_in.gstin)
    if not vendor and invoice_in.vendor_name:
        vendor = db.find_vendor_by_name(invoice_in.vendor_name)
    if not vendor:
        vendor = db.create_vendor({
            "name": invoice_in.vendor_name,
            "gstin": invoice_in.gstin,
            "status": "ACTIVE"
        })

    # 2. Persist Invoice
    inv_data = {
        "invoice_number": invoice_in.invoice_number,
        "vendor_id": vendor["id"],
        "vendor_match_status": "MATCHED",
        "po_id": invoice_in.po_id,
        "invoice_date": invoice_in.invoice_date.isoformat(),
        "currency": invoice_in.currency or "INR",
        "amount": invoice_in.amount,
        "taxable_value": invoice_in.taxable_value,
        "tax_amount": invoice_in.tax_amount,
        "tds_amount": invoice_in.tds_amount,
        "gstin_on_invoice": invoice_in.gstin,
        "irn": invoice_in.irn,
        "status": "INGESTED"
    }
    
    line_items = [it.model_dump() for it in invoice_in.line_items]
    saved_invoice = db.create_invoice(inv_data, line_items)
    
    # Audit ingestion
    db.record_audit_event(
        event_type="INVOICE_INGESTED",
        actor_label="AP_ANALYST",
        invoice_id=saved_invoice["id"],
        vendor_id=vendor["id"],
        payload={"invoice_number": invoice_in.invoice_number, "amount": invoice_in.amount}
    )

    # 3. Run Risk Firewall Pipeline
    run_risk_firewall(saved_invoice["id"], actor_label="AP_ANALYST")
    
    # Return updated invoice
    return db.get_invoice(saved_invoice["id"])

@app.get("/api/invoices", response_model=List[InvoiceResponse])
def list_invoices(status: Optional[str] = None):
    return db.get_all_invoices(status=status)

@app.get("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: str):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv

@app.patch("/api/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(invoice_id: str, updates: Dict[str, Any]):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    updated = db.update_invoice(invoice_id, updates)
    return updated

@app.get("/api/invoices/{invoice_id}/ai-evaluations")
def get_invoice_ai_evaluations(invoice_id: str):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db.get_ai_evaluations_for_invoice(invoice_id)

@app.post("/api/invoices/{invoice_id}/reanalyze")
def reanalyze_invoice(invoice_id: str):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return run_risk_firewall(invoice_id, actor_label="AP_ANALYST")

@app.get("/api/invoices/{invoice_id}/risk-assessment", response_model=RiskAssessmentResponse)
def get_invoice_risk_assessment(invoice_id: str):
    assessment = db.get_latest_assessment(invoice_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Risk assessment not found for invoice")
    return assessment

@app.post("/api/invoices/{invoice_id}/override", response_model=ApprovalResponse)
def override_invoice_decision(invoice_id: str, req: HumanOverrideRequest):
    """Human override of an ESCALATE or BLOCK decision."""
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
        
    assessment = db.get_latest_assessment(invoice_id)
    prev_decision = assessment["decision"] if assessment else inv["status"]
    
    # Record approval
    approval = db.record_approval(
        invoice_id=invoice_id,
        investigation_id=None,
        status="APPROVED" if req.new_decision == "APPROVE" else "REJECTED",
        approver_role_label=req.actor_role_label,
        previous_decision=prev_decision,
        new_decision=req.new_decision,
        reason=req.reason,
        is_override=True
    )
    
    db.update_invoice_status(invoice_id, req.new_decision)
    
    # Audit log
    db.record_audit_event(
        event_type="OVERRIDE_APPLIED",
        actor_label=req.actor_role_label,
        invoice_id=invoice_id,
        decision=req.new_decision,
        payload={
            "previous_decision": prev_decision,
            "new_decision": req.new_decision,
            "reason": req.reason,
            "approval_id": approval["id"]
        }
    )
    return approval

# --- Vendor Endpoints ---

@app.post("/api/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(vendor_in: VendorCreate):
    created = db.create_vendor(vendor_in.model_dump())
    # Initialize trust score = 50 per PRD
    db.save_vendor_trust_score(
        vendor_id=created["id"],
        score=50.0,
        band="NEW",
        evidence_level="NO_EVIDENCE",
        temporary_penalty=False,
        detail={"base_score": 50.0}
    )
    return db.get_vendor(created["id"])

@app.get("/api/vendors", response_model=List[VendorResponse])
def list_vendors():
    return db.get_all_vendors()

@app.get("/api/vendors/{vendor_id}", response_model=VendorResponse)
def get_vendor(vendor_id: str):
    v = db.get_vendor(vendor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return v

@app.post("/api/vendors/{vendor_id}/bank-accounts", response_model=VendorBankAccountResponse)
def add_vendor_bank_account(vendor_id: str, ba_in: VendorBankAccountCreate):
    v = db.get_vendor(vendor_id)
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    data = ba_in.model_dump()
    data["vendor_id"] = vendor_id
    res = db.create_vendor_bank_account(data)
    
    db.record_audit_event(
        event_type="BANK_ACCOUNT_ADDED",
        actor_label="AP_ANALYST",
        vendor_id=vendor_id,
        payload={"account_masked": res["account_number_masked"], "ifsc": res["ifsc"]}
    )
    return res

# --- Investigation Endpoints ---

@app.post("/api/investigations", response_model=InvestigationResponse)
def open_investigation(invoice_id: str):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    ass = db.get_latest_assessment(invoice_id)
    res = db.create_investigation(invoice_id, risk_assessment_id=ass["id"] if ass else None)
    return res

@app.get("/api/investigations/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: str):
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv

@app.post("/api/investigations/{investigation_id}/comments", response_model=InvestigationCommentResponse)
def add_investigation_comment(investigation_id: str, comment_in: InvestigationCommentCreate):
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    res = db.add_investigation_comment(investigation_id, comment_in.author_label, comment_in.body)
    
    db.record_audit_event(
        event_type="INVESTIGATION_COMMENT_ADDED",
        actor_label=comment_in.author_label,
        investigation_id=investigation_id,
        invoice_id=inv["invoice_id"],
        payload={"comment_id": res["id"], "body": comment_in.body}
    )
    return res

@app.post("/api/investigations/{investigation_id}/resolve", response_model=InvestigationResponse)
def resolve_investigation(investigation_id: str, resolve_in: InvestigationResolveRequest):
    inv = db.get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    res = db.resolve_investigation(investigation_id, resolve_in.outcome, resolve_in.rationale, resolve_in.actor_label)
    
    db.record_audit_event(
        event_type="INVESTIGATION_RESOLVED",
        actor_label=resolve_in.actor_label,
        investigation_id=investigation_id,
        invoice_id=inv["invoice_id"],
        payload={"outcome": resolve_in.outcome, "rationale": resolve_in.rationale}
    )
    return res

# --- Payment Runs Endpoints ---

@app.post("/api/payment-runs", response_model=PaymentRunResponse, status_code=status.HTTP_201_CREATED)
def create_payment_run(run_in: PaymentRunCreate):
    res = db.create_payment_run(run_in.name, run_in.invoice_ids, run_in.created_by_label)
    db.record_audit_event(
        event_type="PAYMENT_RUN_CREATED",
        actor_label=run_in.created_by_label,
        payment_run_id=res["id"],
        payload={"name": run_in.name, "total_value": res["total_value"], "items_count": len(run_in.invoice_ids)}
    )
    return res

@app.get("/api/payment-runs/{run_id}", response_model=PaymentRunResponse)
def get_payment_run(run_id: str):
    res = db.get_payment_run(run_id)
    if not res:
        raise HTTPException(status_code=404, detail="Payment run not found")
    return res

@app.post("/api/payment-runs/{run_id}/check-readiness")
def check_payment_run_readiness(run_id: str):
    return db.check_payment_run_readiness(run_id)

# --- Audit Endpoints ---

@app.get("/api/audit/events", response_model=List[AuditEventResponse])
def get_audit_events(invoice_id: Optional[str] = None, limit: int = 50):
    return db.get_audit_events(invoice_id=invoice_id, limit=limit)

@app.get("/api/audit/verify")
def verify_audit_chain():
    return db.verify_audit_chain()

# --- Health check ---
@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "AuditTrail AP", "version": "1.0.0"}

# Mount frontend if dist/static exists
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    @app.get("/")
    def serve_frontend_root():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "AuditTrail AP API is running. Visit /docs for OpenAPI documentation."}
else:
    @app.get("/")
    def root():
        return {"message": "AuditTrail AP API is running. Visit /docs for OpenAPI documentation."}
