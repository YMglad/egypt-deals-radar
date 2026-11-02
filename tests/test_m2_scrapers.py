"""
Milestone 2 (M2) Comprehensive Scraper Engine & Store Adapters Test Suite.
Verifies all 9 store adapters, BaseStoreScraper, ScraperEngine concurrency,
resilience against timeouts and exceptions, and root scraper.py backward compatibility.
"""

import asyncio
import unittest
from unittest.mock import patch, AsyncMock
import aiohttp

from core.models import StoreEnum, CategoryEnum, Deal
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
import scraper

from tests.conftest import (
    AMAZON_EG_HTML,
    NOON_EG_JSON,
    BREADFAST_JSON,
    TALABAT_JSON,
    VALU_HTML,
    CARREFOUR_EG_HTML,
    JUMIA_EG_HTML,
    BTECH_HTML,
    TWO_B_HTML,
)


class TestM2BaseScraperFramework(unittest.TestCase):
    """Tests BaseStoreScraper and fetch_with_timeout behavior."""

    def test_base_scraper_abstract_instantiation_fails(self):
        """Cannot instantiate BaseStoreScraper directly without implementing abstract methods."""
        with self.assertRaises(TypeError):
            BaseStoreScraper()

    def test_fetch_with_timeout_catches_timeout_gracefully(self):
        """Simulates network timeout and verifies fetch_with_timeout returns None without raising."""
        async def run_timeout_test():
            # Test timeout with an unreachable or sleeping async task
            async def slow_fetch(*args, **kwargs):
                await asyncio.sleep(2.0)
                return "slow response"

            with patch("aiohttp.ClientSession.get", side_effect=asyncio.TimeoutError):
                res = await fetch_with_timeout("https://example.com/slow", timeout=0.1)
                self.assertIsNone(res)

        asyncio.run(run_timeout_test())

    def test_fetch_with_timeout_catches_client_error(self):
        """Simulates network connection error and verifies None is returned."""
        async def run_client_error_test():
            with patch("aiohttp.ClientSession.get", side_effect=aiohttp.ClientConnectionError("Connection refused")):
                res = await fetch_with_timeout("https://example.com/broken", timeout=1.0)
                self.assertIsNone(res)

        asyncio.run(run_client_error_test())


