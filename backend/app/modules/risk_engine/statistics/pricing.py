from typing import Dict, Any, List
from backend.app.config import settings
import difflib

def analyze_pricing_anomalies(current_invoice: Dict[str, Any], historical_invoices: List[Dict[str, Any]], vendor_evidence_level: str) -> List[Dict[str, Any]]:
    """
    Evaluates unit price deviation per PRD Section 16.3 and Section 7.5.
    If vendor has insufficient history (< 5 invoices), suppresses anomaly claims.
    """
    signals = []
    curr_id = current_invoice.get("id")
    
    # Filter out current invoice from historical baseline
    true_historical = [inv for inv in historical_invoices if inv.get("id") != curr_id]

    # 1. Insufficient history rule
    if vendor_evidence_level in ("NO_EVIDENCE", "LIMITED") or len(true_historical) < 5:
        signals.append({
            "category": "DATA_QUALITY",
            "severity": "LOW",
            "score_contribution": 5.0,
            "confidence": 1.0,
            "source": "STATISTICAL",
            "evidence": {
                "message": "Insufficient price history to assess statistical deviation (fewer than 5 historical invoices)",
                "historical_invoice_count": len(true_historical)
            },
            "source_ids": [curr_id] if curr_id else []
        })
        return signals

    # 2. Build historical unit price dictionary per description
    historical_prices: Dict[str, List[float]] = {}
    for inv in true_historical:
        for item in inv.get("line_items", []):
            desc = item.get("description", "").strip().lower()
            u_price = item.get("unit_price")
            if desc and u_price and float(u_price) > 0:
                historical_prices.setdefault(desc, []).append(float(u_price))

    # 3. Check current line items
    current_items = current_invoice.get("line_items", [])
    for item in current_items:
        desc = item.get("description", "").strip().lower()
        curr_price = item.get("unit_price")
        if not desc or not curr_price or float(curr_price) <= 0:
            continue
            
        curr_price = float(curr_price)
        
        # Match with historical prices
        matched_desc = None
        if desc in historical_prices:
            matched_desc = desc
        else:
            # Fuzzy match
            for h_desc in historical_prices.keys():
                if difflib.SequenceMatcher(None, desc, h_desc).ratio() >= 0.80:
                    matched_desc = h_desc
                    break

        if matched_desc and historical_prices[matched_desc]:
            prices = historical_prices[matched_desc]
            avg_price = sum(prices) / len(prices)
            
            if avg_price > 0:
                deviation_pct = (curr_price - avg_price) / avg_price
                
                if deviation_pct >= settings.price_deviation_high_threshold: # >= 40%
                    signals.append({
                        "category": "PRICING",
                        "severity": "HIGH",
                        "score_contribution": 50.0,
                        "confidence": 0.95,
                        "source": "STATISTICAL",
                        "evidence": {
                            "item": item.get("description"),
                            "current_unit_price": curr_price,
                            "historical_avg_price": round(avg_price, 2),
                            "deviation_percentage": round(deviation_pct * 100, 1),
                            "historical_sample_size": len(prices),
                            "reason": f"Unit price of '{item.get('description')}' is {round(deviation_pct * 100, 1)}% above vendor historical average (₹{curr_price:,.2f} vs ₹{avg_price:,.2f})"
                        },
                        "source_ids": [curr_id] if curr_id else []
                    })
                elif deviation_pct >= settings.price_deviation_medium_threshold: # >= 25%
                    signals.append({
                        "category": "PRICING",
                        "severity": "MEDIUM",
                        "score_contribution": 25.0,
                        "confidence": 0.90,
                        "source": "STATISTICAL",
                        "evidence": {
                            "item": item.get("description"),
                            "current_unit_price": curr_price,
                            "historical_avg_price": round(avg_price, 2),
                            "deviation_percentage": round(deviation_pct * 100, 1),
                            "historical_sample_size": len(prices),
                            "reason": f"Unit price of '{item.get('description')}' is {round(deviation_pct * 100, 1)}% above vendor historical average"
                        },
                        "source_ids": [curr_id] if curr_id else []
                    })

    return signals
