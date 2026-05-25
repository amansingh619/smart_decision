# agents/response_generator.py

import os
from typing import List

from dotenv import load_dotenv
from openai import OpenAI
from schemas.intent import IntentOutput, QueryIntent
from schemas.response import PipelineResult, RankedProduct

load_dotenv()

class ResponseGenerator:
    """
    Generates user-friendly response from ranked products
    """
    
    def __init__(self, api_key: str = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    
    def generate(self, ranked_products: List[RankedProduct], 
                 intent: IntentOutput, original_query: str) -> str:
        """Generate human-readable response"""
        
        if not ranked_products:
            return "No products found matching your criteria. Try adjusting your filters."
        
        try:
            return self._llm_generate(ranked_products, intent, original_query)
        except Exception as e:
            print(f"LLM response generation failed: {e}")
            return self._rule_based_generate(ranked_products, intent)
    
    def _llm_generate(self, ranked_products: List[RankedProduct], 
                      intent: IntentOutput, query: str) -> str:
        """Use LLM for natural response generation"""
        
        # Build product summary for LLM
        products_text = self._format_products_for_llm(ranked_products[:5])
        
        prompt = f"""Generate a helpful product recommendation response based on the data below.

USER QUERY: "{query}"
INTENT: {intent.primary_intent.value}
RANKED PRODUCTS:
{products_text}

Generate a response that:
1. Starts with the top recommendation
2. Explains why it ranks #1 (mention specific metrics)
3. Mentions any potential downsides
4. Suggests 1-2 alternatives if available
5. Uses emojis for visual appeal
6. Keeps it concise but informative
7. Mentions prices and key nutritional info

Response:"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content
    
    def _format_products_for_llm(self, products: List[RankedProduct]) -> str:
        """Format products as text for LLM consumption"""
        lines = []
        for rp in products:
            p = rp.product
            n = p.nutrition
            lines.append(f"""
Rank #{rp.rank}: {p.brand_name} - {p.product_name}
Price: ₹{p.price} ({p.quantity or 'N/A'})
Score: {rp.composite_score}
{f"Calories: {n.calories_per_100g} per 100g" if n and n.calories_per_100g else ""}
{f"Protein: {n.protein_per_100g}g per 100g" if n and n.protein_per_100g else ""}
{f"Sugar: {n.added_sugar_per_100g}g added sugar" if n and n.added_sugar_per_100g is not None else ""}
{f"Diet: {', '.join(p.diet_preference)}" if p.diet_preference else ""}
{f"Flavour: {p.flavour}" if p.flavour else ""}
---""")
        return "\n".join(lines)
    
    def _rule_based_generate(self, products: List[RankedProduct], 
                            intent: IntentOutput) -> str:
        """Template-based response (fallback)"""
        if not products:
            return "No matching products found."
        
        top = products[0]
        p = top.product
        n = p.nutrition
        
        response = f"""
    Top Recommendation: {p.brand_name} {p.product_name}
    Price: ₹{p.price} ({p.quantity or 'N/A'})

Why it ranks #1:
"""
        if n:
            if n.calories_per_100g:
                response += f"• {n.calories_per_100g} calories per 100g\n"
            if n.protein_per_100g:
                response += f"• {n.protein_per_100g}g protein per 100g\n"
            if n.added_sugar_per_100g is not None:
                response += f"• {n.added_sugar_per_100g}g added sugar\n"
        
        if p.diet_preference:
            response += f"• Dietary: {', '.join(p.diet_preference)}\n"
        
        if len(products) > 1:
            alt = products[1]
            response += f"""
    Alternative: {alt.product.brand_name} {alt.product.product_name}
    Price: ₹{alt.product.price}
"""
        
        return response