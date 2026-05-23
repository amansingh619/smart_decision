import os

class Common():
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