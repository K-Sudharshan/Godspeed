from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from backend.app.config import settings

def evaluate_deterministic_rules(
    invoice: Dict[str, Any],
    vendor: Dict[str, Any],
    trust_score: Dict[str, Any],
    bank_accounts: List[Dict[str, Any]],
    gst_results: Dict[str, Any],
    prior_invoices_count: int = 0
) -> Tuple[List[Dict[str, Any]], bool, bool, List[str]]:
    """
    Evaluates deterministic business rules per PRD Section 5.7 and Section 16.
    Returns:
    - signals: list of risk signals
    - forces_block: bool
    - forces_escalate: bool
    - override_reasons: list of strings
    """
    signals = []
    forces_block = False
    forces_escalate = False
    override_reasons = []

    # 1. Missing mandatory fields check
    mandatory_fields = ["invoice_number", "amount", "invoice_date"]
    missing = [f for f in mandatory_fields if invoice.get(f) is None or str(invoice.get(f)).strip() == ""]
    if missing:
        forces_block = True
        reason = f"Missing mandatory invoice fields: {', '.join(missing)} — cannot evaluate risk"
        override_reasons.append(reason)
        signals.append({
            "category": "DATA_QUALITY",
            "severity": "CRITICAL",
            "score_contribution": 100.0,
            "confidence": 1.0,
            "source": "RULE_ENGINE",
            "evidence": {"missing_fields": missing, "reason": reason},
            "source_ids": [invoice.get("id")] if invoice.get("id") else []
        })
        return signals, forces_block, forces_escalate, override_reasons

    # 2. GST Compliance failure
    if gst_results.get("status") == "FAIL":
        forces_escalate = True
        reasons = gst_results.get("failure_reasons", ["GST compliance check failed"])
        override_reasons.extend(reasons)
        for r in reasons:
            signals.append({
                "category": "COMPLIANCE",
                "severity": "HIGH",
                "score_contribution": 45.0,
                "confidence": 1.0,
                "source": "RULE_ENGINE",
                "evidence": {"reason": r},
                "source_ids": [invoice.get("id")] if invoice.get("id") else []
            })

    # 3. Bank-detail change within lookback window
    for ba in bank_accounts:
        if not ba.get("verified"):
            try:
                eff_dt = datetime.fromisoformat(ba["effective_from"].replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - eff_dt).days
                if days_since <= settings.bank_change_lookback_days:
                    forces_escalate = True
                    reason = f"Vendor bank account changed {days_since} days ago and is unverified (within {settings.bank_change_lookback_days}-day lookback window)"
                    override_reasons.append(reason)
                    signals.append({
                        "category": "BANK_CHANGE",
                        "severity": "HIGH",
                        "score_contribution": 60.0,
                        "confidence": 1.0,
                        "source": "RULE_ENGINE",
                        "evidence": {
                            "bank_account_id": ba.get("id"),
                            "account_masked": ba.get("account_number_masked"),
                            "days_since_change": days_since,
                            "reason": reason
                        },
                        "source_ids": [ba.get("id")] if ba.get("id") else []
                    })
                    break
            except Exception:
                pass

    # 4. New vendor with high-value first invoice (PRD Section 7.3: first invoice > ₹1,00,000 forces ESCALATE)
    inv_amount = float(invoice.get("amount", 0.0))
    if prior_invoices_count == 0 and inv_amount > 100000.0:
        forces_escalate = True
        reason = f"First invoice from NEW vendor exceeding policy threshold of ₹1,00,000 (Amount: ₹{inv_amount:,.2f})"
        override_reasons.append(reason)
        signals.append({
            "category": "VENDOR",
            "severity": "MEDIUM",
            "score_contribution": 40.0,
            "confidence": 0.95,
            "source": "RULE_ENGINE",
            "evidence": {
                "vendor_name": vendor.get("name"),
                "vendor_band": "NEW",
                "amount": inv_amount,
                "reason": reason
            },
            "source_ids": [vendor.get("id")] if vendor.get("id") else []
        })

    # 5. Vendor Trust Risk
    score = trust_score.get("score", 50.0)
    if score < 20.0:
        if inv_amount > 50000.0:
            forces_escalate = True
            reason = f"Vendor is AT_RISK (trust score {score}/100) with high invoice amount ₹{inv_amount:,.2f}"
            override_reasons.append(reason)
        signals.append({
            "category": "VENDOR",
            "severity": "HIGH",
            "score_contribution": 50.0,
            "confidence": 0.90,
            "source": "RULE_ENGINE",
            "evidence": {"trust_score": score, "band": "AT_RISK", "reason": f"Vendor has low trust score: {score}/100"},
            "source_ids": [vendor.get("id")] if vendor.get("id") else []
        })

    return signals, forces_block, forces_escalate, override_reasons
