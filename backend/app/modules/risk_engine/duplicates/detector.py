from datetime import datetime, date
from typing import Dict, Any, List, Optional
import difflib

def calculate_text_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    return difflib.SequenceMatcher(None, s1.strip().lower(), s2.strip().lower()).ratio()

def detect_duplicates(current_invoice: Dict[str, Any], historical_invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Detects EXACT, NEAR, and SEMANTIC duplicates per PRD Section 17.
    Returns:
    - matches: list of duplicate match records
    - signals: list of risk signals
    - is_hard_block: True if exact match of a PAID invoice
    """
    matches = []
    signals = []
    is_hard_block = False

    curr_vendor_id = current_invoice.get("vendor_id")
    curr_number = str(current_invoice.get("invoice_number", "")).strip().upper()
    curr_amount = float(current_invoice.get("amount", 0.0))
    
    curr_date_str = current_invoice.get("invoice_date")
    curr_date = None
    if curr_date_str:
        curr_date = datetime.strptime(str(curr_date_str)[:10], "%Y-%m-%d").date()

    curr_desc = " ".join([item.get("description", "") for item in current_invoice.get("line_items", [])])

    for prev in historical_invoices:
        if prev["id"] == current_invoice.get("id"):
            continue
            
        # Must be same vendor
        if prev.get("vendor_id") != curr_vendor_id:
            continue

        prev_number = str(prev.get("invoice_number", "")).strip().upper()
        prev_amount = float(prev.get("amount", 0.0))
        prev_status = prev.get("status", "")
        
        prev_date_str = prev.get("invoice_date")
        prev_date = None
        if prev_date_str:
            prev_date = datetime.strptime(str(prev_date_str)[:10], "%Y-%m-%d").date()

        prev_desc = " ".join([item.get("description", "") for item in prev.get("line_items", [])])

        # 1. EXACT MATCH
        if curr_number == prev_number and abs(curr_amount - prev_amount) < 0.01:
            similarity = 1.0
            match_type = "EXACT"
            matched_fields = {"invoice_number": curr_number, "amount": curr_amount, "status": prev_status}
            matches.append({
                "invoice_id": current_invoice.get("id"),
                "matched_invoice_id": prev["id"],
                "match_type": match_type,
                "similarity_score": similarity,
                "matched_fields": matched_fields
            })

            if prev_status == "PAID":
                is_hard_block = True
                signals.append({
                    "category": "DUPLICATE",
                    "severity": "CRITICAL",
                    "score_contribution": 100.0,
                    "confidence": 1.0,
                    "source": "DUPLICATE_ENGINE",
                    "evidence": {
                        "matched_invoice_id": prev["id"],
                        "matched_invoice_number": prev_number,
                        "matched_status": "PAID",
                        "similarity": 1.0,
                        "reason": f"Exact duplicate of already-PAID invoice {prev_number}"
                    },
                    "source_ids": [prev["id"]]
                })
            else:
                signals.append({
                    "category": "DUPLICATE",
                    "severity": "HIGH",
                    "score_contribution": 70.0,
                    "confidence": 1.0,
                    "source": "DUPLICATE_ENGINE",
                    "evidence": {
                        "matched_invoice_id": prev["id"],
                        "matched_invoice_number": prev_number,
                        "similarity": 1.0,
                        "reason": f"Exact duplicate invoice number and amount with prior invoice {prev_number}"
                    },
                    "source_ids": [prev["id"]]
                })
            continue

        # 2. NEAR / SEMANTIC MATCH
        # Calculate field similarities per Section 17.2
        amount_score = 1.0 - min(1.0, abs(curr_amount - prev_amount) / max(curr_amount, prev_amount, 1.0))
        
        date_score = 1.0
        if curr_date and prev_date:
            days_diff = abs((curr_date - prev_date).days)
            date_score = max(0.0, 1.0 - (days_diff / 30.0))
        else:
            days_diff = 999

        desc_score = calculate_text_similarity(curr_desc, prev_desc)
        
        # Overall weighted similarity
        overall_similarity = (amount_score * 0.45) + (date_score * 0.25) + (desc_score * 0.30)
        
        if overall_similarity >= 0.90:
            match_type = "NEAR"
            matches.append({
                "invoice_id": current_invoice.get("id"),
                "matched_invoice_id": prev["id"],
                "match_type": match_type,
                "similarity_score": round(overall_similarity, 3),
                "matched_fields": {
                    "amount_score": round(amount_score, 2),
                    "days_diff": days_diff,
                    "desc_similarity": round(desc_score, 2)
                }
            })
            signals.append({
                "category": "DUPLICATE",
                "severity": "HIGH",
                "score_contribution": 60.0,
                "confidence": round(overall_similarity, 2),
                "source": "DUPLICATE_ENGINE",
                "evidence": {
                    "matched_invoice_id": prev["id"],
                    "matched_invoice_number": prev_number,
                    "similarity": round(overall_similarity, 3),
                    "reason": f"Near duplicate detected with invoice {prev_number} ({round(overall_similarity*100, 1)}% similarity)"
                },
                "source_ids": [prev["id"]]
            })
        elif overall_similarity >= 0.80:
            match_type = "SEMANTIC"
            matches.append({
                "invoice_id": current_invoice.get("id"),
                "matched_invoice_id": prev["id"],
                "match_type": match_type,
                "similarity_score": round(overall_similarity, 3),
                "matched_fields": {
                    "amount_score": round(amount_score, 2),
                    "desc_similarity": round(desc_score, 2)
                }
            })
            signals.append({
                "category": "DUPLICATE",
                "severity": "MEDIUM",
                "score_contribution": 35.0,
                "confidence": round(overall_similarity, 2),
                "source": "DUPLICATE_ENGINE",
                "evidence": {
                    "matched_invoice_id": prev["id"],
                    "matched_invoice_number": prev_number,
                    "similarity": round(overall_similarity, 3),
                    "reason": f"Semantic similarity match with invoice {prev_number}"
                },
                "source_ids": [prev["id"]]
            })

    return {
        "matches": matches,
        "signals": signals,
        "is_hard_block": is_hard_block
    }
