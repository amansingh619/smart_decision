# tools/scraper_tool.py

import pandas as pd
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
                # Call YOUR existing spider
                raw_data = self.spider.fetch_search_products(
                    keyword=keyword,
                    pincode=int(pincode),
                    latitude=latitude,
                    longitude=longitude
                )
                
                # Convert to Product objects
                products = self._normalize_products(raw_data, keyword, pincode)
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
    
    def _normalize_products(self, raw_data: List[Dict], keyword: str, pincode: str) -> List[Product]:
        """
        Convert your spider's raw output to standardized Product objects
        """
        products = []
        
        for item in raw_data:
            try:
                # Extract nutrition info if available
                nutrition = None
                if item.get('Calories per 100g (Kcal)') or item.get('Protein Per 100 g (g)'):
                    nutrition = NutritionInfo(
                        calories_per_100g=self._safe_float(item.get('Calories per 100g (Kcal)')),
                        protein_per_100g=self._safe_float(item.get('Protein Per 100 g (g)')),
                        total_carbs_per_100g=self._safe_float(item.get('Total Carbohydrates Per 100 g (g)')),
                        total_sugar_per_100g=self._safe_float(item.get('Total Sugar Per 100 g (g)')),
                        added_sugar_per_100g=self._safe_float(item.get('Added Sugars Per 100 g (g)')),
                        total_fat_per_100g=self._safe_float(item.get('Total Fat Per 100 g (g)')),
                        saturated_fat_per_100g=self._safe_float(item.get('Saturated Fat Per 100 g (g)')),
                        cholesterol_per_100g_mg=self._safe_float(item.get('Cholesterol Per 100 g (g)')),
                        sodium_per_100g_mg=self._safe_float(item.get('Sodium Per 100 g (mg)')),
                        calcium_per_100g_g=self._safe_float(item.get('Calcium Per 100 g (g)')),
                        dietary_fiber_per_100g=self._safe_float(item.get('Dietary Fiber Per 100 g (g)'))
                    )
                
                # Parse diet preferences
                diet_pref = []
                if item.get('Diet Preference'):
                    diet_pref = [d.strip() for d in str(item['Diet Preference']).split(',')]
                
                # Parse key features
                key_features = []
                if item.get('Key Features'):
                    key_features = [f.strip() for f in str(item['Key Features']).split('\n') if f.strip()]
                
                product = Product(
                    product_id=str(item.get('product_id', '')),
                    product_name=str(item.get('product_name', '')),
                    brand_name=str(item.get('brand_name', '')),
                    product_url=str(item.get('product_url', '')),
                    product_type=item.get('product_type'),
                    mrp=float(item.get('mrp', 0)),
                    price=float(item.get('price', 0)),
                    discount=float(item.get('discount', '0').replace('%', '')),
                    quantity=item.get('quantity'),
                    unit=item.get('unit'),
                    availability=item.get('availibility'),
                    position=int(item.get('position', 0)),
                    growth=item.get('growth'),
                    key_features=key_features if key_features else None,
                    ingredients=item.get('Ingredients'),
                    nutrition=nutrition,
                    shelf_life=item.get('Shelf Life'),
                    sugar_profile=item.get('Sugar Profile'),
                    diet_preference=diet_pref if diet_pref else None,
                    flavour=item.get('Flavour') or item.get('Flavour Family'),
                    pack_type=item.get('Pack Type'),
                    description=item.get('Description'),
                    allergen_info=item.get('Allergen Information'),
                    pincode=pincode,
                    keyword=keyword,
                    scraped_at=datetime.now()
                )
                products.append(product)
                
            except Exception as e:
                self.logger.warning(f"   Could not normalize product {item.get('product_name', 'unknown')}: {e}")
        
        return products
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float"""
        if value is None or value == '' or value == '-':
            return None
        try:
            return float(str(value).replace(',', ''))
        except (ValueError, TypeError):
            return None