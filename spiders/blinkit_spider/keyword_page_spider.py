"""
Scraper for Blinkit 
"""
import datetime
from urllib.parse import urlencode
import os
import random
import time
import pandas as pd
from curl_cffi import requests as curl_requests



class BlinkitSpider():
    """Class for Blinkit Scraper"""

    def __init__(self, logger):
        self.logger = logger
        self.proxy = {
            "http": os.getenv("AZURE_PROXY_URL"),
            "https": os.getenv("AZURE_PROXY_URL"),
        }
        self.platform_name = "Blinkit"
        self.base_url = "https://api2.grofers.com"
        self.keyword_page_api = "https://api2.grofers.com/v1/layout/search"
        self.requests_report = {}

    def get_headers(self, latitude="", longitude=""):
        user_agent = (
            "com.grofers.customerapp/280170531 "
            "(Linux; U; Android 13; en_US; sdk_gphone64_x86_64; "
            "Build/TE1A.240213.009; Cronet/113.0.5672.51)"
        )
        return {
            "Host_app": "blinkit",
            "Version_name": "17.79.0",
            "App_client": "consumer_android",
            "App_version": "80170790",
            "Version_code": "80170790",
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflatitudee, br",
            "Accept": "application/json",
            "lat": f"{latitude}",
            "lon": f"{longitude}",
        }
    

    def get_response(
        self,
        request_url,
        headers,
        method="GET",
        data=None,
    ):
        """Function to do GET or POST request and reuturns the response"""

        retries = 20
        for attempt in range(retries):
            try:
                if method.upper() == "GET":
                    response = curl_requests.get(
                        request_url, 
                        headers=headers, 
                        proxies=self.proxy, 
                        timeout=25, 
                        impersonate="chrome"
                    )
                elif method.upper() == "POST":
                    response = curl_requests.post(
                        request_url,
                        headers=headers,
                        json=data,
                        proxies=self.proxy,
                        timeout=25,
                        impersonate="chrome",
                    )
                else:
                    raise ValueError("Unsupported HTTP method")
                if (
                    f"Status Code {response.status_code}"
                    not in self.requests_report
                ):
                    self.requests_report[f"Status Code {response.status_code}"] = 1
                else:
                    self.requests_report[f"Status Code {response.status_code}"] += 1

                response.raise_for_status()
                return response.json()
            except Exception as e:
                if response.status_code == 400:
                    self.logger.error(f"Recieved 400 for URL: {request_url}")
                    self.logger.error(getattr(response, "text", "No response"))
                    return {}
                self.logger.error(
                    f"Error during {method} request to {request_url}: {e}"
                )
                if attempt < retries - 1:
                    delay = random.uniform(0.5, 1.5)
                    self.logger.info(
                        f"Retrying in {delay:.2f} seconds... {attempt + 1}/{retries} attempts"
                    )
                    time.sleep(delay)
                else:
                    self.logger.error("Max retries reached.")
                    self.logger.error(getattr(response, "text", "No response"))
                    return {}
                

    def fetch_search_products(
        self,
        keyword,
        pincode=302006,
        latitude=None,
        longitude=None
    ):
        """
        Function to get all the products of a brand

        """
        current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        headers = self.get_headers(latitude, longitude)
        all_products = []
        next_url = None
        page_number = 0
        params = {
            "q": f"{keyword}",
            "search_type": "type_to_search",
        }
        encoded_params = urlencode(params)
        full_url = f"{self.keyword_page_api}?{encoded_params}"

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
                next_url = None
                return (None, None)

        all_products_detailed = []
        try:
            for product in all_products:
                temp = {}
                raw_data = product
                product = product.get("data", {})
                pack_size = None
                stepper = product.get("cta_data", {}).get("stepper", {})
                increment_actions = stepper.get("increment_actions", {}).get(
                    "default", []
                )
                decrement_actions = stepper.get("decrement_actions", {}).get(
                    "default", []
                )

                all_actions = (
                    increment_actions + decrement_actions
                )  # combining both the lists

                for action in all_actions:
                    if action.get("type") == "add_to_cart":
                        pack_size = (
                            action.get("add_to_cart", {})
                            .get("cart_item")
                            .get("unit", "")
                        )
                    if action.get("type") == "remove_from_cart":
                        pack_size = (
                            action.get("remove_from_cart", {})
                            .get("cart_item")
                            .get("unit", "")
                        )
                if not product.get("product_id", ""):
                    continue
                product_common_attributes = raw_data.get("tracking", {}).get(
                    "common_attributes", {}
                )
                in_organic_check = product_common_attributes.get("product_state", "")
                position = product_common_attributes.get("product_position", "")
                temp["pincode"] = pincode
                temp["key_word"] = keyword
                temp["date_time"] = current_timestamp
                temp["brand_name"] = product_common_attributes.get("brand", "")
                temp["product_name"] = product_common_attributes.get("name", "")
                temp["product_id"] = product.get("product_id", "")
                temp["product_url"] = (
                    f"https://blinkit.com/prn/_/prid/{product['product_id']}"
                )
                temp["position"] = position
                temp["growth"] = (
                    "In-organic" if in_organic_check == "AD_PRODUCT" else "Organic"
                )
                temp["quantity"] = product_common_attributes["inventory"]
                temp["availibility"] = (
                    1 if int(product_common_attributes.get("inventory", 0)) > 0 else 0
                )
                temp["mrp"] = product_common_attributes.get("mrp", "")
                temp["selling_price"] = product_common_attributes.get("price", "")
                temp["discount"] = ""
                temp["unit"] = pack_size
                temp["category"] = product_common_attributes.get("l2_category", "")
                temp["type"] = product_common_attributes.get("ptype", "")
                all_products_detailed.append(temp)
        except Exception as e:
            self.logger.error(f"Error occured while filtering json data: {e}")
        return all_products_detailed

