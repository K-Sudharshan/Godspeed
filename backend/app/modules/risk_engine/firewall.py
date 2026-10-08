from typing import Dict, Any, List, Optional
from backend.app.database import db
from backend.app.modules.vendors.trust_score import calculate_vendor_trust
from backend.app.modules.compliance.gst import check_gst_compliance
from backend.app.modules.risk_engine.duplicates.detector import detect_duplicates
from backend.app.modules.risk_engine.split_invoice.detector import detect_split_invoices
from backend.app.modules.risk_engine.statistics.pricing import analyze_pricing_anomalies
from backend.app.modules.risk_engine.rules.deterministic import evaluate_deterministic_rules
from backend.app.modules.risk_engine.aggregator.scorer import aggregate_risk_score
from backend.app.modules.ai_service.evaluator import evaluate_with_ai

def run_risk_firewall(invoice_id: str, actor_label: str = "SYSTEM") -> Dict[str, Any]:
    """
    Executes the complete end-to-end Risk Firewall pipeline per PRD Section 5.4.
    """
    # 1. Fetch invoice
    invoice = db.get_invoice(invoice_id)
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} not found")

    vendor_id = invoice.get("vendor_id")
    if not vendor_id:
        # Try matching vendor by name or gstin
        vendor = None
        if invoice.get("gstin_on_invoice"):
            vendor = db.find_vendor_by_gstin(invoice["gstin_on_invoice"])
        if not vendor and invoice.get("vendor_name"):
            vendor = db.find_vendor_by_name(invoice["vendor_name"])
            
        if not vendor:
            # Create new vendor
            vname = invoice.get("vendor_name") or f"Vendor-{invoice['invoice_number']}"
            vendor = db.create_vendor({
                "name": vname,
                "gstin": invoice.get("gstin_on_invoice"),
                "status": "ACTIVE"
            })
            
        vendor_id = vendor["id"]
        # Update invoice with vendor
        conn = db._get_connection()
        conn.cursor().execute("UPDATE invoices SET vendor_id = ?, vendor_match_status = 'MATCHED' WHERE id = ?", (vendor_id, invoice_id))
        conn.commit()
        conn.close()
        invoice["vendor_id"] = vendor_id
    else:
        vendor = db.get_vendor(vendor_id)

    # 2. Historical context
    all_vendor_invoices = db.get_invoices_by_vendor(vendor_id)
    prior_invoices = [inv for inv in all_vendor_invoices if inv["id"] != invoice_id]
    
    bank_accounts = []
    conn = db._get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM vendor_bank_accounts WHERE vendor_id = ?", (vendor_id,))
    bank_accounts = [dict(r) for r in c.fetchall()]
    conn.close()

    # 3. Dynamic vendor trust recalculation
    trust_score_data = calculate_vendor_trust(vendor, prior_invoices, bank_accounts)
    db.save_vendor_trust_score(
        vendor_id=vendor_id,
        score=trust_score_data["score"],
        band=trust_score_data["band"],
        evidence_level=trust_score_data["evidence_level"],
        temporary_penalty=trust_score_data["temporary_penalty"],
        detail=trust_score_data["calculation_detail"]
    )

    all_signals = []
    hard_blocks = False
    hard_escalates = False
    override_reasons = []

    # 4. India GST & Compliance Checks
    gst_results = check_gst_compliance(invoice, vendor)
    for chk in gst_results["checks"]:
        db.record_compliance_check(
            invoice_id=invoice_id,
            check_type=chk["check_type"],
            status=chk["status"],
            verification_type=chk["verification_type"],
            detail=chk["detail"]
        )

    # 5. Duplicate Detection
    all_system_invoices = db.get_all_invoices()
    dup_results = detect_duplicates(invoice, all_system_invoices)
    for dm in dup_results["matches"]:
        db.record_duplicate_match(
            invoice_id=invoice_id,
            matched_invoice_id=dm["matched_invoice_id"],
            match_type=dm["match_type"],
            similarity_score=dm["similarity_score"],
            matched_fields=dm["matched_fields"]
        )
    all_signals.extend(dup_results["signals"])
    if dup_results["is_hard_block"]:
        hard_blocks = True
        override_reasons.append("Exact duplicate of an already PAID invoice")

    # 6. Split-Invoice Detection
    split_results = detect_split_invoices(invoice, prior_invoices)
    if split_results.get("split_group"):
        sg = split_results["split_group"]
        db.create_split_group(
            vendor_id=vendor_id,
            invoice_ids=sg["invoice_ids"],
            cumulative_amount=sg["cumulative_amount"],
            threshold=sg["approval_threshold"],
            window_hours=sg["window_hours"],
            severity=sg["severity"],
            explanation=sg["explanation"]
        )
    all_signals.extend(split_results["signals"])
    if split_results["forces_escalate"]:
        hard_escalates = True
        override_reasons.append("Split invoice cluster approaching/crossing approval threshold")

    # 7. Pricing Anomaly Analysis
    pricing_signals = analyze_pricing_anomalies(invoice, prior_invoices, trust_score_data["evidence_level"])
    all_signals.extend(pricing_signals)

    # 8. Deterministic Rules
    det_signals, det_block, det_escalate, det_reasons = evaluate_deterministic_rules(
        invoice, vendor, trust_score_data, bank_accounts, gst_results, prior_invoices_count=len(prior_invoices)
    )
    all_signals.extend(det_signals)
    if det_block:
        hard_blocks = True
    if det_escalate:
        hard_escalates = True
    override_reasons.extend(det_reasons)

    # 9. Real AI Explanation Layer
    valid_context_ids = [invoice_id, vendor_id]
    for s in all_signals:
        valid_context_ids.extend([str(x) for x in s.get("source_ids", [])])
        
    ai_record = evaluate_with_ai(
        invoice=invoice,
        vendor=vendor,
        trust_score=trust_score_data,
        signals=all_signals,
        valid_source_ids=valid_context_ids
    )
    ai_eval_id = db.record_ai_evaluation(ai_record)

    # 10. Aggregation
    final_score, decision, reason, forced_rule = aggregate_risk_score(
        signals=all_signals,
        hard_block=hard_blocks,
        hard_escalate=hard_escalates,
        override_reasons=override_reasons
    )

    # 11. Persist Risk Assessment
    assessment = db.save_risk_assessment({
        "invoice_id": invoice_id,
        "final_score": final_score,
        "decision": decision,
        "decision_reason": reason,
        "forced_by_hard_rule": forced_rule,
        "ai_evaluation_id": ai_eval_id
    }, all_signals)

    # 12. Auto-create investigation for ESCALATE or BLOCK
    inv_record = None
    if decision in ("ESCALATE", "BLOCK"):
        inv_record = db.create_investigation(
            invoice_id=invoice_id,
            risk_assessment_id=assessment["id"],
            split_group_id=assessment.get("split_group", {}).get("id") if assessment.get("split_group") else None
        )

    # 13. Audit Trail Event
    db.record_audit_event(
        event_type="DECISION_MADE",
        actor_label=actor_label,
        invoice_id=invoice_id,
        vendor_id=vendor_id,
        risk_score=final_score,
        decision=decision,
        payload={
            "signals_count": len(all_signals),
            "hard_block": hard_blocks,
            "hard_escalate": hard_escalates,
            "decision_reason": reason,
            "forced_by_hard_rule": forced_rule,
            "ai_evaluation_id": ai_eval_id,
            "investigation_opened": bool(inv_record)
        }
    )

    return assessment
