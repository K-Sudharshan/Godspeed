-- ============================================================================
-- AuditTrail AP — Core Supabase PostgreSQL Schema & Security Safeguards
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 1. Vendors
CREATE TABLE IF NOT EXISTS vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    gstin TEXT UNIQUE,
    pan TEXT,
    tds_category TEXT CHECK (tds_category IN ('CONTRACTOR','PROFESSIONAL_SERVICES','RENT','COMMISSION','NOT_APPLICABLE')) DEFAULT 'NOT_APPLICABLE',
    e_invoice_applicable BOOLEAN DEFAULT false,
    vendor_category TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    first_invoice_date TIMESTAMPTZ,
    status TEXT CHECK (status IN ('ACTIVE','INACTIVE','UNDER_REVIEW')) DEFAULT 'ACTIVE'
);
CREATE INDEX IF NOT EXISTS idx_vendors_normalized_name_trgm ON vendors USING gin (normalized_name gin_trgm_ops);

-- 2. Vendor Bank Accounts
CREATE TABLE IF NOT EXISTS vendor_bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    account_number_masked TEXT NOT NULL,
    account_number_hash TEXT NOT NULL,
    ifsc TEXT NOT NULL,
    effective_from TIMESTAMPTZ DEFAULT now(),
    effective_to TIMESTAMPTZ,
    verified BOOLEAN DEFAULT false,
    source TEXT CHECK (source IN ('VENDOR_SUBMITTED','MANUAL_ENTRY','DOCUMENT_EXTRACTED')) DEFAULT 'MANUAL_ENTRY'
);
CREATE INDEX IF NOT EXISTS idx_vendor_bank_vendor_id ON vendor_bank_accounts(vendor_id);

-- 3. Vendor Trust Scores
CREATE TABLE IF NOT EXISTS vendor_trust_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    score NUMERIC(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    band TEXT NOT NULL CHECK (band IN ('AT_RISK','DEVELOPING','NEW','ESTABLISHED','TRUSTED')),
    evidence_level TEXT NOT NULL CHECK (evidence_level IN ('NO_EVIDENCE','LIMITED','SUFFICIENT')),
    temporary_penalty BOOLEAN DEFAULT false,
    calculation_detail JSONB DEFAULT '{}'::jsonb,
    calculated_at TIMESTAMPTZ DEFAULT now(),
    is_current BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_vendor_trust_vendor_id ON vendor_trust_scores(vendor_id);

-- 4. Invoices
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number TEXT NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    vendor_match_status TEXT CHECK (vendor_match_status IN ('MATCHED','PENDING_REVIEW','NEW_VENDOR')) DEFAULT 'NEW_VENDOR',
    po_id UUID,
    invoice_date DATE,
    currency TEXT DEFAULT 'INR',
    amount NUMERIC(18,2) NOT NULL,
    taxable_value NUMERIC(18,2),
    tax_amount NUMERIC(18,2),
    tds_amount NUMERIC(18,2),
    gstin_on_invoice TEXT,
    irn TEXT,
    status TEXT CHECK (status IN ('INGESTED','VALIDATED','UNDER_REVIEW','APPROVED','ESCALATED','BLOCKED','PAID','REJECTED','CANCELLED')) DEFAULT 'INGESTED',
    validation_errors JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_invoices_vendor_date ON invoices(vendor_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);

-- 5. Invoice Line Items
CREATE TABLE IF NOT EXISTS invoice_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    normalized_description TEXT,
    quantity NUMERIC(14,3),
    unit_price NUMERIC(18,4),
    line_total NUMERIC(18,2),
    hsn_sac_code TEXT
);
CREATE INDEX IF NOT EXISTS idx_line_items_invoice_id ON invoice_line_items(invoice_id);

-- 6. Risk Rules Config
CREATE TABLE IF NOT EXISTS risk_rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    rule_type TEXT CHECK (rule_type IN ('HARD_BLOCK','HARD_ESCALATE','SCORED')),
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    enabled BOOLEAN DEFAULT true,
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 7. AI Evaluations
CREATE TABLE IF NOT EXISTS ai_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    request_context JSONB NOT NULL,
    response_raw JSONB,
    response_validated JSONB,
    dropped_hallucinated_factors JSONB,
    status TEXT CHECK (status IN ('SUCCESS','FAILED','RATE_LIMITED','INVALID_SCHEMA')) NOT NULL,
    failure_reason TEXT,
    model_provider TEXT,
    model_version TEXT,
    latency_ms INT,
    token_usage JSONB,
    correlation_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 8. Risk Assessments
