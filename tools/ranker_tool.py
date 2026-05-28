# tools/ranker_tool.py

from typing import List, Optional

from schemas.intent import IntentOutput, QueryIntent
from schemas.product import NutritionInfo, Product
from schemas.response import RankedProduct


class RankerTool:
    """
    Ranks products based on intent and scoring criteria
    """
    
    def rank(self, products: List[Product], intent: IntentOutput, 
             top_n: int = 5) -> List[RankedProduct]:
        """
        Score and rank products based on intent type
        """
        if not products:
            return []
        
        scored = []
        
        for product in products:
            if not product.nutrition:
                # Products without nutrition data get neutral score
                scored.append(RankedProduct(
                    rank=0,
                    product=product,
                    composite_score=0.5,
                    score_breakdown={"no_nutrition_data": 0.5}
                ))
                continue
            
            # Calculate score based on intent
            score, breakdown = self._calculate_score(product, intent)
            
            scored.append(RankedProduct(
                rank=0,
                product=product,
                composite_score=score,
                score_breakdown=breakdown
            ))
        
        # Sort by score descending
        scored.sort(key=lambda x: x.composite_score, reverse=True)
        
        # Assign ranks
        for i, item in enumerate(scored[:top_n]):
            item.rank = i + 1
        
        return scored[:top_n]
    
    def _calculate_score(self, product: Product, intent: IntentOutput) -> tuple:
        """Calculate composite score based on intent"""
        n = product.nutrition
        breakdown = {}
        total_weight = 0
        total_score = 0
        
        # Get max values for normalization
        all_calories = [p.nutrition.calories_per_100g for p in [product] if p.nutrition and p.nutrition.calories_per_100g]
        all_proteins = [p.nutrition.protein_per_100g for p in [product] if p.nutrition and p.nutrition.protein_per_100g]
        
        if intent["primary_intent"] == QueryIntent.BUDGET:
            # Prioritize price and value
            if intent.entities.max_price:
                # Score price (lower is better)
                price_score = 1.0 - (product.price / intent.entities.max_price)
                price_score = max(0, min(1, price_score))
                breakdown["price_score"] = round(price_score, 3)
                total_score += price_score * 0.4
                total_weight += 0.4
            
            # Calories (lower is better)
            if n.calories_per_100g:
                cal_score = 1.0 - (n.calories_per_100g / 200)
                cal_score = max(0, min(1, cal_score))
                breakdown["calorie_score"] = round(cal_score, 3)
                total_score += cal_score * 0.3
                total_weight += 0.3
            
            # Protein (higher is better)
            if n.protein_per_100g:
                protein_score = min(1.0, n.protein_per_100g / 10)
                breakdown["protein_score"] = round(protein_score, 3)
                total_score += protein_score * 0.3
                total_weight += 0.3
        
        elif intent["primary_intent"] == QueryIntent.GOAL_BASED:
            # Check if diabetic friendly or weight loss
            constraints = [c.type for c in intent.entities.dietary_constraints]
            
            if "diabetic_friendly" in constraints or "sugar_free" in constraints:
                # Prioritize zero added sugar and low total sugar
                if n.added_sugar_per_100g is not None:
                    sugar_score = 1.0 if n.added_sugar_per_100g == 0 else 0.3
                    breakdown["sugar_score"] = round(sugar_score, 3)
                    total_score += sugar_score * 0.5
                    total_weight += 0.5
                
                # Low calories
                if n.calories_per_100g:
                    cal_score = 1.0 - (n.calories_per_100g / 200)
                    cal_score = max(0, min(1, cal_score))
                    breakdown["calorie_score"] = round(cal_score, 3)
                    total_score += cal_score * 0.5
                    total_weight += 0.5
            
            elif "low_calorie" in constraints or "weight_loss" in constraints:
                # Heavily weight calories
                if n.calories_per_100g:
                    cal_score = 1.0 - (n.calories_per_100g / 150)
                    cal_score = max(0, min(1, cal_score))
                    breakdown["calorie_score"] = round(cal_score, 3)
                    total_score += cal_score * 0.7
                    total_weight += 0.7
                
                if n.protein_per_100g:
                    protein_score = min(1.0, n.protein_per_100g / 10)
                    breakdown["protein_score"] = round(protein_score, 3)
                    total_score += protein_score * 0.3
                    total_weight += 0.3
        
        else:
            # Default recommendation: balance of healthy + affordable
            if n.calories_per_100g:
                cal_score = 1.0 - (n.calories_per_100g / 200)
                cal_score = max(0, min(1, cal_score))
                breakdown["calorie_score"] = round(cal_score, 3)
                total_score += cal_score * 0.35
                total_weight += 0.35
            
            if n.protein_per_100g:
                protein_score = min(1.0, n.protein_per_100g / 10)
                breakdown["protein_score"] = round(protein_score, 3)
                total_score += protein_score * 0.25
                total_weight += 0.25
            
            if n.added_sugar_per_100g is not None:
                sugar_score = 1.0 if n.added_sugar_per_100g == 0 else 0.5
                breakdown["sugar_score"] = round(sugar_score, 3)
                total_score += sugar_score * 0.2
                total_weight += 0.2
            
            # Price score
            price_score = 1.0 - (product.price / 300)  # Normalize to ₹300
            price_score = max(0, min(1, price_score))
            breakdown["price_score"] = round(price_score, 3)
            total_score += price_score * 0.2
            total_weight += 0.2
        
        # Calculate final weighted score
        final_score = total_score / total_weight if total_weight > 0 else 0.5
        return round(final_score, 3), breakdown