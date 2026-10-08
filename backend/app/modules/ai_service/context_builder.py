from typing import Dict, Any, List, Set, Tuple, Optional

def build_ai_context(
    invoice: Dict[str, Any],
    vendor: Dict[str, Any],
    trust_score: Dict[str, Any],
    signals: List[Dict[str, Any]],
    duplicate_matches: Optional[List[Dict[str, Any]]] = None,
    split_groups: Optional[List[Dict[str, Any]]] = None,
    pricing_signals: Optional[List[Dict[str, Any]]] = None,
    compliance_checks: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Dict[str, Any], str, Set[str]]:
    """
    Dynamically constructs structured context from current database state per Section 6.
    Returns:
        (structured_context_dict, untrusted_invoice_text, valid_source_ids)
    """
    duplicate_matches = duplicate_matches or []
    split_groups = split_groups or []
    pricing_signals = pricing_signals or []
    compliance_checks = compliance_checks or []

    # 1. Structured Invoice Data
    clean_line_items = []
    untrusted_parts = []
    valid_source_ids: Set[str] = set()

    inv_id = str(invoice.get("id", ""))
    inv_num = str(invoice.get("invoice_number", ""))
    if inv_id:
        valid_source_ids.add(inv_id)
    if inv_num:
        valid_source_ids.add(inv_num)

    for idx, item in enumerate(invoice.get("line_items", [])):
        desc = str(item.get("description", ""))
        item_id = str(item.get("id") or f"ITEM-{idx+1}")
        valid_source_ids.add(item_id)
        if desc:
            untrusted_parts.append(desc)
        clean_line_items.append({
            "id": item_id,
            "description": desc,
            "quantity": item.get("quantity"),
            "unit_price": item.get("unit_price"),
            "line_total": item.get("line_total")
        })

    structured_invoice = {
        "id": inv_id,
        "invoice_number": inv_num,
        "vendor_id": str(invoice.get("vendor_id", "")),
        "vendor_name": str(invoice.get("vendor_name", vendor.get("name", ""))),
        "amount": invoice.get("amount"),
        "currency": invoice.get("currency", "INR"),
        "invoice_date": str(invoice.get("invoice_date", "")),
        "line_items": clean_line_items
    }

    # 2. Vendor Context (Sensitive data like full bank accounts is never sent)
    vendor_id = str(vendor.get("id", ""))
    if vendor_id:
        valid_source_ids.add(vendor_id)

    vendor_calc = trust_score.get("calculation_detail", {})
    structured_vendor = {
        "id": vendor_id,
        "name": vendor.get("name"),
        "trust_score": trust_score.get("score"),
        "trust_band": trust_score.get("band"),
        "evidence_level": trust_score.get("evidence_level"),
        "invoice_count_12m": vendor_calc.get("invoice_count_12m", 0),
        "last_bank_change_days_ago": vendor_calc.get("bank_change_days_ago", None),
        "temporary_penalty": trust_score.get("temporary_penalty", False)
    }

    # 3. Risk Signals
    structured_signals = []
    for s in signals:
        s_id = str(s.get("id", ""))
        if s_id:
            valid_source_ids.add(s_id)
        s_sources = [str(sid) for sid in s.get("source_ids", [])]
        for sid in s_sources:
            valid_source_ids.add(sid)
        structured_signals.append({
            "id": s_id,
            "category": s.get("category"),
            "severity": s.get("severity"),
            "score_contribution": s.get("score_contribution"),
            "source": s.get("source"),
            "evidence": s.get("evidence"),
            "source_ids": s_sources
        })

    # 4. Duplicate Matches
    structured_duplicates = []
    for dm in duplicate_matches:
        dm_id = str(dm.get("id", ""))
        if dm_id:
            valid_source_ids.add(dm_id)
        matched_id = str(dm.get("matched_invoice_id", ""))
        if matched_id:
            valid_source_ids.add(matched_id)
        structured_duplicates.append({
            "matched_invoice_id": matched_id,
            "match_type": dm.get("match_type"),
            "similarity_score": dm.get("similarity_score"),
            "matched_fields": dm.get("matched_fields")
        })

    # 5. Split Invoice Groups
    structured_splits = []
    for sg in split_groups:
        sg_id = str(sg.get("id", ""))
        if sg_id:
            valid_source_ids.add(sg_id)
        sg_inv_ids = [str(x) for x in sg.get("invoice_ids", [])]
        for sid in sg_inv_ids:
            valid_source_ids.add(sid)
        structured_splits.append({
            "id": sg_id,
            "invoice_ids": sg_inv_ids,
            "cumulative_amount": sg.get("cumulative_amount"),
            "threshold": sg.get("approval_threshold"),
            "window_hours": sg.get("window_hours"),
            "severity": sg.get("severity"),
            "explanation": sg.get("explanation")
        })

    # 6. Pricing Signals
    structured_pricing = []
    for ps in pricing_signals:
        for sid in ps.get("source_ids", []):
            valid_source_ids.add(str(sid))
        structured_pricing.append({
            "category": ps.get("category"),
            "severity": ps.get("severity"),
            "evidence": ps.get("evidence"),
            "source_ids": [str(x) for x in ps.get("source_ids", [])]
        })

    # 7. Compliance Checks
    structured_compliance = []
    for cc in compliance_checks:
        cc_id = str(cc.get("id", ""))
        if cc_id:
            valid_source_ids.add(cc_id)
        structured_compliance.append({
            "check_type": cc.get("check_type"),
            "status": cc.get("status"),
            "verification_type": cc.get("verification_type"),
            "detail": cc.get("detail")
        })

    context = {
        "invoice": structured_invoice,
        "vendor": structured_vendor,
        "risk_signals": structured_signals,
        "duplicate_matches": structured_duplicates,
        "split_invoice_groups": structured_splits,
        "pricing_signals": structured_pricing,
        "compliance_checks": structured_compliance
    }

    untrusted_text = " ".join(untrusted_parts) if untrusted_parts else "No line item descriptions provided."
    return context, untrusted_text, valid_source_ids
