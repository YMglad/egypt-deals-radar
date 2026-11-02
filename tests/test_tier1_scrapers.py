"""
Tier 1 Tests: Store Scraper Parsing & Field Completeness across all 9 Stores.

Covers:
- Feature 11: Store Scraper Extraction (9 Stores: Amazon, Noon, Breadfast, Talabat, ValU, Carrefour, Jumia, B.Tech, 2B)
- Feature 12: Direct URL Extraction & Validation (>= 5 tests)
"""

import unittest
from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url
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
    parse_amazon_snippet,
    parse_noon_snippet,
    parse_breadfast_snippet,
    parse_talabat_snippet,
    parse_valu_snippet,
    parse_carrefour_snippet,
    parse_jumia_snippet,
    parse_btech_snippet,
    parse_twob_snippet,
)


class TestTier1ScrapersParsing(unittest.TestCase):
    """Tier 1: Scraper extraction for all 9 authoritative Egyptian retail platforms."""

    def test_amazon_eg_scraper_extraction(self):
        """1. Verifies Amazon EG extraction: title, prices, ASIN direct URL, and discount."""
        deals = parse_amazon_snippet(AMAZON_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)

        # Diapers deal
        diaper_deal = deals[0]
        self.assertEqual(diaper_deal["store"], StoreEnum.AMAZON_EG)
        self.assertIn("بامبرز", diaper_deal["title"])
        self.assertEqual(diaper_deal["discount_price"], 399.50)
        self.assertEqual(diaper_deal["original_price"], 520.00)
        self.assertGreater(diaper_deal["discount_percentage"], 20.0)
        self.assertTrue(diaper_deal["url"].startswith("https://www.amazon.eg/dp/B09H123456"))

        # Laptop deal
        laptop_deal = deals[1]
        self.assertIn("ROG Strix", laptop_deal["title"])
        self.assertEqual(laptop_deal["discount_price"], 64999.00)
        self.assertTrue(laptop_deal["url"].startswith("https://www.amazon.eg/dp/B08XYZ7890"))

    def test_noon_eg_scraper_extraction(self):
        """2. Verifies Noon EG extraction: SKU, title, prices, and direct product link."""
        deals = parse_noon_snippet(NOON_EG_JSON)
        self.assertGreaterEqual(len(deals), 2)

        fine_baby = deals[0]
        self.assertEqual(fine_baby["store"], StoreEnum.NOON_EG)
        self.assertIn("فاين بيبي", fine_baby["title"])
        self.assertEqual(fine_baby["discount_price"], 315.0)
        self.assertEqual(fine_baby["original_price"], 420.0)
        self.assertEqual(fine_baby["discount_percentage"], 25.0)
        self.assertTrue(fine_baby["url"].startswith("https://www.noon.com/egypt-en/"))
        self.assertNotIn("utm_source", fine_baby["url"])

        legion = deals[1]
        self.assertIn("Legion 5", legion["title"])
        self.assertEqual(legion["discount_price"], 54999.0)
        self.assertNotIn("utm_campaign", legion["url"])

    def test_breadfast_scraper_extraction(self):
        """3. Verifies Breadfast extraction: household & diaper deals with deep product URLs."""
        deals = parse_breadfast_snippet(BREADFAST_JSON)
        self.assertGreaterEqual(len(deals), 2)

        molfix = deals[0]
        self.assertEqual(molfix["store"], StoreEnum.BREADFAST)
        self.assertIn("مولفيكس", molfix["title"])
        self.assertEqual(molfix["discount_price"], 365.0)
        self.assertEqual(molfix["original_price"], 440.0)
        self.assertTrue(molfix["url"].startswith("https://www.breadfast.com/product/molfix"))
        self.assertNotIn("source=carousel", molfix["url"])

        persil = deals[1]
        self.assertIn("برسيل", persil["title"])
        self.assertEqual(persil["discount_price"], 289.0)

    def test_talabat_scraper_extraction(self):
        """4. Verifies Talabat Mart extraction: household & baby essentials with direct URLs."""
        deals = parse_talabat_snippet(TALABAT_JSON)
        self.assertGreaterEqual(len(deals), 2)

        pampers = deals[0]
        self.assertEqual(pampers["store"], StoreEnum.TALABAT)
        self.assertIn("بامبرز", pampers["title"])
        self.assertEqual(pampers["discount_price"], 380.0)
        self.assertTrue(pampers["url"].startswith("https://www.talabat.com/egypt/talabat-mart/product/tb-99120"))

        fairy = deals[1]
        self.assertIn("فيري", fairy["title"])
        self.assertEqual(fairy["discount_price"], 45.0)

    def test_valu_deals_scraper_extraction(self):
        """5. Verifies ValU partner promotions: 0% installment info, direct URLs, pricing."""
        deals = parse_valu_snippet(VALU_HTML)
        self.assertGreaterEqual(len(deals), 2)

        dell_deal = deals[0]
        self.assertEqual(dell_deal["store"], StoreEnum.VALU)
        self.assertIn("Dell G15", dell_deal["title"])
        self.assertEqual(dell_deal["discount_price"], 48500.0)
        self.assertIn("0% فوائد", dell_deal["installment_info"])
        self.assertTrue(dell_deal["url"].startswith("https://www.valu.com.eg/shop/dell-g15"))
        self.assertNotIn("fbclid", dell_deal["url"])

        airfryer = deals[1]
        self.assertIn("فيليبس", airfryer["title"])
        self.assertEqual(airfryer["discount_price"], 8999.0)

    def test_carrefour_eg_scraper_extraction(self):
        """6. Verifies Carrefour EG extraction: diapers, baby rompers, and absolute URLs."""
        deals = parse_carrefour_snippet(CARREFOUR_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)

        pampers = deals[0]
        self.assertEqual(pampers["store"], StoreEnum.CARREFOUR_EG)
        self.assertIn("Pampers", pampers["title"])
        self.assertEqual(pampers["discount_price"], 375.0)
        self.assertTrue(pampers["url"].startswith("https://www.carrefouregypt.com/mafegy/en/baby-products"))
        self.assertNotIn("utm_medium", pampers["url"])

        romper = deals[1]
        self.assertIn("سالوبيت", romper["title"])
        self.assertEqual(romper["discount_price"], 299.0)

    def test_jumia_eg_scraper_extraction(self):
        """7. Verifies Jumia EG extraction: gaming laptops, fashion hoodie, direct URLs."""
        deals = parse_jumia_snippet(JUMIA_EG_HTML)
        self.assertGreaterEqual(len(deals), 2)

        laptop = deals[0]
        self.assertEqual(laptop["store"], StoreEnum.JUMIA_EG)
        self.assertIn("HP Victus", laptop["title"])
        self.assertEqual(laptop["discount_price"], 33999.0)
        self.assertTrue(laptop["url"].startswith("https://www.jumia.com.eg/hp-victus"))
        self.assertNotIn("utm_source", laptop["url"])

        hoodie = deals[1]
        self.assertIn("هودي", hoodie["title"])
        self.assertEqual(hoodie["discount_price"], 450.0)

    def test_btech_scraper_extraction(self):
        """8. Verifies B.Tech extraction: laptops, Mini Cash installments, appliances."""
        deals = parse_btech_snippet(BTECH_HTML)
        self.assertGreaterEqual(len(deals), 2)

        ideapad = deals[0]
        self.assertEqual(ideapad["store"], StoreEnum.BTECH)
        self.assertIn("لينوفو", ideapad["title"])
        self.assertEqual(ideapad["discount_price"], 31500.0)
        self.assertIn("ميني كاش", ideapad["installment_info"])
        self.assertTrue(ideapad["url"].startswith("https://btech.com/en/lenovo-ideapad"))
        self.assertNotIn("ref=deals_hub", ideapad["url"])

        kettle = deals[1]
        self.assertIn("تورنيدو", kettle["title"])
        self.assertEqual(kettle["discount_price"], 699.0)

    def test_twob_scraper_extraction(self):
        """9. Verifies 2B Egypt extraction: Nitro, TUF gaming laptops, direct links."""
        deals = parse_twob_snippet(TWO_B_HTML)
        self.assertGreaterEqual(len(deals), 2)

        acer = deals[0]
        self.assertEqual(acer["store"], StoreEnum.TWO_B)
        self.assertIn("Acer Nitro", acer["title"])
        self.assertEqual(acer["discount_price"], 46999.0)
        self.assertTrue(acer["url"].startswith("https://2b.com.eg/en/acer-nitro"))
        self.assertNotIn("utm_campaign", acer["url"])

        tuf = deals[1]
        self.assertIn("TUF Gaming", tuf["title"])
        self.assertEqual(tuf["discount_price"], 33500.0)


