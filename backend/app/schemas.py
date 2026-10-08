from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date

# --- Ingestion & Invoice Schemas ---

class InvoiceLineItemInput(BaseModel):
    description: str
    quantity: Optional[float] = 1.0
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hsn_sac_code: Optional[str] = None

class InvoiceCreate(BaseModel):
    vendor_name: str
    invoice_number: str
    invoice_date: date
    amount: float
    currency: Optional[str] = "INR"
    taxable_value: Optional[float] = None
    tax_amount: Optional[float] = None
    tds_amount: Optional[float] = None
    gstin: Optional[str] = None
    po_id: Optional[str] = None
    irn: Optional[str] = None
    line_items: List[InvoiceLineItemInput] = []

class InvoiceLineItemResponse(BaseModel):
    id: str
    invoice_id: str
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    hsn_sac_code: Optional[str] = None

class InvoiceResponse(BaseModel):
    id: str
    invoice_number: str
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_match_status: Optional[str] = "MATCHED"
    invoice_date: Optional[date] = None
    currency: str = "INR"
    amount: float
    taxable_value: Optional[float] = None
    tax_amount: Optional[float] = None
    tds_amount: Optional[float] = None
    gstin_on_invoice: Optional[str] = None
    irn: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    line_items: List[InvoiceLineItemResponse] = []

# --- Vendor Schemas ---

class VendorCreate(BaseModel):
    name: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    tds_category: Optional[str] = "NOT_APPLICABLE"
    e_invoice_applicable: bool = False
    vendor_category: Optional[str] = None

class VendorBankAccountCreate(BaseModel):
    account_number: str
    ifsc: str
    source: Optional[str] = "MANUAL_ENTRY"

class VendorBankAccountResponse(BaseModel):
    id: str
    vendor_id: str
    account_number_masked: str
    ifsc: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    verified: bool = False
    source: str

class VendorTrustScoreResponse(BaseModel):
    id: str
    vendor_id: str
    score: float
    band: str
    evidence_level: str
    temporary_penalty: bool
    calculation_detail: Dict[str, Any]
    calculated_at: datetime
    is_current: bool

class VendorResponse(BaseModel):
    id: str
    name: str
    normalized_name: str
    gstin: Optional[str] = None
    pan: Optional[str] = None
    tds_category: str
    e_invoice_applicable: bool
    vendor_category: Optional[str] = None
    status: str
    created_at: datetime
    current_trust_score: Optional[VendorTrustScoreResponse] = None

# --- Risk Signals & Assessment Schemas ---

class RiskSignalResponse(BaseModel):
    id: str
    category: str
    severity: str
    score_contribution: float
    confidence: float
    source: str
    evidence: Dict[str, Any]
    status: str = "OPEN"

class DuplicateMatchResponse(BaseModel):
    id: str
    invoice_id: str
    matched_invoice_id: str
    match_type: str
    similarity_score: float
    matched_fields: Dict[str, Any]
    status: str
    detected_at: datetime

class SplitInvoiceGroupResponse(BaseModel):
    id: str
    vendor_id: str
    invoice_ids: List[str]
    cumulative_amount: float
    approval_threshold: float
    window_hours: int
    severity: str
    status: str
    explanation: str
    created_at: datetime

class ComplianceCheckResponse(BaseModel):
    id: str
    invoice_id: str
    check_type: str
    status: str
    verification_type: str
    detail: Dict[str, Any]
    checked_at: datetime

# --- AI Schema ---

class AIRiskFactor(BaseModel):
    category: Optional[str] = "GENERAL"
    severity: Optional[str] = "LOW"
    explanation: Optional[str] = ""
    source_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = 1.0

class AIEvaluationOutput(BaseModel):
    risk_level: Optional[str] = "MEDIUM"
    confidence: Optional[float] = 0.85
    recommended_decision: Optional[str] = "ESCALATE"
    risk_factors: List[AIRiskFactor] = Field(default_factory=list)
    reasoning_summary: Optional[str] = "Evaluation completed"
    recommended_next_action: Optional[str] = "Review evidence"
    risk_score: Optional[float] = None

class AIEvaluationResponse(BaseModel):
    id: str
    invoice_id: str
    status: str
    model_provider: Optional[str] = None
    model_version: Optional[str] = None
    provider_used: Optional[str] = None
    fallback_used: Optional[bool] = False
    fallback_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    validated_output: Optional[AIEvaluationOutput] = None
    dropped_hallucinated_factors: Optional[List[Dict[str, Any]]] = None
    failure_reason: Optional[str] = None

class RiskAssessmentResponse(BaseModel):
    id: str
    invoice_id: str
    final_score: float
    decision: str
    decision_reason: str
    forced_by_hard_rule: Optional[str] = None
    signals: List[RiskSignalResponse] = []
    ai_evaluation: Optional[AIEvaluationResponse] = None
    duplicates: List[DuplicateMatchResponse] = []
    split_group: Optional[SplitInvoiceGroupResponse] = None
    compliance_checks: List[ComplianceCheckResponse] = []
    created_at: datetime

# --- Investigation Schemas ---

class InvestigationCommentCreate(BaseModel):
    author_label: str = "AP_ANALYST"
    body: str

class InvestigationCommentResponse(BaseModel):
    id: str
    investigation_id: str
    author_label: str
    body: str
    created_at: datetime

class InvestigationCreate(BaseModel):
    invoice_id: str

class InvestigationResolveRequest(BaseModel):
    outcome: str
    rationale: str
    actor_label: str = "FINANCE_MANAGER"

class InvestigationResponse(BaseModel):
    id: str
    invoice_id: str
    risk_assessment_id: Optional[str] = None
    status: str
    assigned_role_label: Optional[str] = None
    outcome: Optional[str] = None
    outcome_rationale: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    comments: List[InvestigationCommentResponse] = []
    invoice: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    ai_evaluation: Optional[Dict[str, Any]] = None

class HumanOverrideRequest(BaseModel):
    new_decision: str
    reason: str
    actor_role_label: str = "SENIOR_APPROVER"

class ApprovalResponse(BaseModel):
    id: str
    invoice_id: str
    investigation_id: Optional[str] = None
    status: str
    approver_role_label: str
    previous_decision: str
    new_decision: str
    reason: str
    is_override: bool
    created_at: datetime

# --- Payment Runs Schemas ---

class PaymentRunCreate(BaseModel):
    name: str
    invoice_ids: List[str]
    created_by_label: str = "FINANCE_MANAGER"

class PaymentRunItemResponse(BaseModel):
    id: str
    payment_run_id: str
    invoice_id: str
    invoice_number: Optional[str] = None
    amount: Optional[float] = None
    snapshot_decision: str
    snapshot_risk_score: float
    ready: bool

class PaymentRunResponse(BaseModel):
    id: str
    name: str
    status: str
    total_value: float
    created_by_label: str
    created_at: datetime
    released_at: Optional[datetime] = None
    items: List[PaymentRunItemResponse] = []
    readiness_summary: Optional[Dict[str, Any]] = None

# --- Audit Events ---

class AuditEventResponse(BaseModel):
    sequence_number: int
    id: str
    event_type: str
    occurred_at: datetime
    invoice_id: Optional[str] = None
    vendor_id: Optional[str] = None
    payment_run_id: Optional[str] = None
    actor_label: str
    risk_score: Optional[float] = None
    decision: Optional[str] = None
    payload: Dict[str, Any]
    previous_hash: str
    current_hash: str
