
import json
import os
import re
import time

from openai import OpenAI
from openai import APIError, RateLimitError, APITimeoutError
from schemas.intent import (DietaryConstraint, IntentEntities, IntentOutput,
                            QueryIntent)


class IntentRouter:
    """
    Converts natural language query → structured IntentOutput
    Uses OpenAI with function calling for getting JSON output
    """
    
    def __init__(self, logger):
        self.logger = logger
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"  
        self.MAX_TOKEN_LIMIT=500
        self.LLM_TEMPERATURE=0.1
        self.LLM_OUTPUT_FORMAT={"type": "json_object"}
        
    def classify_intent(self, query: str) -> IntentOutput:
        """query string → IntentOutput"""
        try:
            return self.fetch_intent_from_llm(query)
        except Exception as e:
            self.logger.error(f"LLM intent classification failed: {e}")
            self.logger.error("Falling back to rule-based classification...")
            return self.rule_based_classify(query)
    
    def fetch_intent_from_llm(
        self,
        query: str,
        max_retries: int = 3,
        base_delay: int = 2
    ) -> IntentOutput:
        """
        Using ChatGPT for intent classification
        with retry + validation handling
        """

        for attempt in range(1, max_retries + 1):

            try:

                self.logger.info(
                    f"LLM intent classification attempt "
                    f"{attempt}/{max_retries}"
                )

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self.get_system_prompt()
                        },
                        {
                            "role": "user",
                            "content": f'User Query: "{query}"'
                        }
                    ],
                    response_format=self.LLM_OUTPUT_FORMAT,
                    temperature=self.LLM_TEMPERATURE,
                    max_tokens=self.MAX_TOKEN_LIMIT
                )

               
                content = response.choices[0].message.content

                if not content:
                    raise ValueError("Empty response from LLM")
                
                raw = json.loads(content)
                parsed_output = self.parse_llm_output(raw)

                self.logger.info(
                    "LLM intent classification successful"
                )
                return parsed_output

            except json.JSONDecodeError as e:

                self.logger.warning(
                    f"Invalid JSON response from LLM "
                    f"(attempt {attempt}): {e}"
                )

            except (
                RateLimitError,
                APITimeoutError,
                APIError
            ) as e:

                self.logger.warning(
                    f"OpenAI API error"
                    f"(attempt {attempt}): {e}"
                )

            except Exception as e:
                self.logger.warning(
                    f"Unexpected error during LLM classification "
                    f"(attempt {attempt}): {e}"
                )

            if attempt < max_retries:
                sleep_time = base_delay * (2 ** (attempt - 1))
                self.logger.info(
                    f"Retrying in {sleep_time:.1f} seconds..."
                )
                time.sleep(sleep_time)

    
    def parse_llm_output(self, raw: dict) -> IntentOutput:
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
    
    def rule_based_classify(self, query: str) -> IntentOutput:
        """
            Fallback rule-based classification if in 
            case we don't get succesful response from LLM
        """
        query_lower = query.lower()
        
        # Determining intent
        if any(w in query_lower for w in ["compare", "vs", "versus", "difference", "or"]):
            intent = QueryIntent.COMPARISON
        elif any(w in query_lower for w in ["diabetic", "weight loss", "health"]):
            intent = QueryIntent.GOAL_BASED
        elif any(w in query_lower for w in ["under", "below", "cheap", "budget", "within"]):
            intent = QueryIntent.BUDGET
        else:
            intent = QueryIntent.RECOMMENDATION
        
        # Extracting dietary constraints
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
        max_price = None
        price_match = re.search(r'(?:under|below|within)\s*(?:rs\.?|₹|inr)?\s*(\d+)', query_lower)
        if price_match:
            max_price = float(price_match.group(1))
        
        # Extract flavour
        flavours = ["vanilla", "chocolate", "strawberry", "tangy", "sour", "salty", "sweet"]
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
    
    def get_system_prompt(self) -> str:
        return """You are an intent classifier for an snacks & drinks category.

            INTENT TYPES:
            1. recommendation: User wants suggestions ("best", "top", "suggest", "recommend")
            2. comparison: Compare products ("compare", "vs", "difference", "X or Y")
            3. goal_based: Health driven ("diabetic", "weight loss", "keto", "protein")
            4. budget: Price constrained ("under 200", "cheap", "within budget", "upto")

            EXTRACT ENTITIES:
            If user wants an ice cream recommendation then we can include following entitie:s 
            - flavour: vanilla, chocolate, strawberry, mango
            - brand: Mother Dairy, Cream Bell, Amul, Havmor
            - dietary_constraints: sugar_free, low_calorie, high_protein, diabetic_friendly
            - max_price: extract number if price constraint mentioned
            - pack_type: tub, cup, stick, family_pack
            - sort_preference: price_low, price_high, calories_low, protein_high

            GENERATE SEARCH KEYWORDS:
            - Create 1 strong keyword for the scraper
            - You may include dietary requirements in keywords
            - Example: "low calorie ice cream" or "healthy snacks"

            OUTPUT VALID JSON ONLY:
            {
            "primary_intent": "recommendation",
            "secondary_intents": [],
            "entities": {
                "flavour": "vanilla",
                "brand": null,
                "dietary_constraints": [{"type": "sugar_free", "priority": "must_have"}],
                "max_price": 200,
                "min_price": 100,
                "pack_type": null,
                "sort_preference": "calories_low"
            },
            "confidence": 0.95,
            "requires_scraping": true,
            "requires_detail_scraping": true,
            "suggested_keywords": ["low calorie ice cream",],
            "clarification_question": null
            }
        IMPORTANT:
            - Output ONLY valid JSON
            - No markdown
            - No explanations
            - No extra text
    """