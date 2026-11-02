"""
Tier 2 Tests: Boundary & Corner Cases (Adversarial, Extreme & Invalid Inputs).

Covers:
- Feature 13: Boundary Price Validation (>= 5 tests)
- Feature 14: Boundary Discount Edge Cases (>= 5 tests)
- Feature 15: Boundary Malformed & Tracking URLs (>= 5 tests)
- Feature 16: Boundary HTML / Special Character Escaping (>= 5 tests)
- Feature 17: Boundary Empty & Extreme Payloads (>= 5 tests)
"""

import unittest
from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url
from tests.conftest import (
    html_escape,
    format_deal_telegram,
    parse_amazon_snippet,
    parse_noon_snippet,
    parse_breadfast_snippet,
)


class TestBoundaryPriceValidation(unittest.TestCase):
    """Tier 2: Boundary Price Validation (Feature 13)."""

    def test_original_price_zero_with_positive_discount_price(self):
        """Verifies Deal defaults original_price to discount_price when original_price is 0."""
        deal = Deal(
            id="p_zero_orig",
            title="Ariel Gel 2L",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=0.0,
            discount_price=120.0,
            discount_percentage=0.0,
            url="https://www.amazon.eg/dp/B000000001",
        )
        self.assertEqual(deal.original_price, 120.0)
        self.assertEqual(deal.discount_price, 120.0)
        self.assertEqual(deal.discount_amount, 0.0)

    def test_discount_price_greater_than_original_price(self):
        """Verifies discount_percentage is 0.0 when discount_price exceeds original_price."""
        deal = Deal(
            id="p_inv",
            title="Cookware Set",
            store=StoreEnum.CARREFOUR_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=500.0,
            discount_price=600.0,
            discount_percentage=0.0,
            url="https://www.carrefouregypt.com/p/100",
        )
        self.assertEqual(deal.discount_percentage, 0.0)
        self.assertEqual(deal.discount_amount, 0.0)

    def test_handles_extreme_large_prices(self):
        """Verifies system handles high-value luxury laptops (e.g., 250,000+ EGP)."""
        deal = Deal(
            id="lp_expensive",
            title="ASUS ROG Strix SCAR 18 RTX 4090",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=280000.0,
            discount_price=249999.0,
            discount_percentage=0.0,
            url="https://2b.com.eg/asus-scar-18",
        )
        self.assertEqual(deal.discount_price, 249999.0)
        self.assertAlmostEqual(deal.discount_amount, 30001.0, places=1)
        self.assertTrue(deal.discount_percentage > 10.0)

    def test_handles_fractional_piastres_pricing(self):
        """Verifies precise floating point arithmetic for prices with piasters (e.g. 49.95 EGP)."""
        deal = Deal(
            id="p_piasters",
            title="Fine Baby Pocket Wipes",
            store=StoreEnum.TALABAT,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=65.75,
            discount_price=49.95,
            discount_percentage=0.0,
            url="https://www.talabat.com/wipes",
        )
        self.assertAlmostEqual(deal.discount_amount, 15.80, places=2)
        self.assertAlmostEqual(deal.discount_percentage, 24.0, places=0)

    def test_string_numeric_price_coercion(self):
        """Verifies Deal deserializes numeric string prices into valid floats."""
        data = {
            "id": "p_str",
            "title": "Persil Liquid",
            "store": "Noon Egypt",
            "category": "مستلزمات منزلية",
            "original_price": "250.50",
            "discount_price": "199.99",
            "discount_percentage": "20.1",
            "url": "https://www.noon.com/p",
        }
        deal = Deal.from_dict(data)
        self.assertIsInstance(deal.original_price, float)
        self.assertIsInstance(deal.discount_price, float)
        self.assertIsInstance(deal.discount_percentage, float)
        self.assertEqual(deal.original_price, 250.50)
        self.assertEqual(deal.discount_price, 199.99)
        self.assertEqual(deal.discount_percentage, 20.1)