CREATE TABLE IF NOT EXISTS risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    previous_assessment_id UUID REFERENCES risk_assessments(id),
    final_score NUMERIC(5,2) NOT NULL CHECK (final_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL CHECK (decision IN ('APPROVE','ESCALATE','BLOCK')),
    decision_reason TEXT NOT NULL,
    forced_by_hard_rule TEXT,
    ai_evaluation_id UUID REFERENCES ai_evaluations(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    is_current BOOLEAN DEFAULT true
);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_invoice ON risk_assessments(invoice_id);

-- 9. Risk Signals
CREATE TABLE IF NOT EXISTS risk_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    risk_assessment_id UUID NOT NULL REFERENCES risk_assessments(id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('DUPLICATE','PRICING','VENDOR','COMPLIANCE','SPLIT_INVOICE','BANK_CHANGE','DATA_QUALITY','AI_SYNTHESIS')),
    severity TEXT NOT NULL CHECK (severity IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    score_contribution NUMERIC(5,2) NOT NULL,
    confidence NUMERIC(4,3) NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('RULE_ENGINE','STATISTICAL','DUPLICATE_ENGINE','SPLIT_ENGINE','AI')),
    evidence JSONB NOT NULL,
    status TEXT CHECK (status IN ('OPEN','FALSE_POSITIVE','CONFIRMED')) DEFAULT 'OPEN'
);
CREATE INDEX IF NOT EXISTS idx_risk_signals_assessment ON risk_signals(risk_assessment_id);

-- 10. Duplicate Matches
CREATE TABLE IF NOT EXISTS duplicate_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    matched_invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    match_type TEXT NOT NULL CHECK (match_type IN ('EXACT','NEAR','SEMANTIC','CROSS_PERIOD')),
    similarity_score NUMERIC(4,3) NOT NULL,
    matched_fields JSONB NOT NULL,
    status TEXT CHECK (status IN ('OPEN','CONFIRMED','FALSE_POSITIVE')) DEFAULT 'OPEN',
    detected_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT chk_diff_invoices CHECK (invoice_id != matched_invoice_id)
);

-- 11. Split Invoice Groups
CREATE TABLE IF NOT EXISTS split_invoice_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    invoice_ids UUID[] NOT NULL,
    cumulative_amount NUMERIC(18,2) NOT NULL,
    approval_threshold NUMERIC(18,2) NOT NULL,
    window_hours INT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT CHECK (status IN ('OPEN','REVIEWED','CONFIRMED','FALSE_POSITIVE')) DEFAULT 'OPEN',
    suppression_reason TEXT,
    explanation TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 12. Investigations
CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    risk_assessment_id UUID REFERENCES risk_assessments(id),
    split_invoice_group_id UUID REFERENCES split_invoice_groups(id),
    status TEXT CHECK (status IN ('OPEN','IN_REVIEW','WAITING_FOR_INFORMATION','RESOLVED','CLOSED')) DEFAULT 'OPEN',
    assigned_role_label TEXT DEFAULT 'FINANCE_MANAGER',
    outcome TEXT CHECK (outcome IN ('APPROVED_AFTER_REVIEW','BLOCKED','ESCALATED_FURTHER','FALSE_POSITIVE','AWAITING_VENDOR_CLARIFICATION','DUPLICATE_CONFIRMED','CONTRACT_AMENDMENT_VERIFIED','BANK_CHANGE_VERIFIED')),
    outcome_rationale TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

-- 13. Investigation Comments
CREATE TABLE IF NOT EXISTS investigation_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    author_label TEXT NOT NULL,
    body TEXT NOT NULL,
    mentioned_actor_labels TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 14. Approvals
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    investigation_id UUID REFERENCES investigations(id),
    status TEXT CHECK (status IN ('APPROVED','REJECTED')) NOT NULL,
    approver_role_label TEXT NOT NULL,
    previous_decision TEXT NOT NULL,
    new_decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    is_override BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 15. Payment Runs
CREATE TABLE IF NOT EXISTS payment_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    status TEXT CHECK (status IN ('DRAFT','ANALYZING','REVIEW_REQUIRED','READY_FOR_RELEASE','RELEASED','COMPLETED','FAILED')) DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ DEFAULT now(),
    released_at TIMESTAMPTZ,
    total_value NUMERIC(18,2) DEFAULT 0.00,
    created_by_label TEXT NOT NULL
);

