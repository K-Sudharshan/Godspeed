from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from backend.app.config import settings

def detect_split_invoices(current_invoice: Dict[str, Any], historical_invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detects split invoices / threshold evasion patterns per PRD Section 8.
    Default policy: 72-hour window, ₹5,00,000 threshold, minimum 2 invoices.
    """
    vendor_id = current_invoice.get("vendor_id")
    if not vendor_id:
        return {"split_group": None, "signals": [], "forces_escalate": False}

    threshold = settings.approval_threshold
    window_hours = settings.split_window_hours
    
    curr_date_str = current_invoice.get("invoice_date")
    if not curr_date_str:
        return {"split_group": None, "signals": [], "forces_escalate": False}
        
    try:
        curr_date = datetime.strptime(str(curr_date_str)[:10], "%Y-%m-%d").date()
    except Exception:
        return {"split_group": None, "signals": [], "forces_escalate": False}

    curr_amount = float(current_invoice.get("amount", 0.0))
    window_days = max(1, window_hours // 24)

    # Collect vendor invoices within window
    cluster_invoices = [current_invoice]
    for prev in historical_invoices:
        if prev.get("id") == current_invoice.get("id"):
            continue
        if prev.get("vendor_id") != vendor_id:
            continue
        if prev.get("status") in ("REJECTED", "CANCELLED"):
            continue
            
        prev_date_str = prev.get("invoice_date")
        if not prev_date_str:
            continue
        try:
            prev_date = datetime.strptime(str(prev_date_str)[:10], "%Y-%m-%d").date()
            if abs((curr_date - prev_date).days) <= window_days:
                cluster_invoices.append(prev)
        except Exception:
            continue

    if len(cluster_invoices) < 2:
        return {"split_group": None, "signals": [], "forces_escalate": False}

    cumulative_amount = sum(float(inv.get("amount", 0.0)) for inv in cluster_invoices)
    all_under_threshold = all(float(inv.get("amount", 0.0)) < threshold for inv in cluster_invoices)

    # Trigger conditions per PRD Section 8.3:
    # 1. Combined crosses threshold and each under threshold -> HIGH
    # 2. Cumulative >= 85% of threshold -> HIGH/MEDIUM
    is_split_detected = False
    severity = "MEDIUM"
    
    if all_under_threshold and cumulative_amount >= threshold:
        is_split_detected = True
        severity = "HIGH"
    elif all_under_threshold and cumulative_amount >= (0.85 * threshold):
        is_split_detected = True
        severity = "HIGH" if cumulative_amount >= (0.95 * threshold) else "MEDIUM"

    if not is_split_detected:
        return {"split_group": None, "signals": [], "forces_escalate": False}

    invoice_ids = [inv["id"] for inv in cluster_invoices if inv.get("id")]
    inv_numbers = [inv.get("invoice_number", "") for inv in cluster_invoices]
    
    explanation = (
        f"{len(cluster_invoices)} invoices from vendor totaling ₹{cumulative_amount:,.2f} "
        f"within {window_hours} hours ({', '.join(inv_numbers)}), each individually below the "
        f"₹{threshold:,.2f} approval threshold. Potential threshold evasion detected."
    )

    split_group_data = {
        "vendor_id": vendor_id,
        "invoice_ids": invoice_ids,
        "cumulative_amount": round(cumulative_amount, 2),
        "approval_threshold": threshold,
        "window_hours": window_hours,
        "severity": severity,
        "explanation": explanation
    }

    signal = {
        "category": "SPLIT_INVOICE",
        "severity": severity,
        "score_contribution": 55.0 if severity == "HIGH" else 35.0,
        "confidence": 0.90,
        "source": "SPLIT_ENGINE",
        "evidence": {
            "cumulative_amount": cumulative_amount,
            "threshold": threshold,
            "invoice_count": len(cluster_invoices),
            "invoice_numbers": inv_numbers,
            "window_hours": window_hours,
            "reason": explanation
        },
        "source_ids": invoice_ids
    }

    return {
        "split_group": split_group_data,
        "signals": [signal],
        "forces_escalate": True
    }
