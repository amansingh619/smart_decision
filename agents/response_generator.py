# agents/response_generator.py

import os
import json
import time
from typing import List
from huggingface_hub import InferenceClient
from schemas.intent import IntentOutput
from schemas.response import RankedProduct


class ResponseGenerator:
    """
    Generates user-friendly response from ranked products
    """
    
    def __init__(self, logger):
        self.model = os.getenv("HF_MODEL")
        self.logger = logger
        self.client = InferenceClient(
            api_key=os.getenv("HF_TOKEN")
        )
    
    def generate(self, ranked_products: List[RankedProduct], 
                 intent: IntentOutput, original_query: str) -> str:
        """Generate human-readable response"""
        
        if not ranked_products:
            return "No products found matching your criteria. Try adjusting your filters."
        
        try:
            return self._llm_generate(ranked_products, intent, original_query)
        except Exception as e:
            print(f"LLM response generation failed: {e}")
    
    def _llm_generate(
            self,        
            ranked_products: List[RankedProduct],         
            intent: IntentOutput, 
            query: str,
            max_retries: int = 3,
            base_delay: int = 2
        ) -> str:
        """Use LLM for natural response generation"""

        prompt = f"""Generate a helpful product recommendation response based on the data below.

            USER QUERY: "{query}"
            INTENT: {intent["primary_intent"]}
            RANKED PRODUCTS:
            {ranked_products}

            Generate a response that:
            1. Starts with the top recommendation
            2. Explains why it ranks #1 (mention specific metrics)
            3. Mentions any potential downsides
            4. Suggests 1-2 alternatives if available
            5. Uses emojis for visual appeal
            6. Keeps it concise but informative
            7. Mentions prices and key nutritional info

        """ 
        
        for attempt in range(1, max_retries + 1):

            try:

                self.logger.info(
                    f"LLM Output Generation attempt "
                    f"{attempt}/{max_retries}"
                )

                messages = [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

                response = self.client.chat.completions.create(
                    model="deepseek-ai/DeepSeek-V4-Flash",
                    messages=messages,
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from model")


                self.logger.info(
                    "Output generation completed successful"
                )
                return content

            except Exception as e:

                self.logger.warning(
                    f"LLM classification error "
                    f"(attempt {attempt}): {e}"
                )

                if attempt < max_retries:

                    sleep_time = (
                        base_delay * (2 ** (attempt - 1))
                    )

                    self.logger.info(
                        f"Retrying in {sleep_time:.1f} seconds..."
                    )

                    time.sleep(sleep_time)