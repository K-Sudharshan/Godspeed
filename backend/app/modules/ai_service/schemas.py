from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

RiskFactorCategory = Literal[
    "DUPLICATE",
    "PRICING",
    "VENDOR",
    "COMPLIANCE",
    "SPLIT_INVOICE",
    "BANK_CHANGE",
    "DATA_QUALITY"
]

RiskSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

DecisionRecommendation = Literal["APPROVE", "ESCALATE", "BLOCK"]

class AIRiskFactor(BaseModel):
    category: RiskFactorCategory
    severity: RiskSeverity
    explanation: str
    source_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

class AIEvaluationOutput(BaseModel):
    risk_level: RiskSeverity
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    recommended_decision: DecisionRecommendation
    risk_factors: List[AIRiskFactor] = Field(default_factory=list)
    reasoning_summary: str
    recommended_next_action: str
    risk_score: Optional[float] = None
