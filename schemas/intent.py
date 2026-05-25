# schemas/intent.py

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    RECOMMENDATION = "recommendation"
    COMPARISON = "comparison"
    GOAL_BASED = "goal_based"
    BUDGET = "budget"

class DietaryConstraint(BaseModel):
    type: str = Field(..., description="sugar_free, low_calorie, high_protein, diabetic_friendly, keto, vegan")
    priority: str = Field(default="must_have")

class IntentEntities(BaseModel):
    flavour: Optional[str] = None
    brand: Optional[str] = None
    dietary_constraints: List[DietaryConstraint] = Field(default_factory=list)
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    pack_type: Optional[str] = None
    sort_preference: Optional[str] = None
    comparison_targets: List[str] = Field(default_factory=list)
    raw_keywords: List[str] = Field(default_factory=list)

class IntentOutput(BaseModel):
    """FIXED SCHEMA: LLM must output this exact structure"""
    primary_intent: QueryIntent
    secondary_intents: List[QueryIntent] = Field(default_factory=list)
    entities: IntentEntities
    confidence: float = Field(ge=0.0, le=1.0)
    requires_scraping: bool = True
    requires_detail_scraping: bool = False
    suggested_keywords: List[str] = Field(default_factory=list)
    query_clarity: str = "clear"
    clarification_question: Optional[str] = None