# schemas/response.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .intent import IntentOutput
from .product import Product


class RankedProduct(BaseModel):
    rank: int
    product: Product
    composite_score: float
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    reasoning_tokens: List[str] = Field(default_factory=list)

class PipelineResult(BaseModel):
    query_id: str
    original_query: str
    pincode: str
    intent: IntentOutput
    products_scraped: int
    products_filtered: int
    ranked_products: List[RankedProduct] = Field(default_factory=list)
    response_text: str
    execution_time_seconds: float
    errors: List[str] = Field(default_factory=list)
    completed_at: datetime