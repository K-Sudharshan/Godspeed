import os
import sys
import json
import time
import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

BASE_URL = "http://127.0.0.1:8000"

def run_live_verification():
    print("=" * 65)
    print("AUDITTRAIL AP — LIVE REAL AI LAYER VERIFICATION")
    print("=" * 65)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)

    # ----------------------------------------------------------------------
    # 1. LIVE PRIMARY VERIFICATION (GROQ)
    # ----------------------------------------------------------------------
    print("\n[STEP 1] Ingesting FRESH invoice to test Primary AI (Groq)...")
    fresh_invoice_payload = {
        "vendor_name": "Apex Neural Technologies",
        "invoice_number": f"ANT-LIVE-{int(time.time())}",
        "invoice_date": "2026-10-08",
        "amount": 145000.0,
        "currency": "INR",
        "gstin": "27AAPCA1234F1Z5",
        "line_items": [
            {
                "description": "Enterprise AI Cluster Processing Core",
                "quantity": 1,
                "unit_price": 145000.0,
                "line_total": 145000.0
            }
        ]
    }

    resp = client.post("/api/invoices", json=fresh_invoice_payload)
    assert resp.status_code == 201, f"Failed to ingest invoice: {resp.text}"
    inv_data = resp.json()
    invoice_id = inv_data["id"]
    print(f" -> Invoice Created: ID={invoice_id}, Number={inv_data['invoice_number']}, Amount={inv_data['amount']}")

    # Fetch Risk Assessment
    resp_ass = client.get(f"/api/invoices/{invoice_id}/risk-assessment")
    assert resp_ass.status_code == 200, f"Failed to fetch risk assessment: {resp_ass.text}"
    assessment = resp_ass.json()
    print(f" -> Risk Assessment ID: {assessment['id']}")
    print(f" -> Deterministic Decision: {assessment['decision']} (Score: {assessment['final_score']}/100)")
    print(f" -> Decision Reason: {assessment['decision_reason']}")

    # Fetch AI Evaluation details
    ai_eval = assessment.get("ai_evaluation")
    assert ai_eval is not None, "AI evaluation was not linked to assessment"
    print("\n[AI EVALUATION DETAILS]")
    print(f" -> Evaluation ID: {ai_eval['id']}")
    print(f" -> Status: {ai_eval['status']}")
    print(f" -> Provider Used: {ai_eval.get('provider_used')}")
    print(f" -> Model: {ai_eval.get('model')}")
    print(f" -> Fallback Used: {ai_eval.get('fallback_used')}")
    print(f" -> Fallback Reason: {ai_eval.get('fallback_reason')}")
    print(f" -> Latency: {ai_eval.get('latency_ms')} ms")

    val_out = ai_eval.get("validated_output")
    if val_out:
        print(f" -> AI Risk Level: {val_out.get('risk_level')}")
        print(f" -> AI Confidence: {val_out.get('confidence')}")
        print(f" -> AI Recommended Decision: {val_out.get('recommended_decision')}")
        print(f" -> AI Reasoning Summary: {val_out.get('reasoning_summary')}")
        print(f" -> AI Next Action: {val_out.get('recommended_next_action')}")
        print(f" -> Grounded Factors Count: {len(val_out.get('risk_factors', []))}")
        for idx, f in enumerate(val_out.get("risk_factors", [])):
            print(f"    Factor #{idx+1}: [{f.get('category')} - {f.get('severity')}] {f.get('explanation')} (Sources: {f.get('source_ids')})")
    
    dropped = ai_eval.get("dropped_hallucinated_factors", [])
    print(f" -> Dropped Hallucinated Factors: {len(dropped)}")

    # ----------------------------------------------------------------------
    # 2. RE-ANALYSIS DYNAMIC VERIFICATION (SECTION 17)
    # ----------------------------------------------------------------------
    print("\n[STEP 2] Updating invoice amount (145,000 -> 285,000) and triggering re-analysis...")
    time.sleep(1.0)
    
    # Update invoice amount
    patch_resp = client.patch(f"/api/invoices/{invoice_id}", json={"amount": 285000.0})
    assert patch_resp.status_code == 200, f"Failed to patch invoice: {patch_resp.text}"
    print(" -> Invoice amount updated in DB to ₹2,85,000.00")

    # Call reanalyze
    reanalyze_resp = client.post(f"/api/invoices/{invoice_id}/reanalyze")
    assert reanalyze_resp.status_code == 200, f"Failed to reanalyze: {reanalyze_resp.text}"
    assessment_re = reanalyze_resp.json()
    print(f" -> New Assessment ID: {assessment_re['id']} (Previous: {assessment['id']})")
    print(f" -> New Decision: {assessment_re['decision']} (Score: {assessment_re['final_score']}/100)")

    # Fetch updated evaluation list
    evals_resp = client.get(f"/api/invoices/{invoice_id}/ai-evaluations")
    assert evals_resp.status_code == 200
    all_evals = evals_resp.json()
    print(f" -> Total Historical AI Evaluations: {len(all_evals)}")
    assert len(all_evals) >= 2, "Re-analysis did not create a new evaluation record"

    latest_eval = all_evals[0]
    first_eval = all_evals[-1]
    print(f" -> Latest AI Evaluation ID: {latest_eval['id']}")
    print(f" -> Latest AI Context Invoice Amount: ₹{latest_eval['request_context']['invoice']['amount']:,.2f}")
    print(f" -> First AI Context Invoice Amount: ₹{first_eval['request_context']['invoice']['amount']:,.2f}")
    assert latest_eval["request_context"]["invoice"]["amount"] == 285000.0
    assert first_eval["request_context"]["invoice"]["amount"] == 145000.0
    print(" -> Verification SUCCESS: Dynamic context reflected updated data; previous assessment preserved!")

    # ----------------------------------------------------------------------
    # 3. DIRECT TEST OF GROQ FAILURE -> GEMINI FALLBACK
    # ----------------------------------------------------------------------
    print("\n[STEP 3] Testing Groq Failure -> Gemini Fallback with real Gemini API...")
    from backend.app.modules.ai_service.evaluator import AIService
    from backend.app.modules.ai_service.providers import AIRiskProvider, GeminiRiskProvider
    from backend.app.config import settings

    class MockFailingProvider(AIRiskProvider):
        def __init__(self, err: str):
            self.err = err
        def evaluate(self, system_prompt: str, user_prompt: str, timeout_seconds: int = 15):
            raise TimeoutError(self.err)

    gemini_prov = GeminiRiskProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    fallback_service = AIService(
        groq_provider=MockFailingProvider("Simulated Groq 503 Provider Outage"),
        gemini_provider=gemini_prov
    )

    valid_source_ids = {invoice_id}
    ctx = latest_eval["request_context"]
    if ctx.get("invoice", {}).get("id"): valid_source_ids.add(str(ctx["invoice"]["id"]))
    if ctx.get("invoice", {}).get("invoice_number"): valid_source_ids.add(str(ctx["invoice"]["invoice_number"]))
    if ctx.get("vendor", {}).get("id"): valid_source_ids.add(str(ctx["vendor"]["id"]))
    for s in ctx.get("risk_signals", []):
        for sid in s.get("source_ids", []): valid_source_ids.add(str(sid))
    for d in ctx.get("duplicate_matches", []):
        if d.get("matched_invoice_id"): valid_source_ids.add(str(d["matched_invoice_id"]))
    for sg in ctx.get("split_invoice_groups", []):
        for sid in sg.get("invoice_ids", []): valid_source_ids.add(str(sid))

    fallback_eval = fallback_service.evaluate(
        context=ctx,
        untrusted_text="Enterprise AI Hardware Processing Core",
        valid_source_ids=valid_source_ids,
        invoice_id=invoice_id
    )

    print(f" -> Fallback Evaluation Status: {fallback_eval['status']}")
    print(f" -> Fallback Provider Used: {fallback_eval['provider_used']}")
    print(f" -> Fallback Flag: {fallback_eval['fallback_used']}")
    print(f" -> Fallback Reason: {fallback_eval['fallback_reason']}")
    print(f" -> Latency: {fallback_eval['latency_ms']} ms")
    assert fallback_eval["status"] == "SUCCESS", "Gemini fallback failed"
    assert fallback_eval["provider_used"] == "GEMINI", f"Expected GEMINI but got {fallback_eval['provider_used']}"
    assert fallback_eval["fallback_used"] is True
    assert "Simulated Groq 503" in fallback_eval["fallback_reason"]
    print(" -> Verification SUCCESS: Real Gemini API fallback succeeded when Groq failed!")

    # ----------------------------------------------------------------------
    # 4. DIRECT TEST OF BOTH PROVIDERS FAILING -> DETERMINISTIC ENGINE
    # ----------------------------------------------------------------------
    print("\n[STEP 4] Testing Both Providers Failing -> Pure Deterministic Decision...")
    both_failing_service = AIService(
        groq_provider=MockFailingProvider("Groq offline"),
        gemini_provider=MockFailingProvider("Gemini offline")
    )
    both_failed_eval = both_failing_service.evaluate(
        context=latest_eval["request_context"],
        untrusted_text="Supplies",
        valid_source_ids={invoice_id},
        invoice_id=invoice_id
    )
    print(f" -> Status: {both_failed_eval['status']}")
    print(f" -> Provider: {both_failed_eval['provider_used']}")
    print(f" -> Validated Output: {both_failed_eval['validated_output']}")
    print(f" -> Failure Reason: {both_failed_eval['failure_reason']}")
    assert both_failed_eval["status"] == "FAILED"
    assert both_failed_eval["provider_used"] == "NONE"
    assert both_failed_eval["validated_output"] is None
    print(" -> Verification SUCCESS: System degraded gracefully without crashing; zero fake AI!")

    print("\n" + "=" * 65)
    print("ALL LIVE VERIFICATION CHECKS PASSED WITH REAL EXTERNAL APIS!")
    print("=" * 65)

if __name__ == "__main__":
    run_live_verification()
