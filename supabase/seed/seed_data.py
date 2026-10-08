import os
import sys

# Ensure UTF-8 console output for Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure python path includes project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from datetime import datetime, timezone, timedelta
from backend.app.database import db, DB_FILE
from backend.app.modules.risk_engine.firewall import run_risk_firewall

def run_seed():
    print("==================================================")
    print("SEEDING AUDITTRAIL AP DEMO DATA VIA REAL PIPELINE")
    print("==================================================")

    # 1. Clean Established Vendor (TechLogix Solutions)
    # Valid GSTIN: 27AAAAA0000A1Z5
    v_clean = db.create_vendor({
        "name": "TechLogix Solutions Pvt Ltd",
        "gstin": "27AAAAA0000A1Z5",
        "status": "ACTIVE"
    })
    # Add historical clean invoices so vendor has SUFFICIENT evidence level & established trust
    base_date = datetime.now(timezone.utc).date() - timedelta(days=60)
    for i in range(1, 7):
        hist_inv = db.create_invoice({
            "invoice_number": f"TL-HIST-00{i}",
            "vendor_id": v_clean["id"],
            "vendor_match_status": "MATCHED",
            "invoice_date": (base_date + timedelta(days=i*5)).isoformat(),
            "currency": "INR",
            "amount": 75000.0,
            "status": "PAID",
            "gstin_on_invoice": "27AAAAA0000A1Z5"
        }, [
            {"description": "IT Support & Cloud Services", "quantity": 1, "unit_price": 75000.0, "line_total": 75000.0}
        ])
    # Recalculate trust
    db.save_vendor_trust_score(v_clean["id"], 85.0, "ESTABLISHED", "SUFFICIENT", False, {"clean_invoices": 6})

    # SCENARIO A: Clean Invoice -> APPROVE
    print("\n[Scenario A] Clean invoice for established vendor...")
    inv_a = db.create_invoice({
        "invoice_number": "TL-2026-101",
        "vendor_id": v_clean["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": datetime.now(timezone.utc).date().isoformat(),
        "amount": 75000.0,
        "taxable_value": 63559.32,
        "tax_amount": 11440.68,
        "gstin_on_invoice": "27AAAAA0000A1Z5"
    }, [
        {"description": "IT Support & Cloud Services", "quantity": 1, "unit_price": 75000.0, "line_total": 75000.0}
    ])
    res_a = run_risk_firewall(inv_a["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_a['decision']} (Score: {res_a['final_score']}) | Reason: {res_a['decision_reason']}")

    # SCENARIO B: Exact Duplicate of PAID invoice -> BLOCK (Hard Rule)
    print("\n[Scenario B] Exact duplicate of already-paid invoice...")
    inv_b = db.create_invoice({
        "invoice_number": "TL-HIST-001",
        "vendor_id": v_clean["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": datetime.now(timezone.utc).date().isoformat(),
        "amount": 75000.0,
        "gstin_on_invoice": "27AAAAA0000A1Z5"
    }, [
        {"description": "IT Support & Cloud Services", "quantity": 1, "unit_price": 75000.0, "line_total": 75000.0}
    ])
    res_b = run_risk_firewall(inv_b["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_b['decision']} (Score: {res_b['final_score']}) | Reason: {res_b['decision_reason']}")

    # SCENARIO C: Recent unverified bank-detail change -> ESCALATE
    print("\n[Scenario C] Vendor bank account changed recently...")
    v_bank_test = db.create_vendor({
        "name": "Apex Facilities Management",
        "gstin": "29BBBBB1111B1Z2",
        "status": "ACTIVE"
    })
    # Add unverified bank account updated today
    db.create_vendor_bank_account({
        "vendor_id": v_bank_test["id"],
        "account_number": "987654321098",
        "ifsc": "HDFC0001234",
        "verified": False
    })
    inv_c = db.create_invoice({
        "invoice_number": "AFM-8890",
        "vendor_id": v_bank_test["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": datetime.now(timezone.utc).date().isoformat(),
        "amount": 125000.0,
        "gstin_on_invoice": "29BBBBB1111B1Z2"
    }, [
        {"description": "Facility Sanitization & Janitorial", "quantity": 1, "unit_price": 125000.0, "line_total": 125000.0}
    ])
    res_c = run_risk_firewall(inv_c["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_c['decision']} (Score: {res_c['final_score']}) | Reason: {res_c['decision_reason']}")

    # SCENARIO D: High unit price anomaly (> 40% deviation) -> ESCALATE
    print("\n[Scenario D] Abnormally high unit price (+50% deviation)...")
    v_pricing = db.create_vendor({
        "name": "Urban Office Furniture Ltd",
        "gstin": "07CCCCC2222C1Z9",
        "status": "ACTIVE"
    })
    # Seed 5 historical invoices with unit price ₹5,000 for Office Chairs
    for i in range(1, 6):
        db.create_invoice({
            "invoice_number": f"UOF-HIST-{i}",
            "vendor_id": v_pricing["id"],
            "vendor_match_status": "MATCHED",
            "invoice_date": (base_date + timedelta(days=i*4)).isoformat(),
            "amount": 50000.0,
            "status": "PAID"
        }, [
            {"description": "Ergonomic Office Chair", "quantity": 10, "unit_price": 5000.0, "line_total": 50000.0}
        ])
    db.save_vendor_trust_score(v_pricing["id"], 75.0, "ESTABLISHED", "SUFFICIENT", False, {})
    
    # New invoice unit price ₹7,500 (50% increase!)
    inv_d = db.create_invoice({
        "invoice_number": "UOF-2026-904",
        "vendor_id": v_pricing["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": datetime.now(timezone.utc).date().isoformat(),
        "amount": 75000.0
    }, [
        {"description": "Ergonomic Office Chair", "quantity": 10, "unit_price": 7500.0, "line_total": 75000.0}
    ])
    res_d = run_risk_firewall(inv_d["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_d['decision']} (Score: {res_d['final_score']}) | Reason: {res_d['decision_reason']}")

    # SCENARIO E: Split Invoices (₹1.6L + ₹1.7L + ₹1.5L = ₹4.8L within 24h near ₹5L threshold) -> ESCALATE
    print("\n[Scenario E] Split invoice cluster approaching approval threshold...")
    v_split = db.create_vendor({
        "name": "Global Hardware Distro",
        "gstin": "33DDDDD3333D1Z6",
        "status": "ACTIVE"
    })
    now_d = datetime.now(timezone.utc).date()
    db.create_invoice({
        "invoice_number": "GHD-101", "vendor_id": v_split["id"],
        "vendor_match_status": "MATCHED", "invoice_date": now_d.isoformat(), "amount": 160000.0
    }, [{"description": "Server Racks & Cables", "quantity": 1, "unit_price": 160000.0, "line_total": 160000.0}])
    db.create_invoice({
        "invoice_number": "GHD-102", "vendor_id": v_split["id"],
        "vendor_match_status": "MATCHED", "invoice_date": now_d.isoformat(), "amount": 170000.0
    }, [{"description": "Server Racks & Cables Part 2", "quantity": 1, "unit_price": 170000.0, "line_total": 170000.0}])
    inv_e3 = db.create_invoice({
        "invoice_number": "GHD-103", "vendor_id": v_split["id"],
        "vendor_match_status": "MATCHED", "invoice_date": now_d.isoformat(), "amount": 150000.0
    }, [{"description": "Server Racks & Cables Part 3", "quantity": 1, "unit_price": 150000.0, "line_total": 150000.0}])
    res_e = run_risk_firewall(inv_e3["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_e['decision']} (Score: {res_e['final_score']}) | Reason: {res_e['decision_reason']}")

    # SCENARIO F: New Vendor with High-Value Invoice (> ₹1,00,000) -> ESCALATE
    print("\n[Scenario F] Brand new vendor with high-value first invoice...")
    v_new = db.create_vendor({
        "name": "Quantum AI Hardware Startup",
        "status": "ACTIVE"
    })
    inv_f = db.create_invoice({
        "invoice_number": "QAI-001",
        "vendor_id": v_new["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": now_d.isoformat(),
        "amount": 250000.0
    }, [
        {"description": "AI Accelerator Edge Boards", "quantity": 5, "unit_price": 50000.0, "line_total": 250000.0}
    ])
    res_f = run_risk_firewall(inv_f["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_f['decision']} (Score: {res_f['final_score']}) | Reason: {res_f['decision_reason']}")

    # SCENARIO G: Invalid GSTIN -> ESCALATE
    print("\n[Scenario G] Invoice with invalid GSTIN checksum...")
    v_gst_bad = db.create_vendor({
        "name": "Quick Printing Press",
        "status": "ACTIVE"
    })
    inv_g = db.create_invoice({
        "invoice_number": "QPP-4001",
        "vendor_id": v_gst_bad["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": now_d.isoformat(),
        "amount": 42000.0,
        "gstin_on_invoice": "27AAAAA0000A1ZZ" # Invalid checksum character 'Z'
    }, [
        {"description": "Annual Report Printing", "quantity": 200, "unit_price": 210.0, "line_total": 42000.0}
    ])
    res_g = run_risk_firewall(inv_g["id"], actor_label="SEED_SYSTEM")
    print(f" -> Decision: {res_g['decision']} (Score: {res_g['final_score']}) | Reason: {res_g['decision_reason']}")

    # SCENARIO H: Legitimate suspicious invoice -> Human Review -> Override
    print("\n[Scenario H] Suspicious invoice reviewed and overridden by Senior Approver...")
    v_susp = db.create_vendor({
        "name": "Metro Logistics Courier",
        "status": "ACTIVE"
    })
    # Add unverified bank account changed today -> causes ESCALATE
    db.create_vendor_bank_account({
        "vendor_id": v_susp["id"],
        "account_number": "555544443333",
        "ifsc": "ICIC0005555",
        "verified": False
    })
    inv_h = db.create_invoice({
        "invoice_number": "MLC-7711",
        "vendor_id": v_susp["id"],
        "vendor_match_status": "MATCHED",
        "invoice_date": now_d.isoformat(),
        "amount": 180000.0
    }, [
        {"description": "Urgent International Freight Shipment", "quantity": 1, "unit_price": 180000.0, "line_total": 180000.0}
    ])
    res_h = run_risk_firewall(inv_h["id"], actor_label="SEED_SYSTEM")
    print(f" -> Pre-Override Decision: {res_h['decision']} (Score: {res_h['final_score']}) | Reason: {res_h['decision_reason']}")
    
    # Senior Approver overrides decision
    db.record_approval(
        invoice_id=inv_h["id"],
        investigation_id=None,
        status="APPROVED",
        approver_role_label="SENIOR_APPROVER",
        previous_decision=res_h["decision"],
        new_decision="APPROVE",
        reason="Verified expedited air freight charges against approved emergency PO-9921",
        is_override=True
    )
    db.update_invoice_status(inv_h["id"], "APPROVED")
    print(" -> Override successfully applied by SENIOR_APPROVER. Status is now APPROVED.")

    # Create a Demo Payment Run
    print("\n[Payment Run Demo] Creating batch payment run...")
    p_run = db.create_payment_run(
        name="October Batch Payment Run",
        invoice_ids=[inv_a["id"], inv_b["id"], inv_c["id"], inv_h["id"]],
        created_by_label="FINANCE_MANAGER"
    )
    print(f" -> Payment Run '{p_run['name']}' created (Total Value: Rs.{p_run['total_value']:,.2f})")
    print(f" -> Readiness Summary: {p_run['readiness_summary']}")

    print("\n==================================================")
    print("SEEDING COMPLETE: ALL 8 SCENARIOS PROCESSED LIVE!")
    print("==================================================")

if __name__ == "__main__":
    run_seed()
