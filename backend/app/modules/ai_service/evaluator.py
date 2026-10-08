import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Optional, Tuple
from uuid import uuid4

from backend.app.config import settings
from backend.app.modules.ai_service.context_builder import build_ai_context
from backend.app.modules.ai_service.prompts import AI_SYSTEM_PROMPT, build_user_prompt
from backend.app.modules.ai_service.grounding import validate_and_ground_response
from backend.app.modules.ai_service.providers import AIRiskProvider, GroqRiskProvider, GeminiRiskProvider

class AIService:
    """
    Production-grade AI Layer with Groq as PRIMARY and Gemini as FALLBACK.
    Strictly follows:
    1. Dynamic context building from current DB state.
    2. Prompt injection defense isolating untrusted invoice text.
    3. Primary Groq invocation with retry.
    4. Fallback to Gemini on any Groq failure (timeout, network, malformed, grounding failure).
    5. Pure deterministic fallback (status='FAILED') if both fail - NO CANNED AI.
    6. Grounding enforcement dropping unsupported source IDs.
    """
    def __init__(
        self,
        groq_provider: Optional[AIRiskProvider] = None,
        gemini_provider: Optional[AIRiskProvider] = None,
        timeout_seconds: Optional[int] = None
    ):
        self._groq_provider = groq_provider
        self._gemini_provider = gemini_provider
        self.timeout_seconds = timeout_seconds or settings.ai_timeout_seconds

    def _get_groq_provider(self) -> Optional[AIRiskProvider]:
        if self._groq_provider is not None:
            return self._groq_provider
        if settings.groq_api_key:
            try:
                return GroqRiskProvider(
                    api_key=settings.groq_api_key,
                    model=settings.groq_model,
                    max_retries=settings.ai_max_retries
                )
            except Exception as e:
                print(f"[AIService] Failed to instantiate GroqRiskProvider: {e}")
        return None

    def _get_gemini_provider(self) -> Optional[AIRiskProvider]:
        if self._gemini_provider is not None:
            return self._gemini_provider
        if settings.gemini_api_key:
            try:
                return GeminiRiskProvider(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                    max_retries=settings.ai_max_retries
                )
            except Exception as e:
                print(f"[AIService] Failed to instantiate GeminiRiskProvider: {e}")
        return None

    def evaluate(
        self,
        context: Dict[str, Any],
        untrusted_text: str,
        valid_source_ids: Set[str],
        invoice_id: str,
        assessment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        correlation_id = str(uuid4())
        requested_at = datetime.now(timezone.utc).isoformat()
        start_time = time.time()
        
        user_prompt = build_user_prompt(context, untrusted_text)
        
        provider_used = "NONE"
        model_used = "NONE"
        fallback_used = False
        fallback_reason = None
        raw_response = None
        validated_output = None
        dropped_factors = []
        status = "FAILED"
        failure_reasons = []

        # ----------------------------------------------------
        # 1. PRIMARY: GROQ
        # ----------------------------------------------------
        groq = self._get_groq_provider()
        groq_succeeded = False
        
        if groq:
            try:
                raw_response = groq.evaluate(
                    system_prompt=AI_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    timeout_seconds=self.timeout_seconds
                )
                val_out, dropped, err = validate_and_ground_response(raw_response, valid_source_ids)
                if err:
                    groq_err_msg = f"Groq validation failed: {err}"
                    failure_reasons.append(groq_err_msg)
                    fallback_reason = groq_err_msg
                else:
                    validated_output = val_out
                    dropped_factors = dropped
                    provider_used = "GROQ"
                    model_used = getattr(groq, "model", None) or settings.groq_model
                    fallback_used = False
                    status = "SUCCESS"
                    groq_succeeded = True
            except Exception as e:
                groq_err_msg = f"Groq API error: {str(e)}"
                failure_reasons.append(groq_err_msg)
                fallback_reason = groq_err_msg
        else:
            fallback_reason = "Groq API key not configured or provider unavailable"
            failure_reasons.append(fallback_reason)

        # ----------------------------------------------------
        # 2. FALLBACK: GEMINI (Only if Groq failed)
        # ----------------------------------------------------
        if not groq_succeeded:
            gemini = self._get_gemini_provider()
            if gemini:
                try:
                    raw_response = gemini.evaluate(
                        system_prompt=AI_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        timeout_seconds=self.timeout_seconds
                    )
                    val_out, dropped, err = validate_and_ground_response(raw_response, valid_source_ids)
                    if err:
                        failure_reasons.append(f"Gemini validation failed: {err}")
                    else:
                        validated_output = val_out
                        dropped_factors = dropped
                        provider_used = "GEMINI"
                        model_used = getattr(gemini, "model", None) or settings.gemini_model
                        fallback_used = True
                        status = "SUCCESS"
                except Exception as e:
                    failure_reasons.append(f"Gemini API error: {str(e)}")
            else:
                failure_reasons.append("Gemini fallback provider not configured or unavailable")

        # ----------------------------------------------------
        # 3. BOTH FAILED: STRICT DETERMINISTIC (NO FAKE AI)
        # ----------------------------------------------------
        completed_at = datetime.now(timezone.utc).isoformat()
        latency_ms = int((time.time() - start_time) * 1000)

        eval_record = {
            "id": str(uuid4()),
            "invoice_id": invoice_id,
            "assessment_id": assessment_id,
            "request_context": context,
            "response_raw": raw_response,
            "response_validated": validated_output,
            "validated_output": validated_output,
            "dropped_hallucinated_factors": dropped_factors,
            "status": status,
            "failure_reason": "; ".join(failure_reasons) if status == "FAILED" else None,
            "provider": provider_used,
            "provider_used": provider_used,
            "model": model_used,
            "model_provider": provider_used,
            "model_version": model_used,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason if fallback_used else None,
            "requested_at": requested_at,
            "completed_at": completed_at,
            "latency_ms": latency_ms,
            "token_usage": {"prompt_tokens": len(user_prompt) // 4, "completion_tokens": 150 if status == "SUCCESS" else 0},
            "correlation_id": correlation_id,
            "created_at": completed_at
        }

        return eval_record


# Singleton instance for system usage
ai_service = AIService()

def evaluate_with_ai(
    invoice: Dict[str, Any],
    vendor: Dict[str, Any],
    trust_score: Dict[str, Any],
    signals: List[Dict[str, Any]],
    valid_source_ids: Optional[List[str]] = None,
    duplicate_matches: Optional[List[Dict[str, Any]]] = None,
    split_groups: Optional[List[Dict[str, Any]]] = None,
    pricing_signals: Optional[List[Dict[str, Any]]] = None,
    compliance_checks: Optional[List[Dict[str, Any]]] = None,
    assessment_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    High-level integration function maintaining backward compatibility with the Risk Firewall.
    Builds runtime context from current database state and executes Groq->Gemini AI pipeline.
    """
    context, untrusted_text, extracted_source_ids = build_ai_context(
        invoice=invoice,
        vendor=vendor,
        trust_score=trust_score,
        signals=signals,
        duplicate_matches=duplicate_matches,
        split_groups=split_groups,
        pricing_signals=pricing_signals,
        compliance_checks=compliance_checks
    )

    all_valid_ids = set(extracted_source_ids)
    if valid_source_ids:
        all_valid_ids.update([str(s).strip() for s in valid_source_ids if str(s).strip()])

    return ai_service.evaluate(
        context=context,
        untrusted_text=untrusted_text,
        valid_source_ids=all_valid_ids,
        invoice_id=invoice.get("id", ""),
        assessment_id=assessment_id
    )
