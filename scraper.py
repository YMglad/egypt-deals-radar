"""
Backward-Compatible Root Scraper Module for Egyptian Deals & Black Friday Telegram Bot.
Delegates cleanly to the modular ScraperEngine and its 9 store adapters.
"""

from __future__ import annotations
import asyncio
import logging
from typing import List, Dict, Any, Optional
import aiohttp

from core.models import StoreEnum, Deal
from scrapers.engine import ScraperEngine, get_default_engine
from scrapers.base import DEFAULT_HEADERS

logger = logging.getLogger("DealsScraper")

# Legacy header export for backward compatibility
HEADERS = DEFAULT_HEADERS


class DealDict(dict):
    """
    Hybrid dictionary and Deal wrapper.
    Supports both dict-like key access (deal['title'], deal.get(...))
    and attribute-like property access (deal.title, deal.store).
    """

    def __init__(self, deal: Deal):
        super().__init__(deal.to_dict())
        self._deal = deal

    @property
    def deal(self) -> Deal:
        return self._deal

    def __getattr__(self, name: str) -> Any:
        if hasattr(self._deal, name):
            return getattr(self._deal, name)
        raise AttributeError(f"'DealDict' object has no attribute '{name}'")


async def scrape_all_deals(return_deals: bool = False) -> List[Any]:
    """
    Scrapes active deals across all 9 Egyptian retail platforms.
    If return_deals is True, returns List[Deal].
    Otherwise, returns List[DealDict] for 100% backward compatibility with legacy consumers.
    """
    engine = get_default_engine()
    deals = await engine.scrape_all()
    if return_deals:
        return deals
    return [DealDict(d) for d in deals]


# --- Per-Store Backward-Compatible Delegator Functions ---

async def fetch_amazon_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Amazon Egypt deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.AMAZON_EG, session=session)
    return [DealDict(d) for d in deals]


async def fetch_noon_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Noon Egypt deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.NOON_EG, session=session)
    return [DealDict(d) for d in deals]


async def fetch_breadfast_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Breadfast deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.BREADFAST, session=session)
    return [DealDict(d) for d in deals]


async def fetch_talabat_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Talabat Mart deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.TALABAT, session=session)
    return [DealDict(d) for d in deals]


async def fetch_valu_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes ValU partner deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.VALU, session=session)
    return [DealDict(d) for d in deals]


async def fetch_carrefour_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Carrefour Egypt deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.CARREFOUR_EG, session=session)
    return [DealDict(d) for d in deals]


async def fetch_jumia_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes Jumia Egypt deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.JUMIA_EG, session=session)
    return [DealDict(d) for d in deals]


async def fetch_btech_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes B.Tech deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.BTECH, session=session)
    return [DealDict(d) for d in deals]


async def fetch_2b_deals(session: Optional[aiohttp.ClientSession] = None) -> List[Dict[str, Any]]:
    """Scrapes 2B Egypt deals."""
    engine = get_default_engine()
    deals = await engine.scrape_store(StoreEnum.TWO_B, session=session)
    return [DealDict(d) for d in deals]
