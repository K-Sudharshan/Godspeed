import json
from typing import Dict, Any, List, Set, Tuple, Optional
from pydantic import ValidationError
from backend.app.modules.ai_service.schemas import AIEvaluationOutput, AIRiskFactor

def validate_and_ground_response(
    raw_response: Any,
    valid_source_ids: Set[str]
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """
    Executes complete grounding and anti-hallucination validation per Section 10:
    1. Parse JSON (handling potential Markdown wrapping).
    2. Validate Pydantic schema (validating enums, fields, and confidence ranges).
    3. Validate every source_id against the verified context.
    4. Drop any hallucinated or unsupported source IDs / risk factors.
    5. Returns (validated_output, dropped_hallucinated_factors, error_message).
    """
    # 1. Parse JSON
    if isinstance(raw_response, str):
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
        except Exception as e:
            return None, [], f"Malformed JSON from AI provider: {str(e)}"
    elif isinstance(raw_response, dict):
        parsed = raw_response
    else:
        return None, [], f"Unexpected response type: {type(raw_response).__name__}"

    # 2. Pydantic validation (enums, types, confidence bounds)
    try:
        model = AIEvaluationOutput.model_validate(parsed)
    except ValidationError as ve:
        return None, [], f"Schema validation failed: {str(ve)}"
    except Exception as e:
        return None, [], f"Validation error: {str(e)}"

    # 3. Grounding validation against valid context IDs
    allowed_ids = {str(s).strip() for s in valid_source_ids if str(s).strip()}
    grounded_factors: List[AIRiskFactor] = []
    dropped_factors: List[Dict[str, Any]] = []

    for factor in model.risk_factors:
        f_sources = [str(sid).strip() for sid in factor.source_ids if str(sid).strip()]
        
        # If factor has no source IDs or any source ID is ungrounded / hallucinated:
        if not f_sources:
            dropped_factors.append({
                "factor": factor.model_dump(),
                "reason": "Risk factor omitted source_ids; unsupported by context evidence"
            })
            continue

        invalid_ids = [sid for sid in f_sources if sid not in allowed_ids]
        if invalid_ids:
            dropped_factors.append({
                "factor": factor.model_dump(),
                "reason": f"Hallucinated / unverified source IDs: {invalid_ids}"
            })
            continue

        # All source IDs exist in verified context evidence
        grounded_factors.append(factor)

    validated_dict = {
        "risk_level": model.risk_level,
        "confidence": float(model.confidence),
        "recommended_decision": model.recommended_decision,
        "risk_factors": [gf.model_dump() for gf in grounded_factors],
        "reasoning_summary": model.reasoning_summary,
        "recommended_next_action": model.recommended_next_action,
        "risk_score": model.risk_score
    }

    return validated_dict, dropped_factors, None
