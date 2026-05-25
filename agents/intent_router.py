# agents/intent_router.py

import json
import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from schemas.intent import (DietaryConstraint, IntentEntities, IntentOutput,
                            QueryIntent)

load_dotenv()

class IntentRouter:
    """
    Converts natural language query → structured IntentOutput
    Uses OpenAI with function calling for reliable JSON output
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  # Fast and cheap for intent classification
        
    def classify(self, query: str, pincode: str = "302006") -> IntentOutput:
        """Main method: query string → IntentOutput"""
        
        try:
            return self._llm_classify(query)
        except Exception as e:
            print(f" LLM intent classification failed: {e}")
            print(" Falling back to rule-based classification...")
            return self._rule_based_classify(query)
    
    def _llm_classify(self, query: str) -> IntentOutput:
        """Use OpenAI for intent classification"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": f'User Query: "{query}"'}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=500
        )
        
        raw = json.loads(response.choices[0].message.content)
        return self._parse_llm_output(raw)
    
    def _parse_llm_output(self, raw: dict) -> IntentOutput:
        """Parse and validate LLM JSON output"""
        
        # Convert dietary constraints
        dietary_constraints = []
        for d in raw.get("entities", {}).get("dietary_constraints", []):
            dietary_constraints.append(DietaryConstraint(**d))
        
        # Convert entities
        entities = IntentEntities(
            flavour=raw.get("entities", {}).get("flavour"),
            brand=raw.get("entities", {}).get("brand"),
            dietary_constraints=dietary_constraints,
            max_price=raw.get("entities", {}).get("max_price"),
            min_price=raw.get("entities", {}).get("min_price"),
            pack_type=raw.get("entities", {}).get("pack_type"),
            sort_preference=raw.get("entities", {}).get("sort_preference"),
            raw_keywords=[query.strip() for query in raw.get("entities", {}).get("raw_keywords", [])]
        )
        
        return IntentOutput(
            primary_intent=raw["primary_intent"],
            secondary_intents=raw.get("secondary_intents", []),
            entities=entities,
            confidence=raw.get("confidence", 0.8),
            requires_scraping=raw.get("requires_scraping", True),
            requires_detail_scraping=raw.get("requires_detail_scraping", False),
            suggested_keywords=raw.get("suggested_keywords", [raw.get("entities", {}).get("raw_keywords", [query])]),
            query_clarity=raw.get("query_clarity", "clear"),
            clarification_question=raw.get("clarification_question")
        )
    
    def _rule_based_classify(self, query: str) -> IntentOutput:
        """Fallback rule-based classification (no LLM needed)"""
        query_lower = query.lower()
        
        # Determine intent
        if any(w in query_lower for w in ["compare", "vs", "versus", "difference", "or"]):
            intent = QueryIntent.COMPARISON
        elif any(w in query_lower for w in ["diabetic", "weight loss", "keto", "health"]):
            intent = QueryIntent.GOAL_BASED
        elif any(w in query_lower for w in ["under", "below", "cheap", "budget", "within"]):
            intent = QueryIntent.BUDGET
        else:
            intent = QueryIntent.RECOMMENDATION
        
        # Extract dietary constraints
        dietary = []
        if any(w in query_lower for w in ["sugar free", "no sugar", "sugarless"]):
            dietary.append(DietaryConstraint(type="sugar_free"))
        if any(w in query_lower for w in ["low calorie", "low cal"]):
            dietary.append(DietaryConstraint(type="low_calorie"))
        if "protein" in query_lower:
            dietary.append(DietaryConstraint(type="high_protein"))
        if "diabetic" in query_lower:
            dietary.append(DietaryConstraint(type="diabetic_friendly"))
        
        # Extract price
        import re
        max_price = None
        price_match = re.search(r'(?:under|below|within)\s*(?:rs\.?|₹|inr)?\s*(\d+)', query_lower)
        if price_match:
            max_price = float(price_match.group(1))
        
        # Extract flavour
        flavours = ["vanilla", "chocolate", "strawberry", "mango", "butterscotch", "kesar", "jamun"]
        flavour = None
        for f in flavours:
            if f in query_lower:
                flavour = f
                break
        
        return IntentOutput(
            primary_intent=intent,
            entities=IntentEntities(
                flavour=flavour,
                dietary_constraints=dietary,
                max_price=max_price,
                raw_keywords=[query]
            ),
            confidence=0.5,
            suggested_keywords=[query],
            query_clarity="clear"
        )
    
    def _get_system_prompt(self) -> str:
        return """You are an intent classifier for an ice cream recommendation system.

            INTENT TYPES:
            1. recommendation: User wants suggestions ("best", "top", "suggest", "recommend")
            2. comparison: Compare products ("compare", "vs", "difference", "X or Y")
            3. goal_based: Health driven ("diabetic", "weight loss", "keto", "protein")
            4. budget: Price constrained ("under 200", "cheap", "within budget")

            EXTRACT THESE ENTITIES:
            - flavour: vanilla, chocolate, strawberry, mango, butterscotch, shahi meva, kesar, jamun
            - brand: Mother Dairy, Cream Bell, Go Zero, Amul, Halo Top, Havmor
            - dietary_constraints: sugar_free, low_calorie, high_protein, diabetic_friendly
            - max_price: extract number if price constraint mentioned
            - pack_type: tub, cup, stick, family_pack
            - sort_preference: price_low, price_high, calories_low, protein_high

            GENERATE SEARCH KEYWORDS:
            - Create 2-3 keyword variations for the scraper
            - Include dietary requirements in keywords
            - Example: "low calorie ice cream" → ["low calorie ice cream", "sugar free ice cream", "healthy ice cream"]

            OUTPUT VALID JSON ONLY:
            {
            "primary_intent": "recommendation",
            "secondary_intents": [],
            "entities": {
                "flavour": "vanilla",
                "brand": null,
                "dietary_constraints": [{"type": "sugar_free", "priority": "must_have"}],
                "max_price": 200,
                "pack_type": null,
                "sort_preference": "calories_low"
            },
            "confidence": 0.95,
            "requires_scraping": true,
            "requires_detail_scraping": true,
            "suggested_keywords": ["sugar free vanilla ice cream", "low calorie vanilla ice cream", "healthy vanilla ice cream"],
            "query_clarity": "clear",
            "clarification_question": null
            }"""