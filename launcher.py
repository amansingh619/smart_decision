# launcher.py

import sys
from pathlib import Path
import pandas as pd
import logging
sys.path.insert(0, str(Path(__file__).parent.parent))

from spiders.blinkit_spider.keyword_page_spider import BlinkitSpider
from smart_decision.pipeline import RecommendationPipeline

def setup_logger(logfile: str = None):
    """Setup logger with file and console handlers"""
    logger = logging.getLogger("AgentPipeline")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

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
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


if __name__ == "__main__":
    logger = setup_logger("pipeline.log")
    
    # spider instance 
    spider = BlinkitSpider(logger=logger)
    
    # creating pipeline for inst
    pipeline = RecommendationPipeline(spider_instance=spider, logger=logger)
    
    # queries
    queries = [
        "Best sugar free vanilla ice cream under 200",
        # "Low calorie ice cream for weight loss",
        # "Compare Mother Dairy and Cream Bell sugar free ice cream",
        # "High protein ice cream under 150"
    ]
    
    for query in queries:
        print(f"\n\n{'#'*60}")
        print(f"# QUERY: {query}")
        print(f"{'#'*60}")
        
        result = pipeline.launch_job(query)