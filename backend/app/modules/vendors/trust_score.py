import math
from datetime import datetime, timezone
from typing import Dict, Any, List

def calculate_vendor_trust(vendor: Dict[str, Any], historical_invoices: List[Dict[str, Any]], bank_accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes dynamic vendor trust score (0-100) per PRD Section 7.
    Default score for new vendor = 50.0.
    """
    invoice_count = len(historical_invoices)
    if invoice_count == 0:
        evidence_level = "NO_EVIDENCE"
    elif invoice_count < 5:
        evidence_level = "LIMITED"
    else:
        evidence_level = "SUFFICIENT"
        
    score = 50.0
    detail = {"base_score": 50.0}
    
    # Positive: clean invoices (0.3 per invoice, up to +15)
    clean_count = sum(1 for inv in historical_invoices if inv.get("status") in ("APPROVED", "PAID"))
    clean_bonus = min(15.0, clean_count * 0.3)
    if clean_bonus > 0:
        score += clean_bonus
        detail["clean_invoices_bonus"] = round(clean_bonus, 2)
        
    # Vendor age bonus
    if vendor.get("created_at"):
        try:
            created_dt = datetime.fromisoformat(vendor["created_at"].replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days
            age_bonus = min(10.0, (age_days / 30.0) * 0.5)
            if age_bonus > 0:
                score += age_bonus
                detail["vendor_age_bonus"] = round(age_bonus, 2)
        except Exception:
            pass

    # Bank account penalty: if any bank account added/changed recently and unverified
    has_temp_penalty = False
    for ba in bank_accounts:
        if not ba.get("verified"):
            try:
                eff_dt = datetime.fromisoformat(ba["effective_from"].replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - eff_dt).days
                if days_since <= 30:
                    score -= 20.0
                    has_temp_penalty = True
                    detail["unverified_bank_change_penalty"] = -20.0
                    break
            except Exception:
                pass

    # Clamping
    score = max(0.0, min(100.0, score))
    
    if score >= 90:
        band = "TRUSTED"
    elif score >= 70:
        band = "ESTABLISHED"
    elif score >= 45:
        band = "NEW"
    elif score >= 20:
        band = "DEVELOPING"
    else:
        band = "AT_RISK"
        
    return {
        "score": round(score, 2),
        "band": band,
        "evidence_level": evidence_level,
        "temporary_penalty": has_temp_penalty,
        "calculation_detail": detail
    }
