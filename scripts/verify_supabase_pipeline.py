import os
import sys
import uuid
import json
import httpx
from datetime import datetime, timezone

from backend.app.config import settings
from supabase import create_client

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    print("=" * 70)
    print(" AUDITTRAIL AP — SUPABASE LIVE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Supabase connection succeeds
    print("\n[Step 1] Verifying Supabase connection...")
    assert settings.supabase_url, "SUPABASE_URL is not configured"
    assert settings.supabase_service_role_key, "SUPABASE_SERVICE_ROLE_KEY is not configured"
    
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    print(f"  [PASS] Successfully connected to Supabase endpoint: {settings.supabase_url}")

    # 2 & 3. Existing migrations/schema and required tables exist
    print("\n[Step 2 & 3] Verifying schema and required tables exist...")
    required_tables = [
        "vendors",
        "vendor_bank_accounts",
        "vendor_trust_scores",
        "invoices",
        "invoice_line_items",
        "ai_evaluations",
        "risk_assessments",
        "risk_signals",
        "investigations",
        "audit_events"
    ]
    for tbl in required_tables:
        res = client.table(tbl).select("*").limit(1).execute()
        print(f"  [PASS] Table '{tbl}' verified in Supabase PostgreSQL schema (rows: {len(res.data)})")

    # 4. Backend mode verification (FastAPI health endpoint)
    print("\n[Step 4] Verifying Python backend database mode...")
    health_resp = httpx.get(f"{BASE_URL}/api/health", timeout=10.0)
    assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
    health_data = health_resp.json()
    print(f"  Health status: {health_data}")
    assert health_data.get("database_mode") == "SUPABASE", f"Expected mode SUPABASE, got {health_data.get('database_mode')}"
    print("  [PASS] Backend is actively configured and operating in SUPABASE mode.")

    # 5. Ingest a fresh invoice through Python backend API
    unique_suffix = str(uuid.uuid4())[:8]
    inv_number = f"INV-SUPA-{unique_suffix}"
    gstin = "27AAACG0561D1ZW" # Valid GSTIN structure
    vendor_name = f"Apex Tech Solutions {unique_suffix}"
    
    print(f"\n[Step 5] Ingesting fresh invoice via backend API: {inv_number}...")
    invoice_payload = {
        "invoice_number": inv_number,
        "vendor_name": vendor_name,
        "gstin": gstin,
        "invoice_date": datetime.now(timezone.utc).date().isoformat(),
        "currency": "INR",
        "amount": 285000.0,
        "taxable_value": 241525.42,
        "tax_amount": 43474.58,
        "tds_amount": 0.0,
        "line_items": [
            {
                "description": "High-Throughput Enterprise API Gateway Licenses",
                "quantity": 2,
                "unit_price": 120762.71,
                "line_total": 241525.42,
                "hsn_sac_code": "998313"
            }
        ]
    }
    
    post_resp = httpx.post(f"{BASE_URL}/api/invoices", json=invoice_payload, timeout=45.0)
    assert post_resp.status_code == 201, f"Invoice creation failed: {post_resp.text}"
    created_invoice = post_resp.json()
    invoice_id = created_invoice["id"]
    print(f"  [PASS] Fresh invoice created via API! ID: {invoice_id}, Status: {created_invoice['status']}")

    # 6. Verify directly in Supabase: Invoices and Line Items
    print("\n[Step 6] Direct Supabase verification: Invoice and Line Items...")
    supa_inv = client.table("invoices").select("*").eq("id", invoice_id).execute()
    assert len(supa_inv.data) == 1, f"Invoice {invoice_id} not found in Supabase invoices table!"
    inv_row = supa_inv.data[0]
    assert inv_row["invoice_number"] == inv_number
    assert float(inv_row["amount"]) == 285000.0
    print(f"  [PASS] Invoice verified directly in Supabase table 'invoices':")
    print(f"         ID: {inv_row['id']}")
    print(f"         Invoice Number: {inv_row['invoice_number']}")
    print(f"         Amount: {inv_row['amount']} {inv_row['currency']}")
    print(f"         Status: {inv_row['status']}")

    supa_li = client.table("invoice_line_items").select("*").eq("invoice_id", invoice_id).execute()
    assert len(supa_li.data) >= 1, "Line items missing in Supabase!"
    print(f"  [PASS] {len(supa_li.data)} line item(s) verified directly in Supabase table 'invoice_line_items'")

    # 7. Verify directly in Supabase: Risk Assessment & Signals
    print("\n[Step 7] Direct Supabase verification: Risk Assessment and Signals...")
    supa_ass = client.table("risk_assessments").select("*").eq("invoice_id", invoice_id).eq("is_current", True).execute()
    assert len(supa_ass.data) == 1, f"Risk assessment not found in Supabase for invoice {invoice_id}"
    assessment_1 = supa_ass.data[0]
    assessment_1_id = assessment_1["id"]
    print(f"  [PASS] Risk assessment verified directly in Supabase table 'risk_assessments':")
    print(f"         ID: {assessment_1_id}")
    print(f"         Decision: {assessment_1['decision']}")
    print(f"         Score: {assessment_1['final_score']}")
    print(f"         Reason: {assessment_1['decision_reason']}")
    print(f"         Is Current: {assessment_1['is_current']}")

    supa_sig = client.table("risk_signals").select("*").eq("risk_assessment_id", assessment_1_id).execute()
    assert len(supa_sig.data) > 0, "Risk signals missing in Supabase!"
    print(f"  [PASS] {len(supa_sig.data)} risk signal(s) verified directly in Supabase table 'risk_signals':")
    for sig in supa_sig.data[:3]:
        print(f"         - [{sig['severity']}] {sig['category']} ({sig['source']}): contribution={sig['score_contribution']}")

    # 8. Verify directly in Supabase: AI Evaluation
    print("\n[Step 8] Direct Supabase verification: AI Evaluation...")
    ai_eval_id = assessment_1.get("ai_evaluation_id")
    assert ai_eval_id, "Assessment does not link to an ai_evaluation_id!"
    supa_ai = client.table("ai_evaluations").select("*").eq("id", ai_eval_id).execute()
    assert len(supa_ai.data) == 1, f"AI evaluation {ai_eval_id} missing in Supabase!"
    ai_row_1 = supa_ai.data[0]
    print(f"  [PASS] AI evaluation verified directly in Supabase table 'ai_evaluations':")
    print(f"         ID: {ai_row_1['id']}")
    print(f"         Status: {ai_row_1['status']}")
    print(f"         Provider: {ai_row_1.get('model_provider')}")
    print(f"         Model: {ai_row_1.get('model_version')}")
    print(f"         Latency: {ai_row_1.get('latency_ms')}ms")
    print(f"         Correlation ID: {ai_row_1.get('correlation_id')}")

    # 9. Verify re-analysis creates a new assessment and evaluation in Supabase
    print(f"\n[Step 9] Triggering re-analysis on invoice {invoice_id} via API...")
    reanalyze_resp = httpx.post(f"{BASE_URL}/api/invoices/{invoice_id}/reanalyze", timeout=45.0)
    assert reanalyze_resp.status_code == 200, f"Reanalyze failed: {reanalyze_resp.text}"
    reanalyzed_data = reanalyze_resp.json()
    new_assessment_id = reanalyzed_data["id"]
    print(f"  [PASS] Re-analysis completed! New assessment ID: {new_assessment_id}")

    print("  Direct Supabase verification of re-analysis records:")
    # Fetch all assessments for this invoice
    all_ass = client.table("risk_assessments").select("*").eq("invoice_id", invoice_id).order("created_at", desc=True).execute()
    assert len(all_ass.data) >= 2, f"Expected at least 2 assessments in Supabase, found {len(all_ass.data)}"
    
    current_ass = [a for a in all_ass.data if a["is_current"]]
    superseded_ass = [a for a in all_ass.data if not a["is_current"]]
    assert len(current_ass) == 1, "Expected exactly 1 current assessment!"
    assert current_ass[0]["id"] == new_assessment_id, "New assessment is not the current one!"
    assert current_ass[0]["previous_assessment_id"] == assessment_1_id, "New assessment not linked to prior assessment!"
    print(f"  [PASS] Verified in Supabase: Assessment history chain intact:")
    print(f"         New Assessment ID (Current=True): {current_ass[0]['id']}")
    print(f"         Prior Assessment ID (Current=False): {superseded_ass[0]['id']}")
    print(f"         Linked via previous_assessment_id: {current_ass[0]['previous_assessment_id']}")

    # Verify AI evaluation for re-analysis
    new_ai_id = current_ass[0].get("ai_evaluation_id")
    assert new_ai_id, "New assessment missing ai_evaluation_id!"
    assert new_ai_id != ai_eval_id, "Re-analysis did not create a new AI evaluation!"
    supa_ai_2 = client.table("ai_evaluations").select("*").eq("id", new_ai_id).execute()
    assert len(supa_ai_2.data) == 1, "New AI evaluation missing in Supabase!"
    print(f"  [PASS] Verified in Supabase: New AI evaluation created ({new_ai_id}) for re-analysis.")

    # 10. Verify application uses Supabase rather than local SQLite store
    print("\n[Step 10] Verifying isolation from local SQLite...")
    import sqlite3
    db_file = os.path.join(os.path.dirname(__file__), "..", "godspeed.db")
    if os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM invoices WHERE id = ?", (invoice_id,))
        count = c.fetchone()[0]
        conn.close()
        assert count == 0, f"Invoice {invoice_id} unexpectedly found in local SQLite database! Expected 0, found {count}"
        print(f"  [PASS] Verified: Invoice {invoice_id} is NOT present in local SQLite godspeed.db (count={count}).")
        print("         The application is strictly writing to and reading from Supabase PostgreSQL!")
    else:
        print("  [PASS] Local SQLite database file does not even exist, strictly running on Supabase.")

    # 11. Verify Audit Events in Supabase
    print("\n[Step 11] Verifying audit events in Supabase...")
    supa_audit = client.table("audit_events").select("*").eq("invoice_id", invoice_id).execute()
    assert len(supa_audit.data) > 0, "No audit events found for invoice in Supabase!"
    print(f"  [PASS] Verified {len(supa_audit.data)} audit event(s) in Supabase table 'audit_events'")
    for ev in supa_audit.data:
        print(f"         - Seq {ev['sequence_number']}: {ev['event_type']} by {ev['actor_label']} (hash={ev['current_hash'][:16]}...)")

    print("\n" + "=" * 70)
    print(" ALL 9 VERIFICATION POINTS PASSED DIRECTLY AGAINST SUPABASE!")
    print("=" * 70)

if __name__ == "__main__":
    run_verification()
