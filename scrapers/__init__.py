"""
Scrapers Package for Egyptian Deals & Black Friday Telegram Bot.
Exports BaseStoreScraper, ScraperEngine, and all 9 retail store adapters.
"""

from scrapers.base import BaseStoreScraper, fetch_with_timeout
from scrapers.engine import ScraperEngine, get_default_engine
from scrapers.amazon_eg import AmazonScraper
from scrapers.noon_eg import NoonScraper
from scrapers.breadfast import BreadfastScraper
from scrapers.talabat import TalabatScraper
from scrapers.valu import ValUScraper
from scrapers.carrefour_eg import CarrefourScraper
from scrapers.jumia_eg import JumiaScraper
from scrapers.btech import BTechScraper
from scrapers.two_b import TwoBScraper

__all__ = [
    "BaseStoreScraper",
    "fetch_with_timeout",
    "ScraperEngine",
    "get_default_engine",
    "AmazonScraper",
    "NoonScraper",
    "BreadfastScraper",
    "TalabatScraper",
    "ValUScraper",
    "CarrefourScraper",
    "JumiaScraper",
    "BTechScraper",
    "TwoBScraper",
]