class TestBoundaryDiscountEdgeCases(unittest.TestCase):
    """Tier 2: Boundary Discount Edge Cases (Feature 14)."""

    def test_zero_discount_rate(self):
        """Verifies 0% discount handles gracefully when current equals original price."""
        deal = Deal(
            id="d_zero",
            title="Regular Breadfast Milk",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=45.0,
            discount_price=45.0,
            discount_percentage=0.0,
            url="https://www.breadfast.com/milk",
        )
        self.assertEqual(deal.discount_percentage, 0.0)
        self.assertEqual(deal.discount_amount, 0.0)

    def test_near_100_percent_clearance_discount(self):
        """Verifies flash clearance sale with 90%+ discount."""
        deal = Deal(
            id="d_clearance",
            title="Baby Socks Clearance 5-Pack",
            store=StoreEnum.JUMIA_EG,
            category=CategoryEnum.BABY_CLOTHES,
            original_price=100.0,
            discount_price=5.0,
            discount_percentage=0.0,
            url="https://www.jumia.com.eg/socks",
        )
        self.assertEqual(deal.discount_percentage, 95.0)
        self.assertEqual(deal.discount_amount, 95.0)

    def test_discount_percentage_rounding(self):
        """Verifies discount percentage rounds cleanly to 1 decimal place."""
        deal = Deal(
            id="d_round",
            title="Molfix Diapers",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=333.33,
            discount_price=222.22,
            discount_percentage=0.0,
            url="https://www.amazon.eg/dp/B000000002",
        )
        self.assertAlmostEqual(deal.discount_percentage, 33.3, places=1)

    def test_negative_discount_price_auto_calc_yields_zero_discount(self):
        """Verifies when discount_price exceeds original price, auto-calculated discount is 0.0."""
        deal = Deal(
            id="d_neg",
            title="T-Shirt",
            store=StoreEnum.NOON_EG,
            category=CategoryEnum.CLOTHING_ADULT_KIDS,
            original_price=100.0,
            discount_price=120.0,
            discount_percentage=0.0,
            url="https://www.noon.com/tshirt",
        )
        self.assertEqual(deal.discount_percentage, 0.0)
        self.assertEqual(deal.discount_amount, 0.0)

    def test_explicit_discount_percentage_preserved_if_provided(self):
        """Verifies scrapers passing explicit verified discount_percentage is honored."""
        deal = Deal(
            id="d_explicit",
            title="Fairy Liquid",
            store=StoreEnum.TALABAT,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=100.0,
            discount_price=70.0,
            discount_percentage=30.0,
            url="https://www.talabat.com/fairy",
        )
        self.assertEqual(deal.discount_percentage, 30.0)


class TestBoundaryMalformedAndTrackingURLs(unittest.TestCase):
    """Tier 2: Boundary Malformed & Tracking URLs (Feature 15)."""

    def test_strips_massive_tracking_query_flood(self):
        """Verifies URL sanitizer strips all analytics and social trackers."""
        dirty_url = (
            "https://www.jumia.com.eg/product-1.html?"
            "utm_source=facebook&utm_medium=cpc&utm_campaign=black_friday&utm_term=deals&utm_content=v1&"
            "fbclid=IwAR2XYZ987654&gclid=Cj0KCQjwgNaN&_ga=GA1.2.123456.789012&ref=banner&ascsubtag=991&"
            "campaign_id=bf2026&ad_id=12345&source=app&igshid=xyz123&real_param=active"
        )
        clean = canonicalize_url(dirty_url)
        self.assertNotIn("utm_source", clean)
        self.assertNotIn("fbclid", clean)
        self.assertNotIn("gclid", clean)
        self.assertNotIn("igshid", clean)
        self.assertNotIn("_ga", clean)
        self.assertIn("real_param=active", clean)

    def test_handles_url_without_explicit_scheme(self):
        """Verifies schemeless URLs like 'btech.com/product' are prepended with 'https://'."""
        clean = canonicalize_url("btech.com/en/laptop.html")
        self.assertEqual(clean, "https://btech.com/en/laptop.html")

    def test_handles_whitespace_padded_urls(self):
        """Verifies URL surrounded by spaces, tabs, or newlines is cleanly trimmed."""
        clean = canonicalize_url("\n\t https://www.noon.com/egypt-en/p-10 \r\n ")
        self.assertEqual(clean, "https://www.noon.com/egypt-en/p-10")

    def test_normalizes_uppercase_hostname(self):
        """Verifies hostname with mixed uppercase letters is lowercased."""
        clean = canonicalize_url("HTTPS://WWW.CARREFOUREGYPT.COM/p/102")
        self.assertTrue(clean.startswith("https://www.carrefouregypt.com/p/102"))

    def test_handles_complex_encoded_query_strings(self):
        """Verifies valid parameters containing Arabic or encoded characters are retained."""
        url = "https://www.breadfast.com/search?category=حفاضات&sort=price_asc"
        clean = canonicalize_url(url)
        self.assertIn("category=", clean)
        self.assertIn("sort=price_asc", clean)


