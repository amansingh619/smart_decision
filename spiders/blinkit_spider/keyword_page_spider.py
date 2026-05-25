"""
Scraper for Blinkit
"""
import datetime
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).parent.parent))
from smart_decision.spiders.blinkit_spider.common import Common
from smart_decision.spiders.blinkit_spider.product_page_spider import Product


class BlinkitSpider(Common):
    """Class for Blinkit Scraper"""

    def __init__(self, logger):
        self.logger = logger
        super().__init__(logger)
        self.base_url = "https://api2.grofers.com"
        self.keyword_page_api = "https://api2.grofers.com/v1/layout/search"
        self.product_spider = Product(logger)

    def fetch_search_products(
        self,
        keyword,
        pincode=302006,
        latitude=None,
        longitude=None,
    ):
        """
        Fetch all products for a keyword from the search page,
        enrich each with product-page details, and return a list
        of dicts containing every distinct key-value pair found
        across both sources.
        """
        current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        headers = self.get_headers(latitude, longitude)
        all_products = []
        page_number = 0

        params = {
            "q": f"{keyword}",
            "search_type": "type_to_search",
        }
        encoded_params = urlencode(params)
        full_url = f"{self.keyword_page_api}?{encoded_params}"

        # Fetching data upto 2 pages
        while page_number < 2:
            response_json = self.get_response(
                request_url=full_url,
                headers=headers,
                data={},
                method="POST",
            )
            try:
                snippets = response_json.get("response", {}).get("snippets", [])
                for snippet in snippets:
                    if snippet.get("widget_type") == "product_card_type_unbounded_v2":
                        all_products.append(snippet)

                next_url = (
                    response_json.get("response", {})
                    .get("pagination", {})
                    .get("next_url", "")
                )
                page_number += 1
                if next_url and page_number < 2:
                    full_url = self.base_url + next_url
                else:
                    break
            except TypeError:
                return (None, None)

        # Parsing the data for each product
        all_products_detailed = []
        try:
            for product in all_products:
                raw_data = product
                product_data = product.get("data", {})

                # Resolve pack_size from stepper actions
                pack_size = None
                stepper = product_data.get("cta_data", {}).get("stepper", {})
                increment_actions = stepper.get("increment_actions", {}).get("default", [])
                decrement_actions = stepper.get("decrement_actions", {}).get("default", [])

                for action in increment_actions + decrement_actions:
                    if action.get("type") == "add_to_cart":
                        pack_size = (
                            action.get("add_to_cart", {})
                            .get("cart_item", {})
                            .get("unit", "")
                        )
                    elif action.get("type") == "remove_from_cart":
                        pack_size = (
                            action.get("remove_from_cart", {})
                            .get("cart_item", {})
                            .get("unit", "")
                        )

                if not product_data.get("product_id", ""):
                    continue

                product_common_attributes = raw_data.get("tracking", {}).get(
                    "common_attributes", {}
                )
                in_organic_check = product_common_attributes.get("product_state", "")
                position = product_common_attributes.get("product_position", "")

                # Base dict from search page
                temp = {
                    "pincode": pincode,
                    "key_word": keyword,
                    "date_time": current_timestamp,
                    "brand_name": product_common_attributes.get("brand", ""),
                    "product_name": product_common_attributes.get("name", ""),
                    "product_id": product_data.get("product_id", ""),
                    "product_url": f"https://blinkit.com/prn/_/prid/{product_data['product_id']}",
                    "position": position,
                    "growth": (
                        "In-organic" if in_organic_check == "AD_PRODUCT" else "Organic"
                    ),
                    "quantity": product_common_attributes.get("inventory", ""),
                    "availibility": (
                        1
                        if int(product_common_attributes.get("inventory", 0)) > 0
                        else 0
                    ),
                    "mrp": product_common_attributes.get("mrp", ""),
                    "price": product_common_attributes.get("price", ""),
                    "Unit": pack_size,
                    "type": product_common_attributes.get("ptype", ""),
                }
                temp["discount"] = round(int((temp["mrp"]- temp["price"])/temp["mrp"]*100)) if temp["mrp"] else ""

                # extending product-page details 
                product_id = temp["product_id"]
                try:
                    result = self.product_spider.get_product_details(
                        product_id=product_id,
                        lat=latitude,
                        lon=longitude,
                        locality=str(pincode),
                    )
                    if result is not None:
                        sku_list= result[0]
                        if sku_list:
                            product_page_data = sku_list

                            # Merge: search-page values win on key conflicts
                            for key, value in product_page_data.items():
                                if key not in temp or temp[key] in ("", None):
                                    temp[key] = value

                except Exception as e:
                    self.logger.warning(
                        f"Could not fetch product page for {product_id}: {e}"
                    )

                all_products_detailed.append(temp)

        except Exception as e:
            self.logger.error(f"Error occurred while filtering json data: {e}")

        return all_products_detailed