class TestM2NineStoreAdapters(unittest.TestCase):
    """Tests all 9 store scrapers with synthetic payloads and fallback mechanisms."""

    def setUp(self):
        self.amazon = AmazonScraper()
        self.noon = NoonScraper()
        self.breadfast = BreadfastScraper()
        self.talabat = TalabatScraper()
        self.valu = ValUScraper()
        self.carrefour = CarrefourScraper()
        self.jumia = JumiaScraper()
        self.btech = BTechScraper()
        self.twob = TwoBScraper()

    def test_all_9_scrapers_registered_with_correct_store_enum(self):
        """Verifies each scraper instance matches its required StoreEnum."""
        self.assertEqual(self.amazon.store, StoreEnum.AMAZON_EG)
        self.assertEqual(self.noon.store, StoreEnum.NOON_EG)
        self.assertEqual(self.breadfast.store, StoreEnum.BREADFAST)
        self.assertEqual(self.talabat.store, StoreEnum.TALABAT)
        self.assertEqual(self.valu.store, StoreEnum.VALU)
        self.assertEqual(self.carrefour.store, StoreEnum.CARREFOUR_EG)
        self.assertEqual(self.jumia.store, StoreEnum.JUMIA_EG)
        self.assertEqual(self.btech.store, StoreEnum.BTECH)
        self.assertEqual(self.twob.store, StoreEnum.TWO_B)

    def test_amazon_scraper_parse_html(self):
        """Verifies AmazonScraper.parse_html extracts valid deals from HTML."""
        deals = self.amazon.parse_html(AMAZON_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.AMAZON_EG)
            self.assertTrue(d.url.startswith("https://www.amazon.eg/dp/"))
            self.assertGreater(d.discount_price, 0)
            self.assertIsNotNone(d.deal_hash)

    def test_noon_scraper_parse_json(self):
        """Verifies NoonScraper.parse_json extracts valid deals from catalog JSON."""
        deals = self.noon.parse_json(NOON_EG_JSON)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.NOON_EG)
            self.assertTrue(d.url.startswith("https://www.noon.com/egypt-en/"))
            self.assertNotIn("utm_source", d.url)

    def test_breadfast_scraper_parse_json(self):
        """Verifies BreadfastScraper.parse_json produces deep product links."""
        deals = self.breadfast.parse_json(BREADFAST_JSON)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.BREADFAST)
            self.assertIn("/product/", d.url)
            self.assertNotEqual(d.url, "https://www.breadfast.com")

    def test_talabat_scraper_parse_json(self):
        """Verifies TalabatScraper.parse_json extracts valid grocery deals."""
        deals = self.talabat.parse_json(TALABAT_JSON)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.TALABAT)
            self.assertTrue(d.url.startswith("https://www.talabat.com/egypt/"))

    def test_valu_scraper_parse_html(self):
        """Verifies ValUScraper.parse_html extracts 0% financing info and pricing."""
        deals = self.valu.parse_html(VALU_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.VALU)
            self.assertIn("0%", d.installment_info)
            self.assertTrue(d.url.startswith("https://www.valu.com.eg/shop/"))

    def test_carrefour_scraper_parse_html(self):
        """Verifies CarrefourScraper.parse_html extracts /p/ product SKUs."""
        deals = self.carrefour.parse_html(CARREFOUR_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.CARREFOUR_EG)
            self.assertIn("/p/", d.url)

    def test_jumia_scraper_parse_html(self):
        """Verifies JumiaScraper.parse_html extracts valid product deals."""
        deals = self.jumia.parse_html(JUMIA_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.JUMIA_EG)
            self.assertTrue(d.url.startswith("https://www.jumia.com.eg/"))

    def test_btech_scraper_parse_html(self):
        """Verifies BTechScraper.parse_html extracts Mini Cash installment info."""
        deals = self.btech.parse_html(BTECH_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.BTECH)
            self.assertIn("ميني كاش", d.installment_info)

    def test_twob_scraper_parse_html(self):
        """Verifies TwoBScraper.parse_html extracts gaming laptops and excludes '#' anchor links."""
        deals = self.twob.parse_html(TWO_B_HTML)
        self.assertGreaterEqual(len(deals), 2)
        for d in deals:
            self.assertIsInstance(d, Deal)
            self.assertEqual(d.store, StoreEnum.TWO_B)
            self.assertTrue(d.url.startswith("https://2b.com.eg/en/"))
            self.assertFalse(d.url.endswith("#"))

    def test_all_fallback_deals_are_genuine_valid_deals(self):
        """Verifies every store adapter produces valid, non-empty fallback deals."""
        scrapers = [
            self.amazon, self.noon, self.breadfast, self.talabat,
            self.valu, self.carrefour, self.jumia, self.btech, self.twob
        ]
        for s in scrapers:
            fallbacks = s.get_fallback_deals()
            self.assertGreaterEqual(len(fallbacks), 2, f"{s.name} fallback deals count < 2")
            for deal in fallbacks:
                self.assertIsInstance(deal, Deal)
                self.assertEqual(deal.store, s.store)
                self.assertGreater(deal.discount_price, 0)
                self.assertGreaterEqual(deal.original_price, deal.discount_price)
                self.assertTrue(deal.url.startswith("https://"))
                self.assertIsNotNone(deal.deal_hash)


