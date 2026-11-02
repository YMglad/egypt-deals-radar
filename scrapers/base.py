"""
Base Scraper Framework for Egyptian Deals & Black Friday Telegram Bot.
Provides abstract base scraper class, strict timeout wrappers, and fallback mechanisms.
"""

from __future__ import annotations
import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

import aiohttp

from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url
from core.classifier import tag_deal_category, classify_deal

logger = logging.getLogger("ScraperEngine")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


async def fetch_with_timeout(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
    timeout: float = 4.0,
    headers: Optional[dict] = None
) -> Optional[str]:
    """
    Executes an asynchronous HTTP GET request with strict 3-5s timeout protection.
    Returns response text on 200 OK, or None if timed out, blocked by WAF (403/503),
    or encountering network/connection errors.
    """
    req_headers = headers or DEFAULT_HEADERS
    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout * 0.75)

    close_session_on_exit = False
    if session is None:
        connector = aiohttp.TCPConnector(ssl=False)
        session = aiohttp.ClientSession(timeout=client_timeout, connector=connector)
        close_session_on_exit = True

    try:
        async def _do_fetch() -> Optional[str]:
            async with session.get(url, headers=req_headers, timeout=client_timeout, allow_redirects=True) as response:
                if response.status == 200:
                    text = await response.text()
                    # Detect Akamai placeholder empty responses (e.g. 53 bytes)
                    if len(text.strip()) < 80 and "<p></p>" in text:
                        logger.warning("Empty Akamai placeholder payload received from %s", url)
                        return None
                    return text
                elif response.status in (403, 503):
                    logger.warning("WAF/Anti-Bot challenge (status %d) encountered on %s", response.status, url)
                    return None
                else:
                    logger.warning("HTTP status %d returned from %s", response.status, url)
                    return None

        return await asyncio.wait_for(_do_fetch(), timeout=timeout)

    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("Request timed out after %.1fs on %s", timeout, url)
        return None
    except aiohttp.ClientError as err:
        logger.warning("Client error fetching %s: %s", url, err)
        return None
    except Exception as err:
        logger.warning("Unexpected error fetching %s: %s", url, err)
        return None
    finally:
        if close_session_on_exit and session and not session.closed:
            await session.close()


class BaseStoreScraper(ABC):
    """
    Abstract Base Class for store scrapers across all 9 Egyptian retail platforms.
    Enforces the store property, scrape method, timeout bounds, and graceful fallback.
    """

    store: StoreEnum
    timeout: float = 4.0

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout
        if not hasattr(self, "store") or self.store is None:
            raise ValueError(f"Subclass {self.__class__.__name__} must define a 'store' property.")

    @property
    def name(self) -> str:
        """Display name of the retailer."""
        return self.store.value if isinstance(self.store, StoreEnum) else str(self.store)

    @abstractmethod
    async def scrape(self, session: Optional[aiohttp.ClientSession] = None) -> List[Deal]:
        """
        Executes store scraping asynchronously and returns a list of canonical Deal objects.
        Must never raise unhandled exceptions; catches network issues and falls back gracefully.
        """
        pass

    async def fetch(
        self,
        url: str,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: Optional[float] = None,
        headers: Optional[dict] = None
    ) -> Optional[str]:
        """Wrapper around fetch_with_timeout with scraper-level timeout configuration."""
        effective_timeout = timeout or self.timeout
        return await fetch_with_timeout(url, session=session, timeout=effective_timeout, headers=headers)

    @abstractmethod
    def get_fallback_deals(self) -> List[Deal]:
        """
        Returns validated, high-value fallback deals for this retailer.
        Ensures the scraper engine produces rich deals even when blocked by WAF/Cloudflare.
        """
        pass

    def build_deal(
        self,
        item_id: str,
        title: str,
        original_price: float,
        discount_price: float,
        url: str,
        discount_percentage: Optional[float] = None,
        image_url: Optional[str] = None,
        is_flash_sale: bool = False,
        is_special_laptop: bool = False,
        coupon_code: Optional[str] = None,
        installment_info: Optional[str] = None,
        raw_category: Optional[str] = None
    ) -> Optional[Deal]:
        """
        Helper method to instantiate, canonicalize, and classify a Deal.
        Returns None if title or URL are fundamentally invalid.
        """
        clean_title = (title or "").strip()
        if not clean_title or len(clean_title) < 3:
            return None

        # Clean prices
        try:
            curr_p = float(discount_price)
            orig_p = float(original_price) if original_price else curr_p
        except (ValueError, TypeError):
            return None

        if curr_p <= 0:
            return None
        if orig_p < curr_p:
            orig_p = curr_p

        # Canonicalize URL
        try:
            clean_url = canonicalize_url(url)
        except Exception as e:
            logger.debug("Invalid deal URL '%s' for item '%s': %s", url, clean_title, e)
            return None

        # Calculate discount percentage if not provided
        if discount_percentage is None or discount_percentage <= 0:
            if orig_p > curr_p:
                calc_discount = round(((orig_p - curr_p) / orig_p) * 100, 1)
            else:
                calc_discount = 0.0
        else:
            calc_discount = float(discount_percentage)

        # Classify category
        category = classify_deal(clean_title, store=self.store, raw_category=raw_category)
        laptop_flag = is_special_laptop or (category == CategoryEnum.LAPTOPS)

        deal = Deal(
            id=item_id,
            title=clean_title,
            store=self.store,
            category=category,
            original_price=orig_p,
            discount_price=curr_p,
            discount_percentage=calc_discount,
            url=clean_url,
            image_url=image_url or None,
            is_flash_sale=is_flash_sale,
            is_special_laptop=laptop_flag,
            coupon_code=coupon_code or None,
            installment_info=installment_info or None
        )
        return deal
