import base64
import gzip
import json
import random
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from smart_decision.spiders.blinkit_spider.common import Common


class Product(Common):
    """
    Class for Blinkit product page
    """
    def __init__(self, logger):
        super().__init__(logger)
        self.logger = logger

    def extract_data_from_zip_compressed(self, encoded_string):
        """Function to get JSON data from Gzip-compressed Base64 data"""
        filtered_data = [] 
        decoded_bytes = gzip.decompress(base64.b64decode(encoded_string))
        decoded_text = decoded_bytes.decode('utf-8', errors='ignore')

        # Parse the decoded text as JSON
        try:
            decoded_json = json.loads(decoded_text)
        except json.JSONDecodeError:
            return []

        snippets = decoded_json.get("response", {}).get("snippets", []) 
        for snippet in snippets:
            if snippet.get("widget_type") == "product_card_horizontal_snippet":
                filtered_data.append(snippet)
        
        return filtered_data


    def filter_compressed_products(self, snippet):
        """Function to filter the correct data"""
        type_list = []
        filtered_compressed_dict = []

        actions = snippet.get("data", {}).get("group_info", {}).get("actions", {}) 
        if actions:
            atc_actions = actions.get("atc_actions", {}).get("default", [])
            rfc_actions = actions.get("rfc_actions", {}).get("default", [])
            type_list.extend(rfc_actions)
            type_list.extend(atc_actions)

        for action in type_list:
            if action.get("type", "") == "open_variant_bottom_sheet_v2":
                encoded_value = (
                    action.get("open_variant_bottom_sheet_v2", {})
                    .get("response", {})
                    .get("data", {})
                    .get("encoded_value", "")
                )
                if encoded_value:
                    filtered_data = self.extract_data_from_zip_compressed(encoded_value)
                    if filtered_data:
                        # Extend to flatten the results (filtered_data is already a list)
                        filtered_compressed_dict.extend(filtered_data)
        return filtered_compressed_dict 

    def get_product_details(
        self,
        product_id,
        lat=None,
        lon=None,
        locality=None,
    ):
        """
        Function to get all the products details form a page
        """
        delay = random.uniform(1, 2)
        time.sleep(delay)

        full_url = f'https://api2.grofers.com/v1/layout/product/{product_id}'

        response_json = self.get_response(
            request_url=full_url,
            headers=self.get_headers(latitude=lat, longitude=lon),
            method="POST",
            data={},
        )

        product_details = []
        info_details = []

        try:
            snippets = response_json.get("response", {}).get("snippets", [])
            additional_details = response_json.get("response", {}).get("snippet_list_updater_data", {})

            if snippets:
                product_details.extend(snippets)

            if additional_details:
                for key, value in additional_details.items():
                    snippets_to_add = value.get("payload", {}).get("snippets_to_add", [])
                    for snippet in snippets_to_add:
                        if snippet.get("widget_type", "") == "cart_bill_item":
                            data = snippet.get("data", {})
                            info_details.append(data)

        except TypeError:
            return None

        all_sku_inventory = []

        temp = {}
        try:
            for product in product_details:
                if product.get("widget_type", "") == "text_right_icons_rating_snippet_type":
                    common_attribute = product.get("tracking", {}).get("common_attributes", {})

                    temp = {
                        "product_name": product.get("data", {}).get("title", {}).get("text", ""),
                        "product_id": common_attribute.get("product_id", ""),
                        "mrp": common_attribute.get("mrp", ""),
                        "price": common_attribute.get("price", ""),
                        "type": common_attribute.get("ptype", ""),
                    }
                    temp["discount"] = round(int((temp["mrp"]- temp["price"])/temp["mrp"]*100)) if temp["mrp"] else ""

                elif product.get("widget_type", "") == "crystal_snippet_type_6":
                    temp["brand_name"] = product.get("data", {}).get("title", {}).get("text", "")

            for details in info_details:
                text = details.get("left_header", {}).get("text", "")
                temp[text] = details.get("right_header", {}).get("text", "")

        except Exception as e:
            self.logger.error("Error occurred at get_all_brands function -> %s", e)

        all_sku_inventory.append(temp)
        self.logger.info(f"Scraped for {locality}: {product_id}")

        return all_sku_inventory

