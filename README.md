# AuditTrail AP — Explainable, Real-Time Payment Integrity Platform

AuditTrail AP is a pre-payment integrity platform that intercepts accounts payable (AP) invoices and payment runs **before money moves**, executing real-time explainable risk evaluations to prevent duplicate payments, threshold evasion, vendor bank-detail fraud, pricing anomalies, and compliance violations.

---

## ⚡ Live Features Implemented (P0 Hackathon Working Demo)

1. **Pre-Payment Risk Firewall:**
   - Ingests structured JSON invoices via `POST /api/invoices`.
   - Sequences normalization $\rightarrow$ vendor matching $\rightarrow$ vendor trust $\rightarrow$ GST compliance $\rightarrow$ duplicate detection $\rightarrow$ split-invoice clustering $\rightarrow$ pricing anomalies $\rightarrow$ deterministic rules $\rightarrow$ AI explanation $\rightarrow$ risk aggregation.
   - Deterministic decisions: **`APPROVE`** (0–39), **`ESCALATE`** (40–74), **`BLOCK`** (75–100).
2. **Duplicate Detection Engine:**
   - Exact match against already-PAID invoice forces hard **`BLOCK`**.
   - Near and semantic duplicate detection based on vendor, amount tolerance ($\pm 1\%$), date window ($\pm 3$ days), and description similarity.
3. **Split-Invoice / Threshold Evasion Detection:**
   - Evaluates rolling 72-hour window clusters for the same vendor approaching or crossing the ₹5,00,000 policy threshold.
   - Forces minimum **`ESCALATE`** using non-accusatory terminology.
4. **Historical Pricing Anomaly Detection:**
   - Calculates percentage deviation against historical unit prices ($>25\%$ MEDIUM, $>40\%$ HIGH).
   - Enforces insufficient-history suppression when vendor has $< 5$ historical invoices.
5. **India AP & GST Compliance:**
   - Local deterministic validation: GSTIN format and Mod-36 checksum verification.
   - Invoice GSTIN vs. Vendor Master GSTIN consistency and tax arithmetic checks.
6. **Dynamic Vendor Trust Scoring (0–100):**
   - New vendors start at 50 (`NEW` band).
   - Recalculates dynamically with positive invoice history bonuses and penalties for unverified bank changes (-20 temporary) and duplicate incidents (-15).
7. **Explainable AI Layer & Grounding Filter:**
   - Real LLM integration (Gemini / OpenAI / Groq) with prompt injection defense (`<<<UNTRUSTED_DATA_START>>> ... <<<UNTRUSTED_DATA_END>>>`).
   - Anti-hallucination grounding filter strictly verifies all `source_ids`.
   - Graceful fallback: System produces full deterministic decisions even if AI is offline.
8. **Collaborative Investigation Workspace:**
   - Auto-creates investigation records for `ESCALATE` and `BLOCK` outcomes.
   - Append-only comments and outcome resolutions (`APPROVED_AFTER_REVIEW`, `BLOCKED`, `DUPLICATE_CONFIRMED`).
   - Senior Approver human overrides with required justification audit trail.
9. **Payment Run Release Safeguards:**
   - Assembles invoice batches and calculates release readiness.
   - **Database-Level Guard:** Hard-excludes `BLOCK` invoices from reaching `PAID` without an approved override.
10. **Cryptographic SHA-256 Audit Trail:**
    - Append-only, hash-chained event log recording sequence numbers, previous hash, and current hash.
    - Live verification endpoint `/api/audit/verify` that mathematically proves chain integrity or flags tampering.

---

## 🚀 Quickstart & Local Execution

### 1. Prerequisites
- Python 3.11+
- Virtual environment or system Python

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Seed Realistic Demo Scenarios
Run the live pipeline to populate the 8 PRD benchmark scenarios:
```bash
python supabase/seed/seed_data.py
```

### 4. Start the Application
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
- Open the **UI Dashboard**: [http://localhost:8000](http://localhost:8000)
- Interactive **OpenAPI / Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Automated Test Suite

Run the automated pytest suite verifying all 12 core acceptance criteria:
```bash
python -m pytest tests/test_audit_trail_ap.py
```
**Test Cases Covered:**
- Clean invoice $\rightarrow$ `APPROVE`
- Paid duplicate $\rightarrow$ `BLOCK` (Hard Rule)
- Split invoice cluster $\rightarrow$ `ESCALATE`
- Recent bank-detail change $\rightarrow$ `ESCALATE`
- Pricing anomaly $+50\%$ $\rightarrow$ `PRICING` HIGH signal
- Invalid GSTIN checksum $\rightarrow$ `ESCALATE`
- New vendor initialization $\rightarrow$ Trust score 50
- AI fallback $\rightarrow$ Deterministic continuation
- Grounding filter $\rightarrow$ Unsupported source IDs discarded
- Payment guard $\rightarrow$ Direct release of `BLOCK` invoice rejected
- Human override $\rightarrow$ Logged with audit trail
- Audit hash chain integrity $\rightarrow$ Verifies valid chain & detects tampering

---

## 🌐 Supabase Integration

The database layer supports dual-mode operation:
1. **Local / Testing:** Runs on transactional SQLite (`godspeed.db`) with full relational constraints and SHA-256 hash chaining.
2. **Supabase PostgreSQL:**
   - Copy `.env.example` to `.env` and fill in:
     ```env
     SUPABASE_URL=https://your-project.supabase.co
     SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
     ```
   - Execute the complete schema and triggers in the Supabase SQL Editor:
     `supabase/migrations/001_initial_schema.sql`

---

## 🐳 Docker & Cloud Deployment

### Docker
```bash
docker build -t audittrail-ap .
docker run -p 8000:8000 audittrail-ap
```

### Render Deployment
This repository includes a native `render.yaml` blueprint. Link your repository on [Render](https://render.com) for automated continuous deployment.