class TestM2ScraperEngineOrchestrator(unittest.TestCase):
    """Tests ScraperEngine concurrent execution, fault tolerance, and deduplication."""

    def test_engine_initializes_with_all_9_stores(self):
        """Verifies ScraperEngine contains all 9 retail stores by default."""
        engine = ScraperEngine()
        self.assertEqual(len(engine.scrapers), 9)
        stores = {s.store for s in engine.scrapers}
        for expected in StoreEnum:
            self.assertIn(expected, stores, f"Missing store {expected} in ScraperEngine")

    def test_engine_scrape_store_by_name_and_enum(self):
        """Verifies scrape_store works with both StoreEnum and string aliases."""
        async def run_store_tests():
            engine = ScraperEngine()
            # Test with StoreEnum
            amz_deals = await engine.scrape_store(StoreEnum.AMAZON_EG)
            self.assertGreaterEqual(len(amz_deals), 2)
            self.assertEqual(amz_deals[0].store, StoreEnum.AMAZON_EG)

            # Test with string alias
            twob_deals = await engine.scrape_store("2b egypt")
            self.assertGreaterEqual(len(twob_deals), 2)
            self.assertEqual(twob_deals[0].store, StoreEnum.TWO_B)

        asyncio.run(run_store_tests())

    def test_engine_resilience_when_scraper_raises_exception(self):
        """
        Verifies that if a store scraper raises an unexpected exception during execution,
        ScraperEngine catches it, invokes that store's fallback, and does not crash the loop.
        """
        async def run_resilience_test():
            engine = ScraperEngine()
            # Sabotage one scraper to raise an unhandled exception
            faulty_scraper = engine.get_scraper(StoreEnum.JUMIA_EG)
            original_scrape = faulty_scraper.scrape

            async def crashing_scrape(session=None):
                raise RuntimeError("Simulated critical network/parse failure in JumiaScraper")

            faulty_scraper.scrape = crashing_scrape

            try:
                deals = await engine.scrape_all()
                self.assertGreaterEqual(len(deals), 18)
                # Verify Jumia deals were still obtained via fallback
                jumia_deals = [d for d in deals if d.store == StoreEnum.JUMIA_EG]
                self.assertGreaterEqual(len(jumia_deals), 2)
            finally:
                faulty_scraper.scrape = original_scrape

        asyncio.run(run_resilience_test())

    def test_engine_deduplicates_deals_with_identical_ids_or_hashes(self):
        """Verifies ScraperEngine suppresses duplicate deal instances."""
        async def run_dedup_test():
            engine = ScraperEngine()
            deals = await engine.scrape_all()
            seen_ids = set()
            seen_hashes = set()
            for d in deals:
                self.assertNotIn(d.id, seen_ids, f"Duplicate deal id: {d.id}")
                self.assertNotIn(d.deal_hash, seen_hashes, f"Duplicate deal hash: {d.deal_hash}")
                seen_ids.add(d.id)
                seen_hashes.add(d.deal_hash)

        asyncio.run(run_dedup_test())


class TestM2RootScraperBackwardCompatibility(unittest.TestCase):
    """Tests root scraper.py module backward compatibility."""

    def test_scrape_all_deals_returns_dealdict_with_both_interfaces(self):
        """Verifies legacy scrape_all_deals returns DealDict supporting both dict and attr access."""
        async def run_compat_test():
            deals = await scraper.scrape_all_deals()
            self.assertGreaterEqual(len(deals), 18)
            d = deals[0]
            self.assertIsInstance(d, dict)
            self.assertIn("title", d)
            self.assertIn("discount_price", d)
            self.assertIn("url", d)
            # Attribute access
            self.assertEqual(d.title, d["title"])
            self.assertEqual(d.store, d["store"])
            # Underlying deal
            self.assertIsInstance(d.deal, Deal)

            # Test return_deals=True flag
            canonical_deals = await scraper.scrape_all_deals(return_deals=True)
            self.assertIsInstance(canonical_deals[0], Deal)

        asyncio.run(run_compat_test())

    def test_per_store_legacy_functions_callable(self):
        """Verifies legacy fetch_*_deals functions are present and functional."""
        async def run_per_store():
            amz = await scraper.fetch_amazon_deals()
            self.assertGreaterEqual(len(amz), 2)

            noon = await scraper.fetch_noon_deals()
            self.assertGreaterEqual(len(noon), 2)

            bf = await scraper.fetch_breadfast_deals()
            self.assertGreaterEqual(len(bf), 2)

            tb = await scraper.fetch_talabat_deals()
            self.assertGreaterEqual(len(tb), 2)

            valu = await scraper.fetch_valu_deals()
            self.assertGreaterEqual(len(valu), 2)

            crf = await scraper.fetch_carrefour_deals()
            self.assertGreaterEqual(len(crf), 2)

            jumia = await scraper.fetch_jumia_deals()
            self.assertGreaterEqual(len(jumia), 2)

            btech = await scraper.fetch_btech_deals()
            self.assertGreaterEqual(len(btech), 2)

            twob = await scraper.fetch_2b_deals()
            self.assertGreaterEqual(len(twob), 2)

        asyncio.run(run_per_store())


if __name__ == "__main__":
    unittest.main()
