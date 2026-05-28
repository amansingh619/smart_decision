# schemas/product.py

from datetime import datetime
from typing import List, Optional, Any

from pydantic import BaseModel, Field


class NutritionInfo(BaseModel):
    """Matches your spider output exactly"""
    calories_per_100g: Optional[Any] = None
    protein_per_100g: Optional[Any] = None
    total_carbs_per_100g: Optional[Any] = None
    total_sugar_per_100g: Optional[Any] = None
    added_sugar_per_100g: Optional[Any] = None
    total_fat_per_100g: Optional[Any] = None
    saturated_fat_per_100g: Optional[Any] = None
    cholesterol_per_100g_mg: Optional[Any] = None
    sodium_per_100g_mg: Optional[Any] = None
    calcium_per_100g_g: Optional[Any] = None
    dietary_fiber_per_100g: Optional[Any] = None

class Product(BaseModel):
    """Matches your spider's output structure"""
    product_id: str  # Keep as str since IDs should always be strings
    product_name: str
    brand_name: str
    product_url: str
    product_type: Optional[Any] = None  
    mrp: Any
    price: Any
    discount: Any
    quantity: Optional[Any] = None 
    unit: Optional[Any] = None     
    availability: Optional[Any] = None
    position: Any  
    growth: Optional[Any] = None
    
    # PDP details
    key_features: Optional[Any] = None 
    ingredients: Optional[Any] = None  
    nutrition: Optional[NutritionInfo] = None
    shelf_life: Optional[Any] = None
    sugar_profile: Optional[Any] = None  # Was str, now Any (handles nan)
    diet_preference: Optional[Any] = None
    flavour: Optional[Any] = None
    pack_type: Optional[Any] = None  # Was str, now Any (handles nan)
    description: Optional[Any] = None  # Was str, now Any (handles nan)
    allergen_info: Optional[Any] = None  # Was str, now Any (handles nan)
    
    # Metadata
    pincode: str
    keyword: str
    scraped_at: Any  # Changed from datetime to Any to accept any format