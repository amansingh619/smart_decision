# tools/scraper_tool.py

import pandas as pd
import re
from typing import List, Dict, Any
from datetime import datetime
from schemas.product import Product, NutritionInfo

class ScraperTool:
    """
    Wraps your BlinkitSpider to work as an agent tool.
    Input: keywords, pincode → Output: List[Product]
    """
    
    def __init__(self, spider_instance, logger):
        self.spider = spider_instance
        self.logger = logger
    
    def execute(self, keywords: List[str], pincode: str, 
                latitude: str = '26.9059311', 
                longitude: str = '75.78443829999999',
                fetch_details: bool = True) -> List[Product]:
        """
        Execute scraper with multiple keywords
        Returns deduplicated, structured Product objects
        """
        all_products = []
        
        for keyword in keywords:
            self.logger.info(f"Scraping keyword: '{keyword}' for pincode {pincode}")
            
            try:
                # calling the spider
                raw_data = self.spider.fetch_search_products(
                    keyword=keyword,
                    pincode=int(pincode),
                    latitude=latitude,
                    longitude=longitude
                )
                raw_data_df = pd.DataFrame(raw_data)
                # Convert to Product objects
                products = self._normalize_products(raw_data_df, keyword, pincode)
                all_products.extend(products)
                
                self.logger.info(f"   Found {len(products)} products")
                
            except Exception as e:
                self.logger.error(f"   Error scraping '{keyword}': {e}")
        
        # Deduplicate by product_id
        seen_ids = set()
        unique_products = []
        for product in all_products:
            if product.product_id not in seen_ids:
                seen_ids.add(product.product_id)
                unique_products.append(product)
        
        self.logger.info(f"Total unique products: {len(unique_products)}")
        return unique_products
    
    @staticmethod
    def parse_nutrition_value(value):
        """
        Examples:
        '148 kcal' -> 148.0
        '4.6 g' -> 4.6
        '20 mg' -> 20.0
        '0 g' -> 0.0
        None -> None
        NaN -> None
        """
        
        if pd.isna(value):
            return None

        value = str(value).strip()

        match = re.search(r"[-+]?\d*\.?\d+", value)

        if match:
            return float(match.group())

        return None
    
    def _normalize_products(
        self,
        raw_data: pd.DataFrame,
        keyword: str,
        pincode: str
    ) -> List[Product]:
        """
        Convert DataFrame rows to standardized Product objects.
        """

        products = []

        for item in raw_data.to_dict("records"):

            try:

                nutrition = None

                nutrition_fields = [
                    "Calories per 100g (Kcal)",
                    "Protein Per 100 g (g)",
                    "Total Carbohydrates Per 100 g (g)",
                    "Total Sugar Per 100 g (g)",
                    "Added Sugars Per 100 g (g)",
                    "Total Fat Per 100 g (g)",
                    "Saturated Fat Per 100 g (g)",
                    "Cholesterol Per 100 g (g)",
                    "Sodium Per 100 g (mg)",
                    "Calcium Per 100 g (g)",
                    "Dietary Fiber Per 100 g (g)"
                ]

                if any(pd.notna(item.get(field)) for field in nutrition_fields):
                    nutrition = NutritionInfo(
                        calories_per_100g=self.parse_nutrition_value(
                            item.get("Calories per 100g (Kcal)")
                        ),
                        protein_per_100g=self.parse_nutrition_value(
                            item.get("Protein Per 100 g (g)")
                        ),
                        total_carbs_per_100g=self.parse_nutrition_value(
                            item.get("Total Carbohydrates Per 100 g (g)")
                        ),
                        total_sugar_per_100g=self.parse_nutrition_value(
                            item.get("Total Sugar Per 100 g (g)")
                        ),
                        added_sugar_per_100g=self.parse_nutrition_value(
                            item.get("Added Sugars Per 100 g (g)")
                        ),
                        total_fat_per_100g=self.parse_nutrition_value(
                            item.get("Total Fat Per 100 g (g)")
                        ),
                        saturated_fat_per_100g=self.parse_nutrition_value(
                            item.get("Saturated Fat Per 100 g (g)")
                        ),
                        cholesterol_per_100g_mg=self.parse_nutrition_value(
                            item.get("Cholesterol Per 100 g (g)")
                        ),
                        sodium_per_100g_mg=self.parse_nutrition_value(
                            item.get("Sodium Per 100 g (mg)")
                        ),
                        calcium_per_100g_g=self.parse_nutrition_value(
                            item.get("Calcium Per 100 g (g)")
                        ),
                        dietary_fiber_per_100g=self.parse_nutrition_value(
                            item.get("Dietary Fiber Per 100 g (g)")
                        )
                    )

                diet_pref = None

                if pd.notna(item.get("Diet Preference")):
                    diet_pref = [
                        d.strip()
                        for d in str(item.get("Diet Preference")).split(",")
                        if d.strip()
                    ]

                key_features = None

                if pd.notna(item.get("Key Features")):
                    key_features = [
                        feature.strip()
                        for feature in str(item.get("Key Features")).split("\n")
                        if feature.strip()
                    ]

                discount = item.get("discount")

                if pd.notna(discount):
                    discount = str(discount).replace("%", "")
                else:
                    discount = None

                product = Product(

                    product_id=(
                        str(item.get("product_id"))
                        if pd.notna(item.get("product_id"))
                        else None
                    ),

                    product_name=item.get("product_name"),

                    brand_name=item.get("brand_name"),

                    product_url=item.get("product_url"),

                    product_type=item.get("product_type"),

                    mrp=item.get("mrp"),

                    price=item.get("price"),

                    discount=discount,

                    quantity=item.get("quantity"),

                    unit=item.get("unit"),

                    availability=item.get("availibility"),

                    position=item.get("position"),

                    growth=item.get("growth"),

                    key_features=key_features,

                    ingredients=item.get("Ingredients"),

                    nutrition=nutrition,

                    shelf_life=item.get("Shelf Life"),

                    sugar_profile=item.get("Sugar Profile"),

                    diet_preference=diet_pref,

                    flavour=(
                        item.get("Flavour")
                        if pd.notna(item.get("Flavour"))
                        else item.get("Flavour Family")
                    ),

                    pack_type=item.get("Pack Type"),

                    description=item.get("Description"),

                    allergen_info=item.get("Allergen Information"),

                    pincode=pincode,

                    keyword=keyword,

                    scraped_at=datetime.now()
                )

                products.append(product)

            except Exception as e:

                self.logger.warning(
                    f"Could not normalize product "
                    f"{item.get('product_name', 'unknown')}: {e}"
                )

        return products
