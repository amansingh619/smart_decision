import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import random
import os
import json
import warnings
from urllib.parse import urlencode
import time
import uuid
from dotenv import load_dotenv
from pathlib import Path
import uuid
import gzip
import base64


warnings.filterwarnings("ignore")
env_path = Path(__file__).parent / ".env.Development"
load_dotenv(env_path)
from scrapers.blinkit_mobile.base import Base


class Product(Base):
    """
    Class for Blinkit Scraper

    Attributes:
        url (str): url of the product page
        driver (WebDriver): Selenium WebDriver instance
        market_place_id (str): unique id of the market place
        market_place (str): name of the market place
        market_place_url (str): url of the market place
        market_place_region (str): region of the market place
    """

    def __init__(self):
        self.market_place = "Blinkit"
        self.base_url = "https://api2.grofers.com"
        self.keyword_page_api = "https://api2.grofers.com/v1/layout/search"

    def __del__(self):
        """Destructor of the scraper."""
        self.logger.info("Blinkit x product Scrapper Exited")

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
        Function to get all the products of a brand

        Args:
            brand_url: url of the brand filter applied page
            pincode: pincode of the place

        Returns:
            products_list: list of products
        """
        delay = random.uniform(1, 2)
        cookies = self.get_domain_cookies()
        # decoded_params = self.decode_collection_filters(url=brand_url)
        time.sleep(delay)

        # params = {
        #     'q': f'{decoded_params.get("collection_name", "").lower()}',
        #     'search_type': 'type_to_search',
        # }
        # encoded_params = urlencode(params)
        # full_url = f"{self.keyword_page_api}?{encoded_params}"

        full_url = f'https://api2.grofers.com/v1/layout/product/{product_id}'

        headers = {
            'Host': 'api2.grofers.com',
            'Host_app': 'blinkit',
            'Version_name': '17.61.1',
            'App_client': 'consumer_android',
            'App_version': '80170611',
            'Version_code': '80170611',
            'Qd_sdk_request': 'true',
            'Auth_key': '45bff2b1437ff764d5e5b9b292f9771428e18fc40b7f3b7303d196ea84ab4341',
            'Qd_sdk_version': '1',
            'Rn_bundle_version': '1009002001',
            'App_api_version': '29',
            'X-App-Theme': 'default',
            'X-App-Appearance': 'LIGHT',
            'X-System-Appearance': 'LIGHT',
            'X-Accessibility-Voice-Over-Enabled': '0',
            'Accept': 'application/json',
            'Screen_density': '1080px',
            'Screen_density_num': '3.5',
            'Cpu-Level': 'LOW',
            'Memory-Level': 'LOW',
            'Storage-Level': 'HIGH',
            'Network-Level': 'HIGH',
            'Battery-Level': 'AVERAGE',
            'Is_accessibility_enabled': 'false',
            'Lat': f'{lat}',
            'Lon': f'{lon}',
            'X-Zomato-Installed': 'false',
            'X-Rider-Installed': 'false',
            'X-Bistro-Installed': 'false',
            'X-District-Installed': 'false',
            'Entry_source': 'default',
            'Session_uuid': f'{uuid.uuid4()}',
            'Device_id': f'{uuid.uuid4().hex[:16]}',
            'Content-Type': 'application/json; charset=UTF-8',
            'User-Agent': 'com.grofers.customerapp/280170611 (Linux; U; Android 10; en; Pixel 3 XL; Build/QQ1D.200105.002; Cronet/142.0.7432.0)',
            'Priority': 'u=1, i',
        }

        response_json, _ = self.get_response_and_cookies(
            url=full_url,
            cookies=cookies,
            headers=headers,
            json_data={},
        )
        response_json = response_json.json()

        product_details = []
        info_details = []

        try:
            snippets = response_json.get("response", {}).get("snippets", [])
            additional_details = response_json.get("response", {}).get("snippet_list_updater_data", {})

            if snippets:
                product_details.extend(snippets)

            # FIXED: Must use .items()
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
                        "locality": locality,
                        "product_name": product.get("data", {}).get("title", {}).get("text", ""),
                        "product_id": common_attribute.get("product_id", ""),
                        "mrp": common_attribute.get("mrp", ""),
                        "price": common_attribute.get("price", ""),
                        "product_type": common_attribute.get("ptype", ""),
                        "merchant_id": common_attribute.get("merchant_id", ""),
                    }

                elif product.get("widget_type", "") == "crystal_snippet_type_6":
                    temp["brand_name"] = product.get("data", {}).get("title", {}).get("text", "")
                    temp["brand_url"] = product.get("data", {}).get("click_action", {}).get("blinkit_deeplink", {}).get("url")

            for details in info_details:
                text = details.get("left_header", {}).get("text", "")
                temp[text] = details.get("right_header", {}).get("text", "")

        except Exception as e:
            self.logger.error("Error occurred at get_all_brands function -> %s", e)

        all_sku_inventory.append(temp)
        self.logger.info(f"Scraped for {locality}: {product_id}")

        return (all_sku_inventory, [])

