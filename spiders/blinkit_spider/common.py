import os
import random
import time

from curl_cffi import requests as curl_requests


class Common():
    def __init__(self, logger=None):
        self.logger = logger
        self.proxy = {
            "http": os.getenv("AZURE_PROXY_URL"),
            "https": os.getenv("AZURE_PROXY_URL"),
        }
        self.requests_report = {}
        self.platform_name = "Blinkit"

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