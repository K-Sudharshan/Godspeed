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
        force_sqlite = os.environ.get("FORCE_SQLITE", "").lower() in ("1", "true", "yes")
        
        if not force_sqlite and settings.supabase_url and settings.supabase_service_role_key:
            try:
                from supabase import create_client
                self.supabase_client = create_client(settings.supabase_url, settings.supabase_service_role_key)
                print(f"[Database] Active database mode: SUPABASE ({settings.supabase_url})")
            except Exception as e:
                print(f"[Database] Could not initialize Supabase client: {e}. Falling back to SQLite.")
                self.supabase_client = None
        else:
            print("[Database] Active database mode: SQLITE (local embedded engine)")
            
        self._init_sqlite()

    @property
    def mode(self) -> str:
        return "SUPABASE" if self.supabase_client is not None else "SQLITE"

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
            quantity REAL DEFAULT 1.0,
            unit_price REAL,
            line_total REAL,
            hsn_sac_code TEXT,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE TABLE IF NOT EXISTS risk_rules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            rule_type TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL,
            config TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS ai_evaluations (
            id TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL,
            assessment_id TEXT,
            request_context TEXT NOT NULL,
            response_raw TEXT,
            response_validated TEXT,
            validated_output TEXT,
            dropped_hallucinated_factors TEXT,
            status TEXT NOT NULL,
            failure_reason TEXT,
            model_provider TEXT,
            model_version TEXT,
            provider TEXT,
            provider_used TEXT,
            model TEXT,
            fallback_used INTEGER DEFAULT 0,
            fallback_reason TEXT,
            requested_at TEXT,
            completed_at TEXT,
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
            FOREIGN KEY (invoice_id) REFERENCES invoices(id),
            FOREIGN KEY (ai_evaluation_id) REFERENCES ai_evaluations(id)
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
        
        # Ensure migration columns for ai_evaluations exist in existing databases
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(ai_evaluations)")
        existing_cols = [r[1] for r in cursor.fetchall()]
        needed_cols = [
            ("assessment_id", "TEXT"),
            ("provider", "TEXT"),
            ("provider_used", "TEXT"),
            ("model", "TEXT"),
            ("fallback_used", "INTEGER DEFAULT 0"),
            ("fallback_reason", "TEXT"),
            ("requested_at", "TEXT"),
            ("completed_at", "TEXT"),
            ("validated_output", "TEXT")
        ]
        for col_name, col_def in needed_cols:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE ai_evaluations ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

        conn.commit()
        conn.close()

    # --- Vendor Methods ---
    def create_vendor(self, data: Dict[str, Any]) -> Dict[str, Any]:
        vendor_id = data.get("id") or str(uuid4())
        created_at = data.get("created_at") or datetime.now(timezone.utc).isoformat()
        normalized_name = data["name"].strip().lower()

        if self.supabase_client:
            cat = data.get("vendor_category") or data.get("category") or "GOODS"
            if cat not in ("GOODS", "OTHER", "LOGISTICS", "IT_SERVICES"):
                cat = "GOODS"
            row = {
                "id": vendor_id,
                "vendor_code": data.get("vendor_code") or f"V-{vendor_id[:8].upper()}",
                "legal_name": data.get("legal_name") or data["name"],
                "name": data["name"],
                "normalized_name": normalized_name,
                "category": cat,
                "e_invoice_applicable": bool(data.get("e_invoice_applicable")),
                "po_required": bool(data.get("po_required")),
                "invoice_number_reuse_allowed": bool(data.get("invoice_number_reuse_allowed")),
                "split_billing_allowed": bool(data.get("split_billing_allowed")),
                "default_currency": data.get("currency") or "INR",
                "status": data.get("status") or "ACTIVE",
                "source": data.get("source") or "MANUAL",
                "onboarded_at": created_at,
                "version": 1,
                "created_at": created_at,
                "updated_at": created_at,
                "gstin": data.get("gstin"),
                "pan": data.get("pan"),
                "tds_category": data.get("tds_category", "NOT_APPLICABLE")
            }
            self.supabase_client.table("vendors").insert(row).execute()
            return self.get_vendor(vendor_id)
        
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
        if self.supabase_client:
            res = self.supabase_client.table("vendors").select("*").eq("id", vendor_id).execute()
            if not res.data:
                return None
            v = res.data[0]
            if not v.get("name") and v.get("legal_name"):
                v["name"] = v["legal_name"]
            v["current_trust_score"] = self.get_current_trust_score(vendor_id)
            return v

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
        norm_gstin = gstin.strip().upper()

        if self.supabase_client:
            res = self.supabase_client.table("vendors").select("*").eq("gstin", norm_gstin).execute()
            if res.data:
                v = res.data[0]
                if not v.get("name") and v.get("legal_name"):
                    v["name"] = v["legal_name"]
                v["current_trust_score"] = self.get_current_trust_score(v["id"])
                return v
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendors WHERE gstin = ?", (norm_gstin,))
        row = cursor.fetchone()
        conn.close()
        if row:
            res = dict(row)
            res["current_trust_score"] = self.get_current_trust_score(res["id"])
            return res
        return None

    def find_vendor_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        norm = name.strip().lower()

        if self.supabase_client:
            res = self.supabase_client.table("vendors").select("*").eq("normalized_name", norm).execute()
            if res.data:
                v = res.data[0]
                if not v.get("name") and v.get("legal_name"):
                    v["name"] = v["legal_name"]
                v["current_trust_score"] = self.get_current_trust_score(v["id"])
                return v
            return None

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
        if self.supabase_client:
            res = self.supabase_client.table("vendors").select("*").order("created_at", desc=True).execute()
            out = []
            for v in res.data:
                if not v.get("name") and v.get("legal_name"):
                    v["name"] = v["legal_name"]
                v["current_trust_score"] = self.get_current_trust_score(v["id"])
                out.append(v)
            return out

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
        last4 = acc_num[-4:] if len(acc_num) >= 4 else "0000"
        masked = f"XXXXXXXX{last4}"
        acc_hash = hashlib.sha256(acc_num.encode()).hexdigest() if acc_num else ("0" * 64)
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            ifsc_val = data.get("ifsc", "HDFC0000001")
            row = {
                "id": acct_id,
                "vendor_id": data["vendor_id"],
                "account_number_enc": "\\x01020304",
                "account_number_hash": acc_hash,
                "account_number_last4": last4,
                "account_number_masked": masked,
                "ifsc": ifsc_val,
                "status": "ACTIVE",
                "activated_at": now_str,
                "callback_verified": bool(data.get("verified", False)),
                "requested_by_label": "AP_ANALYST",
                "source": data.get("source", "MANUAL_ENTRY"),
                "verified": bool(data.get("verified", False)),
                "effective_from": now_str,
                "created_at": now_str,
                "updated_at": now_str
            }
            self.supabase_client.table("vendor_bank_accounts").insert(row).execute()
            self.apply_bank_change_penalty(data["vendor_id"])
            return self.get_vendor_bank_account(acct_id)
        
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
        
        self.apply_bank_change_penalty(data["vendor_id"])
        return self.get_vendor_bank_account(acct_id)

    def get_vendor_bank_account(self, acct_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("vendor_bank_accounts").select("*").eq("id", acct_id).execute()
            return res.data[0] if res.data else None

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_bank_accounts WHERE id = ?", (acct_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_latest_bank_account(self, vendor_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("vendor_bank_accounts").select("*").eq("vendor_id", vendor_id).order("created_at", desc=True).limit(1).execute()
            return res.data[0] if res.data else None

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_bank_accounts WHERE vendor_id = ? ORDER BY effective_from DESC LIMIT 1", (vendor_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_vendor_bank_accounts(self, vendor_id: str) -> List[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("vendor_bank_accounts").select("*").eq("vendor_id", vendor_id).execute()
            return res.data or []

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM vendor_bank_accounts WHERE vendor_id = ?", (vendor_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    # --- Vendor Trust Score Methods ---
    def save_vendor_trust_score(self, vendor_id: str, score: float, band: str, evidence_level: str, temporary_penalty: bool, detail: Dict[str, Any]) -> Dict[str, Any]:
        score_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            # Map band to allowed enum: ('HIGH_TRUST', 'MODERATE', 'LOW_TRUST', 'UNRATED')
            if band in ('HIGH_TRUST', 'MODERATE', 'LOW_TRUST', 'UNRATED'):
                pg_band = band
            elif score >= 75.0:
                pg_band = 'HIGH_TRUST'
            elif score < 45.0:
                pg_band = 'LOW_TRUST'
            else:
                pg_band = 'MODERATE'

            # Map evidence to allowed enum: ('NO_EVIDENCE', 'LIMITED', 'ESTABLISHED')
            if evidence_level in ('NO_EVIDENCE', 'LIMITED', 'ESTABLISHED'):
                pg_ev = evidence_level
            elif evidence_level == 'SUFFICIENT':
                pg_ev = 'ESTABLISHED'
            else:
                pg_ev = 'LIMITED'

            # The vendor_trust_scores table is immutable with unique index on (vendor_id) WHERE is_current = true.
            # If a current score exists, subsequent evaluations are appended with is_current = False.
            existing_current = self.supabase_client.table("vendor_trust_scores").select("id").eq("vendor_id", vendor_id).eq("is_current", True).execute()
            is_curr_val = False if existing_current.data else True

            row = {
                "id": score_id,
                "vendor_id": vendor_id,
                "score": float(score),
                "evidence_state": pg_ev,
                "confidence": 0.95,
                "band": pg_band,
                "components": detail if isinstance(detail, dict) else {},
                "trigger_event": "INVOICE_EVALUATION",
                "algorithm_version": "1.0",
                "is_current": is_curr_val,
                "computed_at": now_str,
                "calculation_detail": detail if isinstance(detail, dict) else {},
                "calculated_at": now_str
            }
            self.supabase_client.table("vendor_trust_scores").insert(row).execute()
            return {
                "id": score_id, "vendor_id": vendor_id, "score": score, "band": band,
                "evidence_level": evidence_level, "temporary_penalty": temporary_penalty,
                "calculation_detail": detail, "calculated_at": now_str, "is_current": True
            }

        conn = self._get_connection()
        cursor = conn.cursor()
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
        if self.supabase_client:
            res = self.supabase_client.table("vendor_trust_scores").select("*").eq("vendor_id", vendor_id).order("computed_at", desc=True).limit(1).execute()
            if not res.data:
                return None
            r = res.data[0]
            if not r.get("calculation_detail"):
                r["calculation_detail"] = r.get("components") or {}
            r["temporary_penalty"] = False
            r["is_current"] = True
            r["evidence_level"] = r.get("evidence_state", "LIMITED")
            return r

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
            self.save_vendor_trust_score(vendor_id, new_score, band, curr.get("evidence_level", "LIMITED"), True, detail)

    # --- Invoice Methods ---
    def create_invoice(self, data: Dict[str, Any], line_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        invoice_id = data.get("id") or str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            st = data.get("status", "INGESTED")
            if st == "APPROVE": st = "APPROVED"
            elif st == "ESCALATE": st = "ESCALATED"
            elif st == "BLOCK": st = "BLOCKED"

            inv_row = {
                "id": invoice_id,
                "invoice_number": data["invoice_number"],
                "vendor_id": data.get("vendor_id"),
                "vendor_match_status": data.get("vendor_match_status", "MATCHED"),
                "po_id": data.get("po_id"),
                "invoice_date": data.get("invoice_date") or now_str[:10],
                "currency": data.get("currency", "INR"),
                "amount": float(data["amount"]),
                "taxable_value": float(data.get("taxable_value") or 0.0),
                "tax_amount": float(data.get("tax_amount") or 0.0),
                "tds_amount": float(data.get("tds_amount") or 0.0),
                "gstin_on_invoice": data.get("gstin_on_invoice"),
                "irn": data.get("irn"),
                "status": st,
                "validation_errors": data.get("validation_errors", []),
                "created_at": now_str,
                "updated_at": now_str
            }
            self.supabase_client.table("invoices").insert(inv_row).execute()

            if line_items:
                li_rows = []
                for item in line_items:
                    li_id = item.get("id") or str(uuid4())
                    li_rows.append({
                        "id": li_id,
                        "invoice_id": invoice_id,
                        "description": item["description"],
                        "normalized_description": item["description"].strip().lower(),
                        "quantity": float(item.get("quantity", 1.0)),
                        "unit_price": float(item.get("unit_price", 0.0)),
                        "line_total": float(item.get("line_total", 0.0)),
                        "hsn_sac_code": item.get("hsn_sac_code")
                    })
                self.supabase_client.table("invoice_line_items").insert(li_rows).execute()
            return self.get_invoice(invoice_id)

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
                approvals = self.get_approvals_for_invoice(invoice_id)
                override_approved = any(a.get("status") == "APPROVED" and a.get("is_override") for a in approvals)
                if not override_approved:
                    raise ValueError(f"DATABASE SAFEGUARD VIOLATION: Invoice {invoice_id} is BLOCKED and cannot be marked PAID without an approved override.")
            elif latest_assessment and latest_assessment["decision"] == "ESCALATE":
                approvals = self.get_approvals_for_invoice(invoice_id)
                approved = any(a.get("status") == "APPROVED" for a in approvals)
                if not approved:
                    raise ValueError(f"DATABASE SAFEGUARD VIOLATION: Invoice {invoice_id} is ESCALATED and requires approval before payment release.")

        st = new_status
        if st == "APPROVE": st = "APPROVED"
        elif st == "ESCALATE": st = "ESCALATED"
        elif st == "BLOCK": st = "BLOCKED"
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            self.supabase_client.table("invoices").update({"status": st, "updated_at": now_str}).eq("id", invoice_id).execute()
            return

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, invoice_id))
        conn.commit()
        conn.close()

    def update_invoice(self, invoice_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        now_str = datetime.now(timezone.utc).isoformat()
        allowed_fields = [
            "amount", "invoice_number", "vendor_id", "currency", "taxable_value",
            "tax_amount", "tds_amount", "gstin_on_invoice", "irn", "po_id", "status", "vendor_match_status"
        ]

        if self.supabase_client:
            up = {}
            for f in allowed_fields:
                if f in updates:
                    val = updates[f]
                    if f == "status":
                        if val == "APPROVE": val = "APPROVED"
                        elif val == "ESCALATE": val = "ESCALATED"
                        elif val == "BLOCK": val = "BLOCKED"
                    up[f] = val
            if up:
                up["updated_at"] = now_str
                self.supabase_client.table("invoices").update(up).eq("id", invoice_id).execute()
            return self.get_invoice(invoice_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        set_clauses = []
        params = []
        for f in allowed_fields:
            if f in updates:
                set_clauses.append(f"{f} = ?")
                params.append(updates[f])
        if not set_clauses:
            conn.close()
            return self.get_invoice(invoice_id)
        
        set_clauses.append("updated_at = ?")
        params.append(now_str)
        params.append(invoice_id)
        
        cursor.execute(f"UPDATE invoices SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return self.get_invoice(invoice_id)

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("invoices").select("*").eq("id", invoice_id).execute()
            if not res.data:
                return None
            inv = res.data[0]
            inv["vendor_match_status"] = inv.get("vendor_match_status") or "MATCHED"
            if inv.get("vendor_id"):
                v_res = self.supabase_client.table("vendors").select("name, legal_name").eq("id", inv["vendor_id"]).execute()
                if v_res.data:
                    inv["vendor_name"] = v_res.data[0].get("name") or v_res.data[0].get("legal_name")
            li_res = self.supabase_client.table("invoice_line_items").select("*").eq("invoice_id", invoice_id).execute()
            inv["line_items"] = li_res.data or []
            return inv

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
        if self.supabase_client:
            res = self.supabase_client.table("invoices").select("*").eq("vendor_id", vendor_id).order("created_at", desc=True).execute()
            invoices = res.data or []
            for inv in invoices:
                li_res = self.supabase_client.table("invoice_line_items").select("*").eq("invoice_id", inv["id"]).execute()
                inv["line_items"] = li_res.data or []
            return invoices

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
        if self.supabase_client:
            q = self.supabase_client.table("invoices").select("*")
            if status:
                st = status
                if st == "APPROVE": st = "APPROVED"
                elif st == "ESCALATE": st = "ESCALATED"
                elif st == "BLOCK": st = "BLOCKED"
                q = q.eq("status", st)
            res = q.order("created_at", desc=True).execute()
            invoices = res.data or []
            
            # Efficiently map vendor names
            vendors_map = {}
            try:
                v_res = self.supabase_client.table("vendors").select("id, name, legal_name").execute()
                for v in (v_res.data or []):
                    vendors_map[v["id"]] = v.get("name") or v.get("legal_name")
            except Exception:
                pass

            for inv in invoices:
                inv["vendor_match_status"] = inv.get("vendor_match_status") or "MATCHED"
                inv["vendor_name"] = vendors_map.get(inv.get("vendor_id"), "Vendor")
                try:
                    li_res = self.supabase_client.table("invoice_line_items").select("*").eq("invoice_id", inv["id"]).execute()
                    inv["line_items"] = li_res.data or []
                except Exception:
                    inv["line_items"] = []
            return invoices

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
        invoice_id = assessment_data["invoice_id"]

        decision_val = assessment_data["decision"]
        if decision_val == "APPROVED": decision_val = "APPROVE"
        elif decision_val == "ESCALATED": decision_val = "ESCALATE"
        elif decision_val == "BLOCKED": decision_val = "BLOCK"

        if self.supabase_client:
            # 1. Fetch prior current assessment
            prior_res = self.supabase_client.table("risk_assessments").select("id").eq("invoice_id", invoice_id).eq("is_current", True).execute()
            prev_id = assessment_data.get("previous_assessment_id") or (prior_res.data[0]["id"] if prior_res.data else None)

            # 2. Mark previous current as false
            try:
                self.supabase_client.table("risk_assessments").update({"is_current": False}).eq("invoice_id", invoice_id).execute()
            except Exception as e:
                print(f"[Database] Notice updating prior assessments: {e}")

            # 3. Insert new assessment
            ass_row = {
                "id": assessment_id,
                "invoice_id": invoice_id,
                "previous_assessment_id": prev_id,
                "final_score": float(assessment_data["final_score"]),
                "decision": decision_val,
                "decision_reason": assessment_data["decision_reason"],
                "forced_by_hard_rule": assessment_data.get("forced_by_hard_rule"),
                "ai_evaluation_id": assessment_data.get("ai_evaluation_id"),
                "created_at": now_str,
                "is_current": True
            }
            self.supabase_client.table("risk_assessments").insert(ass_row).execute()

            # 4. Insert risk signals
            if signals:
                sig_rows = []
                for sig in signals:
                    cat = sig.get("category", "VENDOR")
                    if cat not in ('DUPLICATE', 'PRICING', 'VENDOR', 'COMPLIANCE', 'SPLIT_INVOICE', 'BANK_CHANGE', 'DATA_QUALITY', 'AI_SYNTHESIS'):
                        cat = "VENDOR"
                    sev = sig.get("severity", "LOW")
                    if sev not in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
                        sev = "LOW"
                    src = sig.get("source", "RULE_ENGINE")
                    if src not in ('RULE_ENGINE', 'STATISTICAL', 'DUPLICATE_ENGINE', 'SPLIT_ENGINE', 'AI'):
                        src = "RULE_ENGINE"
                    sig_rows.append({
                        "id": sig.get("id") or str(uuid4()),
                        "risk_assessment_id": assessment_id,
                        "category": cat,
                        "severity": sev,
                        "score_contribution": float(sig.get("score_contribution", 0.0)),
                        "confidence": float(sig.get("confidence", 1.0)),
                        "source": src,
                        "evidence": sig.get("evidence", {}),
                        "status": sig.get("status", "OPEN")
                    })
                self.supabase_client.table("risk_signals").insert(sig_rows).execute()

            # 5. Update invoice status
            inv_st = "APPROVED" if decision_val == "APPROVE" else ("ESCALATED" if decision_val == "ESCALATE" else "BLOCKED")
            self.supabase_client.table("invoices").update({"status": inv_st, "updated_at": now_str}).eq("id", invoice_id).execute()

            return self.get_risk_assessment(assessment_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM risk_assessments WHERE invoice_id = ? AND is_current = 1 LIMIT 1", (invoice_id,))
        prev_row = cursor.fetchone()
        prev_id = assessment_data.get("previous_assessment_id") or (prev_row["id"] if prev_row else None)
        
        cursor.execute("UPDATE risk_assessments SET is_current = 0 WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("""
            INSERT INTO risk_assessments (id, invoice_id, previous_assessment_id, final_score, decision, decision_reason, forced_by_hard_rule, ai_evaluation_id, created_at, is_current)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            assessment_id, invoice_id, prev_id,
            assessment_data["final_score"], decision_val, assessment_data["decision_reason"],
            assessment_data.get("forced_by_hard_rule"), assessment_data.get("ai_evaluation_id"), now_str
        ))
        
        if assessment_data.get("ai_evaluation_id"):
            cursor.execute("UPDATE ai_evaluations SET assessment_id = ? WHERE id = ?", (assessment_id, assessment_data["ai_evaluation_id"]))
        
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
            decision_val, now_str, invoice_id
        ))
        conn.commit()
        conn.close()
        return self.get_risk_assessment(assessment_id)

    def get_latest_assessment(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("risk_assessments").select("*").eq("invoice_id", invoice_id).eq("is_current", True).limit(1).execute()
            if not res.data:
                return None
            return self.get_risk_assessment(res.data[0]["id"])

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM risk_assessments WHERE invoice_id = ? AND is_current = 1 LIMIT 1", (invoice_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return self.get_risk_assessment(row["id"])

    def get_risk_assessment(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("risk_assessments").select("*").eq("id", assessment_id).execute()
            if not res.data:
                return None
            assessment = res.data[0]
            sig_res = self.supabase_client.table("risk_signals").select("*").eq("risk_assessment_id", assessment_id).execute()
            assessment["signals"] = sig_res.data or []

            if assessment.get("ai_evaluation_id"):
                assessment["ai_evaluation"] = self.get_ai_evaluation(assessment["ai_evaluation_id"])
            else:
                assessment["ai_evaluation"] = None

            assessment["duplicates"] = []
            assessment["split_group"] = None
            assessment["compliance_checks"] = []
            return assessment

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
            
        conn.close()
        if res.get("ai_evaluation_id"):
            res["ai_evaluation"] = self.get_ai_evaluation(res["ai_evaluation_id"])
        else:
            res["ai_evaluation"] = None
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
        now_str = datetime.now(timezone.utc).isoformat()
        provider_val = eval_data.get("model_provider") or eval_data.get("provider_used") or eval_data.get("provider") or "GROQ"
        model_val = eval_data.get("model_version") or eval_data.get("model") or "llama-3.3-70b-versatile"

        if self.supabase_client:
            row = {
                "id": eval_id,
                "invoice_id": eval_data["invoice_id"],
                "request_context": eval_data.get("request_context", {}),
                "response_raw": eval_data.get("response_raw"),
                "response_validated": eval_data.get("response_validated") or eval_data.get("validated_output"),
                "dropped_hallucinated_factors": eval_data.get("dropped_hallucinated_factors", []),
                "status": eval_data.get("status", "SUCCESS"),
                "failure_reason": eval_data.get("failure_reason"),
                "model_provider": provider_val,
                "model_version": model_val,
                "latency_ms": eval_data.get("latency_ms", 0),
                "token_usage": eval_data.get("token_usage", {}),
                "correlation_id": eval_data.get("correlation_id") or str(uuid4()),
                "created_at": eval_data.get("created_at") or now_str
            }
            self.supabase_client.table("ai_evaluations").insert(row).execute()
            return eval_id

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_evaluations (
                id, invoice_id, assessment_id, request_context, response_raw, response_validated,
                validated_output, dropped_hallucinated_factors, status, failure_reason,
                model_provider, model_version, provider, provider_used, model,
                fallback_used, fallback_reason, requested_at, completed_at,
                latency_ms, token_usage, correlation_id, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            eval_id,
            eval_data["invoice_id"],
            eval_data.get("assessment_id"),
            json.dumps(eval_data.get("request_context", {})),
            json.dumps(eval_data.get("response_raw")) if eval_data.get("response_raw") is not None else None,
            json.dumps(eval_data.get("response_validated")) if eval_data.get("response_validated") is not None else None,
            json.dumps(eval_data.get("validated_output") or eval_data.get("response_validated")) if (eval_data.get("validated_output") or eval_data.get("response_validated")) is not None else None,
            json.dumps(eval_data.get("dropped_hallucinated_factors", [])),
            eval_data["status"],
            eval_data.get("failure_reason"),
            provider_val,
            model_val,
            provider_val,
            provider_val,
            model_val,
            1 if eval_data.get("fallback_used") else 0,
            eval_data.get("fallback_reason"),
            eval_data.get("requested_at") or now_str,
            eval_data.get("completed_at") or now_str,
            eval_data.get("latency_ms"),
            json.dumps(eval_data.get("token_usage", {})),
            eval_data.get("correlation_id", str(uuid4())),
            eval_data.get("created_at") or now_str
        ))
        conn.commit()
        conn.close()
        return eval_id

    def get_ai_evaluation(self, eval_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("ai_evaluations").select("*").eq("id", eval_id).execute()
            if not res.data:
                return None
            r = res.data[0]
            val_out = r.get("response_validated") or r.get("validated_output")
            r["validated_output"] = val_out
            r["response_validated"] = val_out
            r["fallback_used"] = False
            return r

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ai_evaluations WHERE id = ?", (eval_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        res = dict(row)
        res["request_context"] = json.loads(res["request_context"] or "{}")
        res["response_raw"] = json.loads(res["response_raw"]) if res.get("response_raw") else None
        val_out = res.get("validated_output") or res.get("response_validated")
        res["validated_output"] = json.loads(val_out) if val_out else None
        res["response_validated"] = res["validated_output"]
        res["dropped_hallucinated_factors"] = json.loads(res["dropped_hallucinated_factors"] or "[]")
        res["token_usage"] = json.loads(res["token_usage"] or "{}")
        res["fallback_used"] = bool(res.get("fallback_used", 0))
        return res

    def get_ai_evaluations_for_invoice(self, invoice_id: str) -> List[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("ai_evaluations").select("*").eq("invoice_id", invoice_id).order("created_at", desc=True).execute()
            out = []
            for r in (res.data or []):
                val_out = r.get("response_validated") or r.get("validated_output")
                r["validated_output"] = val_out
                r["response_validated"] = val_out
                r["fallback_used"] = False
                out.append(r)
            return out

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ai_evaluations WHERE invoice_id = ? ORDER BY created_at DESC", (invoice_id,))
        rows = cursor.fetchall()
        conn.close()
        return [self.get_ai_evaluation(r["id"]) for r in rows if r]

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
        inv_id = str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            existing = self.supabase_client.table("investigations").select("id").eq("invoice_id", invoice_id).in_("status", ["OPEN", "IN_REVIEW", "WAITING_FOR_INFORMATION"]).execute()
            if existing.data:
                return self.get_investigation(existing.data[0]["id"])
            row = {
                "id": inv_id,
                "invoice_id": invoice_id,
                "risk_assessment_id": risk_assessment_id,
                "status": "OPEN",
                "assigned_role_label": "FINANCE_MANAGER",
                "created_at": now_str
            }
            self.supabase_client.table("investigations").insert(row).execute()
            return self.get_investigation(inv_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM investigations WHERE invoice_id = ? AND status IN ('OPEN', 'IN_REVIEW', 'WAITING_FOR_INFORMATION')", (invoice_id,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return self.get_investigation(existing["id"])
            
        cursor.execute("""
            INSERT INTO investigations (id, invoice_id, risk_assessment_id, split_invoice_group_id, status, assigned_role_label, created_at)
            VALUES (?, ?, ?, ?, 'OPEN', 'FINANCE_MANAGER', ?)
        """, (inv_id, invoice_id, risk_assessment_id, split_group_id, now_str))
        conn.commit()
        conn.close()
        return self.get_investigation(inv_id)

    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase_client:
            res = self.supabase_client.table("investigations").select("*").eq("id", investigation_id).execute()
            if not res.data:
                return None
            inv = res.data[0]
            inv["comments"] = []
            return inv

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
        if self.supabase_client:
            res = self.supabase_client.table("investigations").select("id").eq("invoice_id", invoice_id).order("created_at", desc=True).limit(1).execute()
            if res.data:
                return self.get_investigation(res.data[0]["id"])
            return None

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

        if self.supabase_client:
            inv = self.get_investigation(investigation_id)
            if not inv:
                raise ValueError("Investigation not found")
            invoice_id = inv["invoice_id"]
            self.supabase_client.table("investigations").update({
                "status": "RESOLVED",
                "outcome": outcome,
                "outcome_rationale": rationale,
                "resolved_at": now_str
            }).eq("id", investigation_id).execute()

            if outcome == "APPROVED_AFTER_REVIEW":
                self.update_invoice_status(invoice_id, "APPROVED")
            elif outcome == "BLOCKED":
                self.update_invoice_status(invoice_id, "BLOCKED")
            elif outcome == "DUPLICATE_CONFIRMED":
                self.update_invoice_status(invoice_id, "REJECTED")

            return self.get_investigation(investigation_id)

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
        
        if outcome == "APPROVED_AFTER_REVIEW":
            app_id = str(uuid4())
            cursor.execute("""
                INSERT INTO approvals (id, invoice_id, investigation_id, status, approver_role_label, previous_decision, new_decision, reason, is_override, created_at)
                VALUES (?, ?, ?, 'APPROVED', ?, 'BLOCK/ESCALATE', 'APPROVED', ?, 1, ?)
            """, (app_id, invoice_id, investigation_id, actor_label, rationale, now_str))
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
            inv_row = self.get_invoice(inv_id)
            if not inv_row:
                continue
            total_val += inv_row["amount"]
            
            ass_row = self.get_latest_assessment(inv_id)
            snap_decision = ass_row["decision"] if ass_row else "APPROVE"
            snap_score = ass_row["final_score"] if ass_row else 0.0
            
            # Check readiness: APPROVE or (ESCALATE with approval)
            is_ready = False
            if snap_decision == "APPROVE":
                is_ready = True
            elif snap_decision == "ESCALATE":
                approvals = self.get_approvals_for_invoice(inv_id)
                if any(a["status"] == "APPROVED" for a in approvals):
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
        event_id = str(uuid4())
        corr_id = correlation_id or str(uuid4())
        now_str = datetime.now(timezone.utc).isoformat()

        if self.supabase_client:
            # 1. Fetch previous hash from Supabase
            try:
                res = self.supabase_client.table("audit_events").select("sequence_number, current_hash").order("sequence_number", desc=True).limit(1).execute()
                prev_hash = res.data[0]["current_hash"] if res.data else ("0" * 64)
            except Exception:
                prev_hash = "0" * 64

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

            row = {
                "id": event_id,
                "event_type": event_type,
                "occurred_at": now_str,
                "invoice_id": invoice_id,
                "vendor_id": vendor_id,
                "correlation_id": corr_id,
                "actor_label": actor_label,
                "decision": decision,
                "payload": payload,
                "previous_hash": prev_hash,
                "current_hash": cur_hash
            }
            ins = self.supabase_client.table("audit_events").insert(row).execute()
            seq = ins.data[0].get("sequence_number", 0) if ins.data else 0

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

        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT sequence_number, current_hash FROM audit_events ORDER BY sequence_number DESC LIMIT 1")
        last_row = cursor.fetchone()
        if last_row:
            prev_hash = last_row["current_hash"]
        else:
            prev_hash = "0" * 64
            
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
        if self.supabase_client:
            q = self.supabase_client.table("audit_events").select("*")
            if invoice_id:
                q = q.eq("invoice_id", invoice_id)
            res = q.order("sequence_number", desc=True).limit(limit).execute()
            out = []
            for r in (res.data or []):
                if isinstance(r.get("payload"), str):
                    try:
                        r["payload"] = json.loads(r["payload"])
                    except Exception:
                        pass
                out.append(r)
            return out

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
        if self.supabase_client:
            res = self.supabase_client.table("audit_events").select("*").order("sequence_number", desc=False).execute()
            rows = res.data or []
            if not rows:
                return {"valid": True, "rows_checked": 0, "first_broken_sequence": None}
            prev_hash = "0" * 64
            for r in rows:
                seq = r["sequence_number"]
                if r["previous_hash"] != prev_hash:
                    return {"valid": False, "rows_checked": seq, "first_broken_sequence": seq}
                pld = r.get("payload")
                if isinstance(pld, str):
                    try:
                        pld = json.loads(pld)
                    except Exception:
                        pass
                canonical_dict = {
                    "actor_label": r["actor_label"],
                    "correlation_id": r["correlation_id"],
                    "decision": r.get("decision"),
                    "event_type": r["event_type"],
                    "invoice_id": r.get("invoice_id"),
                    "occurred_at": r["occurred_at"],
                    "payload": pld,
                    "risk_score": r.get("risk_score")
                }
                canonical_str = json.dumps(canonical_dict, sort_keys=True)
                expected_hash = hashlib.sha256((canonical_str + prev_hash).encode()).hexdigest()
                if r["current_hash"] != expected_hash:
                    return {"valid": False, "rows_checked": seq, "first_broken_sequence": seq}
                prev_hash = r["current_hash"]
            return {"valid": True, "rows_checked": len(rows), "first_broken_sequence": None}

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