class TestDirectURLExtractionAndValidation(unittest.TestCase):
    """Tier 1: Direct Order URL Integrity & Deep Link Verification (Feature 12)."""

    def test_rejects_empty_and_whitespace_urls(self):
        """Verifies scrapers and canonicalizers reject blank URLs."""
        with self.assertRaises(ValueError):
            canonicalize_url("")
        with self.assertRaises(ValueError):
            canonicalize_url("    ")

    def test_rejects_dummy_hash_url(self):
        """Verifies dummy anchor '#' links are strictly rejected."""
        with self.assertRaises(ValueError):
            canonicalize_url("#")

    def test_ensures_all_9_stores_yield_https_urls(self):
        """Verifies every extracted deal from all 9 stores produces a valid HTTPS URL."""
        all_deals = []
        all_deals.extend(parse_amazon_snippet(AMAZON_EG_HTML))
        all_deals.extend(parse_noon_snippet(NOON_EG_JSON))
        all_deals.extend(parse_breadfast_snippet(BREADFAST_JSON))
        all_deals.extend(parse_talabat_snippet(TALABAT_JSON))
        all_deals.extend(parse_valu_snippet(VALU_HTML))
        all_deals.extend(parse_carrefour_snippet(CARREFOUR_EG_HTML))
        all_deals.extend(parse_jumia_snippet(JUMIA_EG_HTML))
        all_deals.extend(parse_btech_snippet(BTECH_HTML))
        all_deals.extend(parse_twob_snippet(TWO_B_HTML))

        self.assertGreaterEqual(len(all_deals), 18)
        for d in all_deals:
            url = d["url"]
            self.assertTrue(url.startswith("https://"), f"URL {url} does not start with https://")
            self.assertNotEqual(url, "https://", "URL cannot be just scheme")
            self.assertFalse(url.endswith("#"), f"URL {url} cannot end with #")

    def test_deep_links_lead_to_product_pages_not_homepages(self):
        """Verifies links are direct deep links to products rather than top-level homepages."""
        bf_deals = parse_breadfast_snippet(BREADFAST_JSON)
        for deal in bf_deals:
            self.assertIn("/product/", deal["url"], "Breadfast URL must be a deep product link")
            self.assertNotEqual(deal["url"], "https://www.breadfast.com")

        crf_deals = parse_carrefour_snippet(CARREFOUR_EG_HTML)
        for deal in crf_deals:
            self.assertIn("/p/", deal["url"], "Carrefour URL must contain product SKU path /p/")

    def test_asin_preserved_in_amazon_direct_links(self):
        """Verifies Amazon links reliably contain the 10-character ASIN."""
        amz_deals = parse_amazon_snippet(AMAZON_EG_HTML)
        for deal in amz_deals:
            self.assertRegex(deal["url"], r"/dp/[A-Z0-9]{10}", "Amazon URL must contain canonical ASIN")


if __name__ == "__main__":
    unittest.main()
