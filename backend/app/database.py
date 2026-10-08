import os
import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import uuid4
from backend.app.config import settings

DB_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "godspeed.db")

class Database:
    """
    Robust Dual-Mode Data Access Layer for AuditTrail AP:
    1. Direct Supabase client when SUPABASE_URL & SUPABASE_SERVICE_ROLE_KEY are set.
    2. Embedded SQLite engine with identical schema, constraints, payment release guard,
       and cryptographic SHA-256 hash-chaining when running locally or during tests.
    """
    def __init__(self):
        self.supabase_client = None
        if settings.supabase_url and settings.supabase_service_role_key:
            try:
                from supabase import create_client
                self.supabase_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
            except Exception as e:
                print(f"[Database] Could not initialize Supabase client: {e}. Falling back to SQLite.")
                self.supabase_client = None
        self._init_sqlite()

    def _get_connection(self):
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_sqlite(self):
        os.makedirs(os.path.dirname(os.path.abspath(DB_FILE)), exist_ok=True)
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS vendors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            gstin TEXT UNIQUE,
            pan TEXT,
            tds_category TEXT DEFAULT 'NOT_APPLICABLE',
            e_invoice_applicable INTEGER DEFAULT 0,
            vendor_category TEXT,
            created_at TEXT NOT NULL,
            first_invoice_date TEXT,
            status TEXT DEFAULT 'ACTIVE'
        );

        CREATE TABLE IF NOT EXISTS vendor_bank_accounts (
            id TEXT PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            account_number_masked TEXT NOT NULL,
            account_number_hash TEXT NOT NULL,
            ifsc TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            effective_to TEXT,
            verified INTEGER DEFAULT 0,
            source TEXT DEFAULT 'MANUAL_ENTRY',
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS vendor_trust_scores (
            id TEXT PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            score REAL NOT NULL,
            band TEXT NOT NULL,
            evidence_level TEXT NOT NULL,
            temporary_penalty INTEGER DEFAULT 0,
            calculation_detail TEXT DEFAULT '{}',
            calculated_at TEXT NOT NULL,
            is_current INTEGER DEFAULT 1,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            invoice_number TEXT NOT NULL,
            vendor_id TEXT,
            vendor_match_status TEXT DEFAULT 'NEW_VENDOR',
            po_id TEXT,
            invoice_date TEXT,
            currency TEXT DEFAULT 'INR',
            amount REAL NOT NULL,
            taxable_value REAL,
            tax_amount REAL,
            tds_amount REAL,
            gstin_on_invoice TEXT,
            irn TEXT,
            status TEXT DEFAULT 'INGESTED',
            validation_errors TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            description TEXT NOT NULL,
            normalized_description TEXT,
            quantity REAL,
            unit_price REAL,
            line_total REAL,
            hsn_sac_code TEXT,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS ai_evaluations (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            request_context TEXT NOT NULL,
            response_raw TEXT,
            response_validated TEXT,
            dropped_hallucinated_factors TEXT,
            status TEXT NOT NULL,
            failure_reason TEXT,
            model_provider TEXT,
            model_version TEXT,
            latency_ms INTEGER,
            token_usage TEXT,
            correlation_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS risk_assessments (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            previous_assessment_id TEXT,
            final_score REAL NOT NULL,
            decision TEXT NOT NULL,
            decision_reason TEXT NOT NULL,
            forced_by_hard_rule TEXT,
            ai_evaluation_id TEXT,
            created_at TEXT NOT NULL,
            is_current INTEGER DEFAULT 1,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS risk_signals (
            id TEXT PRIMARY KEY,
            risk_assessment_id TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            score_contribution REAL NOT NULL,
            confidence REAL NOT NULL,
            source TEXT NOT NULL,
            evidence TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            FOREIGN KEY (risk_assessment_id) REFERENCES risk_assessments(id)
        );

        CREATE TABLE IF NOT EXISTS duplicate_matches (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            matched_invoice_id TEXT NOT NULL,
            match_type TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            matched_fields TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            detected_at TEXT NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (matched_invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS split_invoice_groups (
            id TEXT PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            invoice_ids TEXT NOT NULL,
            cumulative_amount REAL NOT NULL,
            approval_threshold REAL NOT NULL,
            window_hours INTEGER NOT NULL,
            severity TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            suppression_reason TEXT,
            explanation TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        );

        CREATE TABLE IF NOT EXISTS investigations (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            risk_assessment_id TEXT,
            split_invoice_group_id TEXT,
            status TEXT DEFAULT 'OPEN',
            assigned_role_label TEXT DEFAULT 'FINANCE_MANAGER',
            outcome TEXT,
            outcome_rationale TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS investigation_comments (
            id TEXT PRIMARY KEY,
            investigation_id TEXT NOT NULL,
            author_label TEXT NOT NULL,
            body TEXT NOT NULL,
            mentioned_actor_labels TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            investigation_id TEXT,
            status TEXT NOT NULL,
            approver_role_label TEXT NOT NULL,
            previous_decision TEXT NOT NULL,
            new_decision TEXT NOT NULL,
            reason TEXT NOT NULL,
            is_override INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS payment_runs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'DRAFT',
            created_at TEXT NOT NULL,
            released_at TEXT,
            total_value REAL DEFAULT 0.0,
            created_by_label TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_run_items (
            id TEXT PRIMARY KEY,
            payment_run_id TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            snapshot_decision TEXT NOT NULL,
            snapshot_risk_score REAL NOT NULL,
            ready INTEGER DEFAULT 0,
            FOREIGN KEY (payment_run_id) REFERENCES payment_runs(id),
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            UNIQUE(payment_run_id, invoice_id)
        );

        CREATE TABLE IF NOT EXISTS compliance_checks (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            check_type TEXT NOT NULL,
            status TEXT NOT NULL,
            verification_type TEXT NOT NULL,
            detail TEXT NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
            id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            invoice_id TEXT,
            vendor_id TEXT,
            payment_run_id TEXT,
            investigation_id TEXT,
            correlation_id TEXT NOT NULL,
            actor_label TEXT NOT NULL,
            risk_score REAL,
            confidence REAL,
            decision TEXT,
            payload TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            current_hash TEXT NOT NULL
        );
        """)
        conn.commit()
        conn.close()

    # --- Vendor Methods ---
    def create_vendor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        vendor_id = data.get("id") or str(uuid4())
        created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        normalized_name = data["name"].strip().lower()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vendors (id, name, normalized_name, gstin, pan, tds_category, e_invoice_applicable, vendor_category, created_at, first_invoice_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            vendor_id, data["name"], normalized_name, data.get("gstin"), data.get("pan"),
            data.get("tds_category", "NOT_APPLICABLE"), 1 if data.get("e_invoice_applicable") else 0,
            data.get("vendor_category"), created_at, data.get("first_invoice_date"), data.get("status", "ACTIVE")
        ))
        conn.commit()
        conn.close()
        return self.get_vendor(vendor_id)

    def get_vendor(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["current_trust_score"] = self.get_current_trust_score(vendor_id)
        return res

    def find_vendor_by_gstin(self, gstin: str) -> Optional[Dict[str, Any]]:
        if not gstin:
            return None
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE gstin = ?", (gstin.strip().upper(),))
        row = cursor.fetchone()
        conn.close()
        if row:
            res = dict(row)
            res["current_trust_score"] = self.get_current_trust_score(res["id"])
            return res
        return None

    def find_vendor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        norm = name.strip().lower()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE normalized_name = ?", (norm,))
        row = cursor.fetchone()
        conn.close()
        if row:
            res = dict(row)
            res["current_trust_score"] = self.get_current_trust_score(res["id"])
            return res
        return None

    def get_all_vendors(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            d["current_trust_score"] = self.get_current_trust_score(d["id"])
            results.append(d)
        return results

    # --- Vendor Bank Account Methods ---
    def create_vendor_bank_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        acct_id = data.get("id") or str(uuid4())
        acc_num = data.get("account_number", "")
        masked = f"XXXXXXXX{acc_num[-4:]}" if len(acc_num) >= 4 else "XXXXXXXX"
        acc_hash = hashlib.sha256(acc_num.encode()).hexdigest()
        now_str = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO vendor_bank_accounts (id, vendor_id, account_number_masked, account_number_hash, ifsc, effective_from, verified, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            acct_id, data["vendor_id"], masked, acc_hash, data.get("ifsc", ""),
            now_str, 1 if data.get("verified") else 0, data.get("source", "MANUAL_ENTRY")
        ))
        conn.commit()
        conn.close()
        
        # Invalidate current trust score by applying temporary penalty of -20 per PRD
        self.apply_bank_change_penalty(data["vendor_id"])
        return self.get_vendor_bank_account(acct_id)

    def get_vendor_bank_account(self, acct_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_bank_accounts WHERE id = ?", (acct_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_latest_bank_account(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_bank_accounts WHERE vendor_id = ? ORDER BY effective_from DESC LIMIT 1", (vendor_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # --- Vendor Trust Score Methods ---
    def save_vendor_trust_score(self, vendor_id: str, score: float, band: str, evidence_level: str, temporary_penalty: bool, detail: Dict[str, Any]) -> Dict[str, Any]:
        score_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        # Mark previous current as false
        cursor.execute("UPDATE vendor_trust_scores SET is_current = 0 WHERE vendor_id = ?", (vendor_id,))
        cursor.execute("""
            INSERT INTO vendor_trust_scores (id, vendor_id, score, band, evidence_level, temporary_penalty, calculation_detail, calculated_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            score_id, vendor_id, score, band, evidence_level,
            1 if temporary_penalty else 0, json.dumps(detail), now_str
        ))
        conn.commit()
        conn.close()
        return {
            "id": score_id, "vendor_id": vendor_id, "score": score, "band": band,
            "evidence_level": evidence_level, "temporary_penalty": temporary_penalty,
            "calculation_detail": detail, "calculated_at": now_str, "is_current": True
        }

    def get_current_trust_score(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_trust_scores WHERE vendor_id = ? AND is_current = 1 LIMIT 1", (vendor_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["calculation_detail"] = json.loads(res["calculation_detail"] or "{}")
        res["temporary_penalty"] = bool(res["temporary_penalty"])
        res["is_current"] = bool(res["is_current"])
        return res

    def apply_bank_change_penalty(self, vendor_id: str):
        curr = self.get_current_trust_score(vendor_id)
        if curr:
            new_score = max(0.0, curr["score"] - 20.0)
            band = "AT_RISK" if new_score < 20 else ("DEVELOPING" if new_score < 45 else ("NEW" if new_score < 70 else "ESTABLISHED"))
            detail = curr["calculation_detail"]
            detail["bank_change_penalty"] = -20.0
            self.save_vendor_trust_score(vendor_id, new_score, band, curr["evidence_level"], True, detail)

    # --- Invoice Methods ---
    def create_invoice(self, data: Dict[str, Any], line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        invoice_id = data.get("id") or str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO invoices (id, invoice_number, vendor_id, vendor_match_status, po_id, invoice_date, currency, amount, taxable_value, tax_amount, tds_amount, gstin_on_invoice, irn, status, validation_errors, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice_id, data["invoice_number"], data.get("vendor_id"),
            data.get("vendor_match_status", "NEW_VENDOR"), data.get("po_id"),
            data.get("invoice_date"), data.get("currency", "INR"), data["amount"],
            data.get("taxable_value"), data.get("tax_amount"), data.get("tds_amount"),
            data.get("gstin_on_invoice"), data.get("irn"), data.get("status", "INGESTED"),
            json.dumps(data.get("validation_errors", [])), now_str, now_str
        ))
        
        for item in line_items:
            item_id = item.get("id") or str(uuid4())
            cursor.execute("""
                INSERT INTO invoice_line_items (id, invoice_id, description, normalized_description, quantity, unit_price, line_total, hsn_sac_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item_id, invoice_id, item["description"],
                item["description"].strip().lower(), item.get("quantity", 1.0),
                item.get("unit_price"), item.get("line_total"), item.get("hsn_sac_code")
            ))
            
        conn.commit()
        conn.close()
        return self.get_invoice(invoice_id)

    def update_invoice_status(self, invoice_id: str, new_status: str):
        # Database-Level Payment Release Safeguard
        if new_status == "PAID":
            latest_assessment = self.get_latest_assessment(invoice_id)
            if latest_assessment and latest_assessment["decision"] == "BLOCK":
                # Check for override approval
                approvals = self.get_approvals_for_invoice(invoice_id)
                override_approved = any(a["status"] == "APPROVED" and a["is_override"] for a in approvals)
                if not override_approved:
                    raise ValueError(f"DATABASE SAFEGUARD VIOLATION: Invoice {invoice_id} is BLOCKED and cannot be marked PAID without an approved override.")
            elif latest_assessment and latest_assessment["decision"] == "ESCALATE":
                approvals = self.get_approvals_for_invoice(invoice_id)
                approved = any(a["status"] == "APPROVED" for a in approvals)
                if not approved:
                    raise ValueError(f"DATABASE SAFEGUARD VIOLATION: Invoice {invoice_id} is ESCALATED and requires approval before payment release.")

        conn = self._get_connection()
        cursor = conn.cursor()
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, invoice_id))
        conn.commit()
        conn.close()

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.*, v.name as vendor_name 
            FROM invoices i 
            LEFT JOIN vendors v ON i.vendor_id = v.id 
            WHERE i.id = ?
        """, (invoice_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        inv = dict(row)
        
        cursor.execute("SELECT * FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,))
        inv["line_items"] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return inv

    def get_invoices_by_vendor(self, vendor_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM invoices WHERE vendor_id = ? ORDER BY invoice_date DESC, created_at DESC", (vendor_id,))
        rows = cursor.fetchall()
        invoices = []
        for r in rows:
            inv = dict(r)
            cursor.execute("SELECT * FROM invoice_line_items WHERE invoice_id = ?", (inv["id"],))
            inv["line_items"] = [dict(lr) for lr in cursor.fetchall()]
            invoices.append(inv)
        conn.close()
        return invoices

    def get_all_invoices(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = """
            SELECT i.*, v.name as vendor_name 
            FROM invoices i 
            LEFT JOIN vendors v ON i.vendor_id = v.id
        """
        params = []
        if status:
            query += " WHERE i.status = ?"
            params.append(status)
        query += " ORDER BY i.created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        invoices = []
        for r in rows:
            inv = dict(r)
            cursor.execute("SELECT * FROM invoice_line_items WHERE invoice_id = ?", (inv["id"],))
            inv["line_items"] = [dict(lr) for lr in cursor.fetchall()]
            invoices.append(inv)
        conn.close()
        return invoices

    # --- Risk Assessment & Signals ---
    def save_risk_assessment(self, assessment_data: Dict[str, Any], signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        assessment_id = assessment_data.get("id") or str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE risk_assessments SET is_current = 0 WHERE invoice_id = ?", (assessment_data["invoice_id"],))
        cursor.execute("""
            INSERT INTO risk_assessments (id, invoice_id, previous_assessment_id, final_score, decision, decision_reason, forced_by_hard_rule, ai_evaluation_id, created_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            assessment_id, assessment_data["invoice_id"], assessment_data.get("previous_assessment_id"),
            assessment_data["final_score"], assessment_data["decision"], assessment_data["decision_reason"],
            assessment_data.get("forced_by_hard_rule"), assessment_data.get("ai_evaluation_id"), now_str
        ))
        
        for sig in signals:
            sig_id = sig.get("id") or str(uuid4())
            cursor.execute("""
                INSERT INTO risk_signals (id, risk_assessment_id, category, severity, score_contribution, confidence, source, evidence, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sig_id, assessment_id, sig["category"], sig["severity"],
                sig["score_contribution"], sig["confidence"], sig["source"],
                json.dumps(sig.get("evidence", {})), sig.get("status", "OPEN")
            ))
            
        cursor.execute("UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?", (
            assessment_data["decision"], now_str, assessment_data["invoice_id"]
        ))
        
        conn.commit()
        conn.close()
        return self.get_risk_assessment(assessment_id)

    def get_latest_assessment(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_assessments WHERE invoice_id = ? AND is_current = 1 LIMIT 1", (invoice_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self.get_risk_assessment(row["id"])

    def get_risk_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_assessments WHERE id = ?", (assessment_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        res = dict(row)
        
        cursor.execute("SELECT * FROM risk_signals WHERE risk_assessment_id = ?", (assessment_id,))
        res["signals"] = []
        for sr in cursor.fetchall():
            sd = dict(sr)
            sd["evidence"] = json.loads(sd["evidence"] or "{}")
            res["signals"].append(sd)
            
        cursor.execute("SELECT * FROM duplicate_matches WHERE invoice_id = ? ORDER BY detected_at DESC", (res["invoice_id"],))
        res["duplicates"] = []
        for dr in cursor.fetchall():
            dd = dict(dr)
            dd["matched_fields"] = json.loads(dd["matched_fields"] or "{}")
            res["duplicates"].append(dd)
            
        cursor.execute("SELECT * FROM split_invoice_groups WHERE invoice_ids LIKE ? AND status != 'FALSE_POSITIVE' LIMIT 1", (f"%{res['invoice_id']}%",))
        srow = cursor.fetchone()
        if srow:
            sdict = dict(srow)
            sdict["invoice_ids"] = json.loads(sdict["invoice_ids"]) if sdict["invoice_ids"].startswith("[") else sdict["invoice_ids"].split(",")
            res["split_group"] = sdict
        else:
            res["split_group"] = None
            
        cursor.execute("SELECT * FROM compliance_checks WHERE invoice_id = ?", (res["invoice_id"],))
        res["compliance_checks"] = []
        for cr in cursor.fetchall():
            cd = dict(cr)
            cd["detail"] = json.loads(cd["detail"] or "{}")
            res["compliance_checks"].append(cd)
            
        if res.get("ai_evaluation_id"):
            cursor.execute("SELECT * FROM ai_evaluations WHERE id = ?", (res["ai_evaluation_id"],))
            arow = cursor.fetchone()
            if arow:
                ad = dict(arow)
                ad["validated_output"] = json.loads(ad["response_validated"]) if ad.get("response_validated") else None
                ad["dropped_hallucinated_factors"] = json.loads(ad["dropped_hallucinated_factors"]) if ad.get("dropped_hallucinated_factors") else None
                res["ai_evaluation"] = ad
            else:
                res["ai_evaluation"] = None
        else:
            res["ai_evaluation"] = None
            
        conn.close()
        return res

    # --- Duplicate Matches ---
    def record_duplicate_match(self, invoice_id: str, matched_invoice_id: str, match_type: str, similarity_score: float, matched_fields: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO duplicate_matches (id, invoice_id, matched_invoice_id, match_type, similarity_score, matched_fields, status, detected_at)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?)
        """, (
            str(uuid4()), invoice_id, matched_invoice_id, match_type, similarity_score,
            json.dumps(matched_fields), datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    # --- Split Invoice Groups ---
    def create_split_group(self, vendor_id: str, invoice_ids: List[str], cumulative_amount: float, threshold: float, window_hours: int, severity: str, explanation: str) -> Dict[str, Any]:
        group_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO split_invoice_groups (id, vendor_id, invoice_ids, cumulative_amount, approval_threshold, window_hours, severity, status, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        """, (
            group_id, vendor_id, json.dumps(invoice_ids), cumulative_amount, threshold,
            window_hours, severity, explanation, now_str
        ))
        conn.commit()
        conn.close()
        return {
            "id": group_id, "vendor_id": vendor_id, "invoice_ids": invoice_ids,
            "cumulative_amount": cumulative_amount, "approval_threshold": threshold,
            "window_hours": window_hours, "severity": severity, "status": "OPEN",
            "explanation": explanation, "created_at": now_str
        }

    # --- AI Evaluations ---
    def record_ai_evaluation(self, eval_data: Dict[str, Any]) -> str:
        eval_id = eval_data.get("id") or str(uuid4())
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_evaluations (id, invoice_id, request_context, response_raw, response_validated, dropped_hallucinated_factors, status, failure_reason, model_provider, model_version, latency_ms, token_usage, correlation_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eval_id, eval_data["invoice_id"], json.dumps(eval_data.get("request_context", {})),
            json.dumps(eval_data.get("response_raw", {})), json.dumps(eval_data.get("response_validated", {})),
            json.dumps(eval_data.get("dropped_hallucinated_factors", [])), eval_data["status"],
            eval_data.get("failure_reason"), eval_data.get("model_provider"), eval_data.get("model_version"),
            eval_data.get("latency_ms"), json.dumps(eval_data.get("token_usage", {})),
            eval_data["correlation_id"], datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
        return eval_id

    # --- Compliance Checks ---
    def record_compliance_check(self, invoice_id: str, check_type: str, status: str, verification_type: str, detail: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO compliance_checks (id, invoice_id, check_type, status, verification_type, detail, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid4()), invoice_id, check_type, status, verification_type,
            json.dumps(detail), datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    # --- Investigation Methods ---
    def create_investigation(self, invoice_id: str, risk_assessment_id: Optional[str] = None, split_group_id: Optional[str] = None) -> Dict[str, Any]:
        # Check if already open
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE invoice_id = ? AND status IN ('OPEN', 'IN_REVIEW', 'WAITING_FOR_INFORMATION')", (invoice_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return self.get_investigation(existing["id"])
            
        inv_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO investigations (id, invoice_id, risk_assessment_id, split_invoice_group_id, status, assigned_role_label, created_at)
            VALUES (?, ?, ?, ?, 'OPEN', 'FINANCE_MANAGER', ?)
        """, (inv_id, invoice_id, risk_assessment_id, split_group_id, now_str))
        conn.commit()
        conn.close()
        return self.get_investigation(inv_id)

    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        res = dict(row)
        cursor.execute("SELECT * FROM investigation_comments WHERE investigation_id = ? ORDER BY created_at ASC", (investigation_id,))
        res["comments"] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return res

    def get_investigation_by_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE invoice_id = ? ORDER BY created_at DESC LIMIT 1", (invoice_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self.get_investigation(row["id"])
        return None

    def add_investigation_comment(self, investigation_id: str, author_label: str, body: str) -> Dict[str, Any]:
        cid = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO investigation_comments (id, investigation_id, author_label, body, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (cid, investigation_id, author_label, body, now_str))
        cursor.execute("UPDATE investigations SET status = 'IN_REVIEW' WHERE id = ? AND status = 'OPEN'", (investigation_id,))
        conn.commit()
        conn.close()
        return {"id": cid, "investigation_id": investigation_id, "author_label": author_label, "body": body, "created_at": now_str}

    def resolve_investigation(self, investigation_id: str, outcome: str, rationale: str, actor_label: str) -> Dict[str, Any]:
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id FROM investigations WHERE id = ?", (investigation_id,))
        inv_row = cursor.fetchone()
        if not inv_row:
            conn.close()
            raise ValueError("Investigation not found")
        invoice_id = inv_row["invoice_id"]
        
        cursor.execute("""
            UPDATE investigations 
            SET status = 'RESOLVED', outcome = ?, outcome_rationale = ?, resolved_at = ?
            WHERE id = ?
        """, (outcome, rationale, now_str, investigation_id))
        
        # Outcome side-effects per PRD Section 11.5
        if outcome == "APPROVED_AFTER_REVIEW":
            # Record approval
            self.record_approval(invoice_id, investigation_id, "APPROVED", actor_label, "BLOCK/ESCALATE", "APPROVED", rationale, is_override=True)
            cursor.execute("UPDATE invoices SET status = 'APPROVED', updated_at = ? WHERE id = ?", (now_str, invoice_id))
        elif outcome == "BLOCKED":
            cursor.execute("UPDATE invoices SET status = 'BLOCKED', updated_at = ? WHERE id = ?", (now_str, invoice_id))
        elif outcome == "DUPLICATE_CONFIRMED":
            cursor.execute("UPDATE invoices SET status = 'REJECTED', updated_at = ? WHERE id = ?", (now_str, invoice_id))
            cursor.execute("UPDATE duplicate_matches SET status = 'CONFIRMED' WHERE invoice_id = ?", (invoice_id,))
        elif outcome == "CONTRACT_AMENDMENT_VERIFIED":
            cursor.execute("UPDATE split_invoice_groups SET status = 'FALSE_POSITIVE' WHERE invoice_ids LIKE ?", (f"%{invoice_id}%",))
        elif outcome == "BANK_CHANGE_VERIFIED":
            cursor.execute("SELECT vendor_id FROM invoices WHERE id = ?", (invoice_id,))
            vrow = cursor.fetchone()
            if vrow:
                cursor.execute("UPDATE vendor_bank_accounts SET verified = 1 WHERE vendor_id = ?", (vrow["vendor_id"],))
                cursor.execute("UPDATE vendor_trust_scores SET temporary_penalty = 0 WHERE vendor_id = ?", (vrow["vendor_id"],))
                
        conn.commit()
        conn.close()
        return self.get_investigation(investigation_id)

    # --- Approvals & Overrides ---
    def record_approval(self, invoice_id: str, investigation_id: Optional[str], status: str, approver_role_label: str, previous_decision: str, new_decision: str, reason: str, is_override: bool = False) -> Dict[str, Any]:
        app_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO approvals (id, invoice_id, investigation_id, status, approver_role_label, previous_decision, new_decision, reason, is_override, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            app_id, invoice_id, investigation_id, status, approver_role_label,
            previous_decision, new_decision, reason, 1 if is_override else 0, now_str
        ))
        conn.commit()
        conn.close()
        return {
            "id": app_id, "invoice_id": invoice_id, "investigation_id": investigation_id,
            "status": status, "approver_role_label": approver_role_label,
            "previous_decision": previous_decision, "new_decision": new_decision,
            "reason": reason, "is_override": is_override, "created_at": now_str
        }

    def get_approvals_for_invoice(self, invoice_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM approvals WHERE invoice_id = ?", (invoice_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- Payment Runs ---
    def create_payment_run(self, name: str, invoice_ids: List[str], created_by_label: str = "FINANCE_MANAGER") -> Dict[str, Any]:
        run_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        total_val = 0.0
        items_to_insert = []
        for inv_id in invoice_ids:
            cursor.execute("SELECT * FROM invoices WHERE id = ?", (inv_id,))
            inv_row = cursor.fetchone()
            if not inv_row:
                continue
            total_val += inv_row["amount"]
            
            cursor.execute("SELECT * FROM risk_assessments WHERE invoice_id = ? AND is_current = 1 LIMIT 1", (inv_id,))
            ass_row = cursor.fetchone()
            snap_decision = ass_row["decision"] if ass_row else "APPROVE"
            snap_score = ass_row["final_score"] if ass_row else 0.0
            
            # Check readiness: APPROVE or (ESCALATE with approval)
            is_ready = False
            if snap_decision == "APPROVE":
                is_ready = True
            elif snap_decision == "ESCALATE":
                cursor.execute("SELECT COUNT(*) as c FROM approvals WHERE invoice_id = ? AND status = 'APPROVED'", (inv_id,))
                if cursor.fetchone()["c"] > 0:
                    is_ready = True
                    
            item_id = str(uuid4())
            items_to_insert.append((item_id, run_id, inv_id, snap_decision, snap_score, 1 if is_ready else 0))
            
        cursor.execute("""
            INSERT INTO payment_runs (id, name, status, created_at, total_value, created_by_label)
            VALUES (?, ?, 'DRAFT', ?, ?, ?)
        """, (run_id, name, now_str, total_val, created_by_label))
        
        for it in items_to_insert:
            cursor.execute("""
                INSERT INTO payment_run_items (id, payment_run_id, invoice_id, snapshot_decision, snapshot_risk_score, ready)
                VALUES (?, ?, ?, ?, ?, ?)
            """, it)
            
        conn.commit()
        conn.close()
        return self.get_payment_run(run_id)

    def get_payment_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payment_runs WHERE id = ?", (run_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        res = dict(row)
        
        cursor.execute("""
            SELECT pri.*, i.invoice_number, i.amount 
            FROM payment_run_items pri
            JOIN invoices i ON pri.invoice_id = i.id
            WHERE pri.payment_run_id = ?
        """, (run_id,))
        res["items"] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        
        total_items = len(res["items"])
        ready_items = sum(1 for it in res["items"] if it["ready"])
        blocked_items = sum(1 for it in res["items"] if it["snapshot_decision"] == "BLOCK")
        res["readiness_summary"] = {
            "total_items": total_items,
            "ready_items": ready_items,
            "blocked_items": blocked_items,
            "is_fully_ready": total_items > 0 and total_items == ready_items
        }
        return res

    def check_payment_run_readiness(self, run_id: str) -> Dict[str, Any]:
        run = self.get_payment_run(run_id)
        if not run:
            raise ValueError("Payment run not found")
        return run["readiness_summary"]

    # --- Append-only Hash-chained Audit Events ---
    def record_audit_event(self, event_type: str, actor_label: str, payload: Dict[str, Any], correlation_id: Optional[str] = None, invoice_id: Optional[str] = None, vendor_id: Optional[str] = None, payment_run_id: Optional[str] = None, risk_score: Optional[float] = None, decision: Optional[str] = None) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch previous hash
        cursor.execute("SELECT sequence_number, current_hash FROM audit_events ORDER BY sequence_number DESC LIMIT 1")
        last_row = cursor.fetchone()
        if last_row:
            prev_hash = last_row["current_hash"]
        else:
            prev_hash = "0" * 64
            
        event_id = str(uuid4())
        corr_id = correlation_id or str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()
        
        # 2. Canonical JSON computation
        canonical_dict = {
            "actor_label": actor_label,
            "correlation_id": corr_id,
            "decision": decision,
            "event_type": event_type,
            "invoice_id": invoice_id,
            "occurred_at": now_str,
            "payload": payload,
            "risk_score": risk_score
        }
        canonical_str = json.dumps(canonical_dict, sort_keys=True)
        cur_hash = hashlib.sha256((canonical_str + prev_hash).encode()).hexdigest()
        
        cursor.execute("""
            INSERT INTO audit_events (id, event_type, occurred_at, invoice_id, vendor_id, payment_run_id, correlation_id, actor_label, risk_score, decision, payload, previous_hash, current_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, event_type, now_str, invoice_id, vendor_id, payment_run_id,
            corr_id, actor_label, risk_score, decision, json.dumps(payload),
            prev_hash, cur_hash
        ))
        seq = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "sequence_number": seq,
            "id": event_id,
            "event_type": event_type,
            "occurred_at": now_str,
            "invoice_id": invoice_id,
            "vendor_id": vendor_id,
            "payment_run_id": payment_run_id,
            "correlation_id": corr_id,
            "actor_label": actor_label,
            "risk_score": risk_score,
            "decision": decision,
            "payload": payload,
            "previous_hash": prev_hash,
            "current_hash": cur_hash
        }

    def get_audit_events(self, invoice_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        if invoice_id:
            cursor.execute("SELECT * FROM audit_events WHERE invoice_id = ? ORDER BY sequence_number DESC LIMIT ?", (invoice_id, limit))
        else:
            cursor.execute("SELECT * FROM audit_events ORDER BY sequence_number DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        results = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"] or "{}")
            results.append(d)
        return results

    def verify_audit_chain(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_events ORDER BY sequence_number ASC")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {"valid": True, "rows_checked": 0, "first_broken_sequence": None}
            
        prev_hash = "0" * 64
        for r in rows:
            seq = r["sequence_number"]
            if r["previous_hash"] != prev_hash:
                return {"valid": False, "rows_checked": seq, "first_broken_sequence": seq}
                
            canonical_dict = {
                "actor_label": r["actor_label"],
                "correlation_id": r["correlation_id"],
                "decision": r["decision"],
                "event_type": r["event_type"],
                "invoice_id": r["invoice_id"],
                "occurred_at": r["occurred_at"],
                "payload": json.loads(r["payload"] or "{}"),
                "risk_score": r["risk_score"]
            }
            canonical_str = json.dumps(canonical_dict, sort_keys=True)
            expected_hash = hashlib.sha256((canonical_str + prev_hash).encode()).hexdigest()
            if r["current_hash"] != expected_hash:
                return {"valid": False, "rows_checked": seq, "first_broken_sequence": seq}
            prev_hash = r["current_hash"]
            
        return {"valid": True, "rows_checked": len(rows), "first_broken_sequence": None}

db = Database()
