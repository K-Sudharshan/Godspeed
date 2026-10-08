from typing import Dict, Any, List, Tuple

CATEGORY_WEIGHTS = {
    "DUPLICATE": 1.0,
    "SPLIT_INVOICE": 0.9,
    "BANK_CHANGE": 1.0,
    "COMPLIANCE": 0.7,
    "PRICING": 0.6,
    "VENDOR": 0.8,
    "DATA_QUALITY": 0.4,
    "AI_SYNTHESIS": 0.5
}

def aggregate_risk_score(
    signals: List[Dict[str, Any]],
    hard_block: bool = False,
    hard_escalate: bool = False,
    override_reasons: List[str] = None
) -> Tuple[float, str, str, str]:
    """
    Computes final risk score and deterministic decision per PRD Section 5.6 & 5.7:
    - 0–39   -> APPROVE
    - 40–74  -> ESCALATE
    - 75–100 -> BLOCK
    Returns: (final_score, decision, decision_reason, forced_by_hard_rule)
    """
    override_reasons = override_reasons or []
    
    if not signals:
        return 0.0, "APPROVE", "No risk signals triggered. Clean invoice.", None

    weighted_contrib_sum = 0.0
    weight_sum = 0.0
    critical_scores = []

    for s in signals:
        cat = s.get("category", "DATA_QUALITY")
        w = CATEGORY_WEIGHTS.get(cat, 0.5)
        conf = float(s.get("confidence", 1.0))
        contrib = float(s.get("score_contribution", 0.0))
        
        weighted_contrib_sum += (contrib * conf * w)
        weight_sum += w
        
        if s.get("severity") == "CRITICAL":
            critical_scores.append(contrib)

    base_score = weighted_contrib_sum / max(0.1, weight_sum)
    if critical_scores:
        final_score = max(max(critical_scores), base_score)
    else:
        final_score = base_score
        
    final_score = round(max(0.0, min(100.0, final_score)), 2)

    forced_rule = None
    if hard_block:
        decision = "BLOCK"
        forced_rule = "HARD_BLOCK"
        reason = f"HARD BLOCK: {'; '.join(override_reasons) if override_reasons else 'Critical risk rule violation'}"
    elif hard_escalate and final_score < 75.0:
        decision = "ESCALATE"
        forced_rule = "HARD_ESCALATE"
        reason = f"HARD ESCALATE: {'; '.join(override_reasons) if override_reasons else 'Mandatory review rule triggered'}"
    elif final_score >= 75.0:
        decision = "BLOCK"
        reason = f"High cumulative risk score ({final_score}/100) exceeded threshold of 75"
    elif final_score >= 40.0:
        decision = "ESCALATE"
        reason = f"Moderate cumulative risk score ({final_score}/100) requires human review"
    else:
        decision = "APPROVE"
        reason = f"Risk score ({final_score}/100) within acceptable policy limit (< 40)"

    return final_score, decision, reason, forced_rule
