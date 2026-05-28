from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, List, Any

from pydantic import BaseModel, Field

class QueryIntent(str, Enum):
    RECOMMENDATION = "recommendation"
    BUDGET         = "budget"
    GOAL_BASED     = "goal_based"
    COMPARISON     = "comparison"

IntentOutput = Dict[str, Any]


# Execution plan schema

class ToolName(str, Enum):
    KEYWORD_SCRAPER        = "keyword_scraper"
    PRODUCT_DETAIL_SCRAPER = "product_detail_scraper"
    PRICE_FILTER           = "price_filter"
    DIETARY_FILTER         = "dietary_filter"
    FLAVOUR_FILTER         = "flavour_filter"
    BRAND_FILTER           = "brand_filter"
    NUTRITION_RANKER       = "nutrition_ranker"
    PRICE_RANKER           = "price_ranker"
    COMPOSITE_RANKER       = "composite_ranker"
    COMPARISON_ENGINE      = "comparison_engine"
    RESPONSE_GENERATOR     = "response_generator"


class StepStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    FAILED      = "failed"
    SKIPPED     = "skipped"


class PlanStep(BaseModel):
    step_id:          int
    tool:             ToolName
    description:      str
    params:           Dict[str, Any]       = Field(default_factory=dict)
    depends_on:       List[int]            = Field(default_factory=list)
    save_output_as:   str
    retry_on_failure: bool                 = False
    max_retries:      int                  = 1
    fallback_step:    Optional[int]        = None
    status:           StepStatus           = StepStatus.PENDING
    reasoning:        str                  = ""


class ExecutionPlan(BaseModel):
    plan_id:           str
    query:             str
    intent:            IntentOutput
    steps:             List[PlanStep]
    created_at:        str                 = Field(
                           default_factory=lambda: datetime.now(timezone.utc).isoformat()
                       )
    estimated_time_s:  float               = 0.0
    total_steps:       int                 = 0
    requires_scraping: bool                = False
    requires_ranking:  bool                = False

    def get_pending_steps(self) -> List[PlanStep]:
        """Steps whose dependencies are all completed — safe to execute (possibly in parallel)."""
        completed_ids = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}
        return [
            s for s in self.steps
            if s.status == StepStatus.PENDING
            and all(dep in completed_ids for dep in s.depends_on)
        ]

    def get_step(self, step_id: int) -> Optional[PlanStep]:
        return next((s for s in self.steps if s.step_id == step_id), None)