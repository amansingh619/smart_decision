import sys
from pathlib import Path
import pandas as pd
import logging
sys.path.insert(0, str(Path(__file__).parent.parent))
from smart_decision.spiders.blinkit_spider.keyword_page_spider import BlinkitSpider 

def setup_logger(logfile: str = None):
    """Setup logger with file and console handlers"""
    logger = logging.getLogger(f"{logfile.split('_')[0].capitalize()}Launcher")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()  # Clear any existing handlers

    # File handler
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger

data = BlinkitSpider(logger=setup_logger("launcher.log")).fetch_search_products(
    keyword="sugar free ice cream",
    pincode=302006,
    latitude='26.9059311',
    longitude='75.78443829999999' 
)
data_df = pd.DataFrame(data)
data_df.to_excel('output.xlsx')