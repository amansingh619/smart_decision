# schemas/product.py

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class NutritionInfo(BaseModel):
    """Matches your spider output exactly"""
    calories_per_100g: Optional[float] = None
    protein_per_100g: Optional[float] = None
    total_carbs_per_100g: Optional[float] = None
    total_sugar_per_100g: Optional[float] = None
    added_sugar_per_100g: Optional[float] = None
    total_fat_per_100g: Optional[float] = None
    saturated_fat_per_100g: Optional[float] = None
    cholesterol_per_100g_mg: Optional[float] = None
    sodium_per_100g_mg: Optional[float] = None
    calcium_per_100g_g: Optional[float] = None
    dietary_fiber_per_100g: Optional[float] = None

class Product(BaseModel):
    """Matches your spider's output structure"""
    product_id: str
    product_name: str
    brand_name: str
    product_url: str
    product_type: Optional[str] = None
    mrp: float
    price: float
    discount: float
    quantity: Optional[str] = None
    unit: Optional[str] = None
    availability: Optional[str] = None
    position: int
    growth: Optional[str] = None
    
    # PDP details
    key_features: Optional[List[str]] = None
    ingredients: Optional[str] = None
    nutrition: Optional[NutritionInfo] = None
    shelf_life: Optional[str] = None
    sugar_profile: Optional[str] = None
    diet_preference: Optional[List[str]] = None
    flavour: Optional[str] = None
    pack_type: Optional[str] = None
    description: Optional[str] = None
    allergen_info: Optional[str] = None
    
    # Metadata
    pincode: str
    keyword: str
    scraped_at: datetime