-- 16. Payment Run Items
CREATE TABLE IF NOT EXISTS payment_run_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_run_id UUID NOT NULL REFERENCES payment_runs(id) ON DELETE CASCADE,
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    snapshot_decision TEXT NOT NULL,
    snapshot_risk_score NUMERIC(5,2) NOT NULL,
    ready BOOLEAN DEFAULT false,
    UNIQUE(payment_run_id, invoice_id)
);

-- 17. Compliance Checks
CREATE TABLE IF NOT EXISTS compliance_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    check_type TEXT CHECK (check_type IN ('GST','TDS','EINVOICE')) NOT NULL,
    status TEXT CHECK (status IN ('PASS','FAIL','EXCEPTION','MISSING','UNVERIFIED')) NOT NULL,
    verification_type TEXT CHECK (verification_type IN ('LOCAL_DETERMINISTIC','MOCK_EXTERNAL')) NOT NULL,
    detail JSONB NOT NULL,
    checked_at TIMESTAMPTZ DEFAULT now()
);

-- 18. Audit Events (Append-only Cryptographically Chained)
CREATE TABLE IF NOT EXISTS audit_events (
    sequence_number BIGSERIAL PRIMARY KEY,
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    invoice_id UUID REFERENCES invoices(id),
    vendor_id UUID REFERENCES vendors(id),
    payment_run_id UUID REFERENCES payment_runs(id),
    investigation_id UUID REFERENCES investigations(id),
    correlation_id UUID NOT NULL,
    actor_label TEXT NOT NULL,
    risk_score NUMERIC(5,2),
    confidence NUMERIC(4,3),
    decision TEXT,
    payload JSONB NOT NULL,
    previous_hash CHAR(64) NOT NULL,
    current_hash CHAR(64) NOT NULL
);

-- ============================================================================
-- DATABASE SAFEGUARDS & TRIGGERS
-- ============================================================================

-- A. Append-only safeguard on audit_events and investigation_comments
CREATE OR REPLACE FUNCTION fn_block_audit_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Table % is strictly append-only. UPDATE and DELETE are prohibited.', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_audit_mutation ON audit_events;
CREATE TRIGGER trg_block_audit_mutation
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION fn_block_audit_mutation();

DROP TRIGGER IF EXISTS trg_block_comment_mutation ON investigation_comments;
CREATE TRIGGER trg_block_comment_mutation
BEFORE UPDATE OR DELETE ON investigation_comments
FOR EACH ROW EXECUTE FUNCTION fn_block_audit_mutation();

-- B. Payment Release Guard
-- A BLOCKED invoice must NEVER become PAID without an approval override
CREATE OR REPLACE FUNCTION fn_guard_payment_release()
RETURNS TRIGGER AS $$
DECLARE
    v_latest_decision TEXT;
    v_approved_count INT;
BEGIN
    IF NEW.status = 'PAID' AND (OLD.status IS DISTINCT FROM 'PAID') THEN
        -- Check latest risk assessment
        SELECT decision INTO v_latest_decision
        FROM risk_assessments
        WHERE invoice_id = NEW.id AND is_current = true
        LIMIT 1;

        IF v_latest_decision = 'BLOCK' THEN
            -- Check if override approval exists
            SELECT COUNT(*) INTO v_approved_count
            FROM approvals
            WHERE invoice_id = NEW.id AND status = 'APPROVED' AND is_override = true;

            IF v_approved_count = 0 THEN
                RAISE EXCEPTION 'Database Guard: Invoice % has risk decision BLOCK and cannot be marked PAID without an approved override.', NEW.id;
            END IF;
        ELSIF v_latest_decision = 'ESCALATE' THEN
            SELECT COUNT(*) INTO v_approved_count
            FROM approvals
            WHERE invoice_id = NEW.id AND status = 'APPROVED';

            IF v_approved_count = 0 THEN
                RAISE EXCEPTION 'Database Guard: Invoice % has risk decision ESCALATE and requires approval before payment release.', NEW.id;
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_guard_payment_release ON invoices;
CREATE TRIGGER trg_guard_payment_release
BEFORE UPDATE ON invoices
FOR EACH ROW EXECUTE FUNCTION fn_guard_payment_release();