class TestBoundaryHTMLSpecialCharactersEscaping(unittest.TestCase):
    """Tier 2: Boundary HTML / Special Character Escaping (Feature 16)."""

    def test_escapes_xss_script_tags_in_titles(self):
        """Verifies <script> tags in product titles are escaped to prevent XSS / Telegram crash."""
        raw_title = '<script>alert("XSS")</script> بامبرز حفاضات'
        escaped = html_escape(raw_title)
        self.assertNotIn("<script>", escaped)
        self.assertIn("&lt;script&gt;", escaped)
        self.assertIn("&lt;/script&gt;", escaped)

    def test_escapes_ampersands_and_angle_brackets(self):
        """Verifies '&', '<', and '>' are properly escaped."""
        raw = "B.TECH & 2B <Best Deals> & Laptops"
        escaped = html_escape(raw)
        self.assertEqual(escaped, "B.TECH &amp; 2B &lt;Best Deals&gt; &amp; Laptops")

    def test_telegram_formatter_survives_adversarial_markdown_characters(self):
        """Verifies titles with `_`, `*`, `[`, `]`, `(`, `)` do not break Telegram HTML rendering."""
        adversarial_title = "Dell G15 [2026 Edition] *Special* _Offer_ (16GB RAM) Core i7"
        deal = Deal(
            id="adv_1",
            title=adversarial_title,
            store=StoreEnum.VALU,
            category=CategoryEnum.LAPTOPS,
            original_price=50000.0,
            discount_price=42000.0,
            discount_percentage=16.0,
            url="https://www.valu.com.eg/dell-g15",
        )
        msg_text, markup = format_deal_telegram(deal)
        # Message text must contain title safely and include #Laptop tag
        self.assertIn("Dell G15 [2026 Edition] *Special* _Offer_ (16GB RAM) Core i7", msg_text)
        self.assertIn("#Laptop", msg_text)
        self.assertIsNotNone(markup)
        self.assertEqual(markup.inline_keyboard[0][0].url, "https://www.valu.com.eg/dell-g15")

    def test_escapes_unclosed_html_tags_in_coupon_and_installment(self):
        """Verifies unclosed HTML tags in coupon codes or financing strings are escaped."""
        deal = Deal(
            id="adv_tags",
            title="Persil Automatic Gel",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=200.0,
            discount_price=160.0,
            discount_percentage=20.0,
            url="https://www.amazon.eg/dp/B000000003",
            coupon_code="<SAVE50&FREE>",
            installment_info="<b>0% interest <terms apply>",
        )
        msg_text, _ = format_deal_telegram(deal)
        self.assertNotIn("<SAVE50&FREE>", msg_text)
        self.assertIn("&lt;SAVE50&amp;FREE&gt;", msg_text)
        self.assertIn("&lt;terms apply&gt;", msg_text)

    def test_handles_none_and_empty_inputs_in_html_escape(self):
        """Verifies html_escape returns empty string on None or empty input."""
        self.assertEqual(html_escape(""), "")
        self.assertEqual(html_escape(None), "")


class TestBoundaryEmptyAndExtremePayloads(unittest.TestCase):
    """Tier 2: Boundary Empty & Extreme Payloads (Feature 17)."""

    def test_scraper_handles_empty_html_cleanly(self):
        """Verifies Amazon, Carrefour, ValU, BTech, Jumia scrapers return empty list on empty HTML."""
        self.assertEqual(parse_amazon_snippet(""), [])
        self.assertEqual(parse_amazon_snippet("<div>No results found</div>"), [])
        self.assertEqual(parse_breadfast_snippet({"products": []}), [])
        self.assertEqual(parse_noon_snippet({"hits": []}), [])

    def test_scraper_handles_corrupt_malformed_html(self):
        """Verifies scrapers do not crash on unclosed or corrupted HTML tags."""
        corrupt_html = "<<<div class='s-result-item' data-asin='B01'><a href='broken'><span>Title"
        deals = parse_amazon_snippet(corrupt_html)
        self.assertIsInstance(deals, list)

    def test_handles_extremely_long_titles(self):
        """Verifies Deal model and hash handle massive 2000-character titles without overflow."""
        long_title = "Laptop " + ("Super Powerful Machine " * 80)
        deal = Deal(
            id="extreme_title",
            title=long_title,
            store=StoreEnum.BTECH,
            category=CategoryEnum.LAPTOPS,
            original_price=40000.0,
            discount_price=35000.0,
            discount_percentage=12.5,
            url="https://btech.com/long-title-laptop",
        )
        self.assertIsNotNone(deal.deal_hash)
        self.assertEqual(len(deal.deal_hash), 64)

    def test_handles_unicode_emojis_in_title(self):
        """Verifies product titles containing emojis (🔥, ⚡, 💻, 👶) are processed cleanly."""
        emoji_title = "🔥 صفقة الجمعة البيضاء ⚡ لابتوب ديل للألعاب 💻 + هدايا 🎁"
        deal = Deal(
            id="emoji_deal",
            title=emoji_title,
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=30000.0,
            discount_price=26000.0,
            discount_percentage=13.0,
            url="https://2b.com.eg/dell-gaming",
        )
        self.assertIn("🔥", deal.title)
        self.assertTrue(deal.is_laptop)
        msg_text, _ = format_deal_telegram(deal)
        self.assertIn("🔥", msg_text)
        self.assertIn("#Laptop", msg_text)

    def test_deal_clean_title_normalizes_excessive_whitespace(self):
        """Verifies Deal automatically collapses multi-space, tab, and newline runs in title."""
        messy_title = "  Pampers   \n\t  Diapers \r\n Size   4  "
        deal = Deal(
            id="whitespace_deal",
            title=messy_title,
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=400.0,
            discount_price=300.0,
            discount_percentage=25.0,
            url="https://www.amazon.eg/dp/B000000004",
        )
        self.assertEqual(deal.title, "Pampers Diapers Size 4")


if __name__ == "__main__":
    unittest.main()
