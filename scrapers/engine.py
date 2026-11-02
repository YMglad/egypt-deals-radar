"""
Scraper Engine Orchestrator for Egyptian Deals & Black Friday Telegram Bot.
Concurrently executes all 9 store scrapers with strict timeout bounds and unified deduplication.
"""

from __future__ import annotations
import asyncio
import logging
from typing import Optional, List, Dict, Union, Any

import aiohttp

from core.models import StoreEnum, Deal
from scrapers.base import BaseStoreScraper
from scrapers.amazon_eg import AmazonScraper
from scrapers.noon_eg import NoonScraper
from scrapers.breadfast import BreadfastScraper
from scrapers.talabat import TalabatScraper
from scrapers.valu import ValUScraper
from scrapers.carrefour_eg import CarrefourScraper
from scrapers.jumia_eg import JumiaScraper
from scrapers.btech import BTechScraper
from scrapers.two_b import TwoBScraper

logger = logging.getLogger("ScraperEngine")


class ScraperEngine:
    """
    Coordinates and executes scraping tasks across all 9 authoritative Egyptian retail platforms.
    Guarantees concurrency via asyncio.gather and resilience through per-store exception containment.
    """

    def __init__(
        self,
        scrapers: Optional[List[BaseStoreScraper]] = None,
        timeout_per_store: float = 4.0
    ):
        self.timeout_per_store = timeout_per_store
        if scrapers is not None:
            self.scrapers = scrapers
        else:
            self.scrapers = [
                AmazonScraper(timeout=self.timeout_per_store),
                NoonScraper(timeout=self.timeout_per_store),
                BreadfastScraper(timeout=self.timeout_per_store),
                TalabatScraper(timeout=self.timeout_per_store),
                ValUScraper(timeout=self.timeout_per_store),
                CarrefourScraper(timeout=self.timeout_per_store),
                JumiaScraper(timeout=self.timeout_per_store),
                BTechScraper(timeout=self.timeout_per_store),
                TwoBScraper(timeout=self.timeout_per_store),
            ]

    def get_scraper(self, store_identifier: Union[str, StoreEnum]) -> Optional[BaseStoreScraper]:
        """Finds a scraper adapter by StoreEnum, store name, or common alias."""
        target_enum = StoreEnum.from_str(store_identifier)
        for s in self.scrapers:
            if s.store == target_enum:
                return s
        return None

    async def scrape_store(
        self,
        store_identifier: Union[str, StoreEnum],
        session: Optional[aiohttp.ClientSession] = None
    ) -> List[Deal]:
        """Scrapes an individual retailer on demand."""
        scraper = self.get_scraper(store_identifier)
        if not scraper:
            logger.warning("No scraper registered for store identifier: %s", store_identifier)
            return []

        try:
            return await scraper.scrape(session=session)
        except Exception as e:
            logger.error("Scraper %s raised unhandled exception: %s. Using fallback.", scraper.name, e)
            return scraper.get_fallback_deals()

    async def scrape_all(self, session: Optional[aiohttp.ClientSession] = None) -> List[Deal]:
        """
        Executes all 9 store scrapers concurrently using asyncio.gather(..., return_exceptions=True).
        Filters out exceptions gracefully, logs per-store metrics, and returns a unified,
        deduplicated list of validated Deal objects.
        """
        close_session = False
        if session is None:
            connector = aiohttp.TCPConnector(limit=30, ssl=False)
            timeout = aiohttp.ClientTimeout(total=self.timeout_per_store + 3.0)
            session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            close_session = True

        try:
            tasks = [scraper.scrape(session=session) for scraper in self.scrapers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            all_deals: List[Deal] = []
            seen_ids = set()
            seen_hashes = set()

            for scraper, res in zip(self.scrapers, results):
                if isinstance(res, Exception):
                    logger.error(
                        "Scraper for %s raised exception: %s. Activating fallback.",
                        scraper.name, res
                    )
                    deals = scraper.get_fallback_deals()
                elif isinstance(res, list):
                    deals = res
                    logger.info("Scraper for %s returned %d deals.", scraper.name, len(deals))
                else:
                    logger.warning("Scraper for %s returned invalid type: %s. Using fallback.", scraper.name, type(res))
                    deals = scraper.get_fallback_deals()

                # Deduplicate and validate
                for deal in deals:
                    if not isinstance(deal, Deal):
                        continue
                    # Check deduplication by id and content hash
                    deal_key = deal.id
                    deal_hash = deal.deal_hash or deal.compute_hash()
                    if deal_key in seen_ids or deal_hash in seen_hashes:
                        continue

                    seen_ids.add(deal_key)
                    seen_hashes.add(deal_hash)
                    all_deals.append(deal)

            logger.info("ScraperEngine.scrape_all completed. Total deduplicated deals: %d", len(all_deals))
            return all_deals

        finally:
            if close_session and session and not session.closed:
                await session.close()


_default_engine: Optional[ScraperEngine] = None


def get_default_engine() -> ScraperEngine:
    """Returns or initializes the global singleton ScraperEngine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = ScraperEngine()
    return _default_engine
