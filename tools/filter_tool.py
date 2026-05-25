# tools/filter_tool.py

from typing import List
from schemas.product import Product
from schemas.intent import IntentOutput, QueryIntent

class FilterTool:
    """
    Filters products based on intent entities
    """
    
    def filter(self, products: List[Product], intent: IntentOutput) -> List[Product]:
        """Apply all relevant filters"""
        filtered = products
        
        # Price filter
        if intent.entities.max_price:
            before = len(filtered)
            filtered = [p for p in filtered if p.price <= intent.entities.max_price]
            print(f"Price filter (≤₹{intent.entities.max_price}): {before} → {len(filtered)} products")
        
        # Dietary filter
        if intent.entities.dietary_constraints:
            for constraint in intent.entities.dietary_constraints:
                before = len(filtered)
                filtered = self._filter_by_dietary(filtered, constraint.type)
                print(f"Dietary filter ({constraint.type}): {before} → {len(filtered)} products")
        
        # Flavour filter
        if intent.entities.flavour:
            before = len(filtered)
            filtered = [p for p in filtered 
                       if p.flavour and intent.entities.flavour.lower() in p.flavour.lower()]
            print(f"Flavour filter ({intent.entities.flavour}): {before} → {len(filtered)} products")
        
        # Brand filter
        if intent.entities.brand:
            before = len(filtered)
            filtered = [p for p in filtered 
                       if intent.entities.brand.lower() in p.brand_name.lower()]
            print(f"Brand filter ({intent.entities.brand}): {before} → {len(filtered)} products")
        
        # Pack type filter
        if intent.entities.pack_type:
            before = len(filtered)
            filtered = [p for p in filtered 
                       if p.pack_type and intent.entities.pack_type.lower() in p.pack_type.lower()]
            print(f"Pack type filter ({intent.entities.pack_type}): {before} → {len(filtered)} products")
        
        return filtered
    
    def _filter_by_dietary(self, products: List[Product], constraint: str) -> List[Product]:
        """Apply dietary constraint filter"""
        constraint_lower = constraint.lower()
        
        if constraint_lower == "sugar_free":
            return [p for p in products if (
                (p.sugar_profile and "no added sugar" in p.sugar_profile.lower()) or
                (p.nutrition and p.nutrition.added_sugar_per_100g is not None and p.nutrition.added_sugar_per_100g == 0) or
                (p.diet_preference and any("sugar" in d.lower() for d in p.diet_preference))
            )]
        
        elif constraint_lower == "low_calorie":
            return [p for p in products if (
                (p.diet_preference and any("low calorie" in d.lower() for d in p.diet_preference)) or
                (p.nutrition and p.nutrition.calories_per_100g and p.nutrition.calories_per_100g < 100)
            )]
        
        elif constraint_lower == "high_protein":
            return [p for p in products if (
                (p.nutrition and p.nutrition.protein_per_100g and p.nutrition.protein_per_100g >= 5) or
                (p.diet_preference and any("protein" in d.lower() for d in p.diet_preference))
            )]
        
        elif constraint_lower == "diabetic_friendly":
            return [p for p in products if (
                (p.sugar_profile and "no added sugar" in p.sugar_profile.lower()) or
                (p.nutrition and p.nutrition.added_sugar_per_100g is not None and p.nutrition.added_sugar_per_100g == 0)
            )]
        
        return products  # Unknown constraint, return all