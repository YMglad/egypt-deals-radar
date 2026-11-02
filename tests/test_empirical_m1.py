"""
Adversarial and Empirical Stress Test Suite for Milestone 1 (M1).
Authored by Teamwork Challenger (critic, specialist).

Covers:
1. URL Canonicalization Fuzzing (casing, fragments, tracking params, unicode, sorting, ASIN)
2. Adversarial Category Classification (laptops vs accessories, baby wipes/diapers/clothes/detergent, clothing vs household)
3. Deduplication State Transitions (10-cycle laptop spam test)
4. Price Drop Delta Transitions & Cooldown State Machine (1%, 4.9%, 5%, 10%, price increases, cumulative drops)
"""

import os
import unittest
import tempfile
import sqlite3
import datetime
from urllib.parse import urlparse

from core.models import (
    StoreEnum,
    CategoryEnum,
    Deal,
    canonicalize_url,
    compute_deal_hash,
)
from core.classifier import (
    classify_deal,
    tag_deal_category,
    normalize_arabic,
)
from database.db_service import DatabaseService


class TestURLCanonicalizationAdversarial(unittest.TestCase):
    """Stress tests and fuzzing for URL Canonicalization."""

    def test_tracking_parameter_fuzzing(self):
        """Verify comprehensive stripping of marketing & telemetry parameters."""
        fuzz_params = [
            "utm_source=google",
            "utm_medium=cpc",
            "utm_campaign=black_friday_2026",
            "utm_term=laptops",
            "utm_content=banner_v2",
            "ref=deal_of_the_day",
            "ref_=sr_1_1",
            "tag=deals01-21",
            "ascsubtag=affiliate_tracking_token_123",
            "fbclid=IwAR2x123abc456def789",
            "gclid=CjwKCAjw123_EiwA456",
            "_ga=GA1.2.123456789",
            "campaign_id=998877",
            "ad_id=554433",
            "gbraid=0AAAAAD",
            "wbraid=0AAAAAD",
            "source=mobile_app",
            "spm=a2g0o.productlist.0.0",
            "igshid=YmMyMTA2M2Y=",
            "msclkid=abcdef0123456789",
            "dclid=CPT123456",
            "sc_channel=ppc",
            "sc_campaign=egypt_deals",
            "sc_country=EG",
            "sc_geo=Cairo",
        ]
        query = "&".join(fuzz_params) + "&keep_param=valid_sku_123"
        url = f"https://www.jumia.com.eg/catalog/product?{query}#section-reviews"
        canonical = canonicalize_url(url)
        self.assertEqual(canonical, "https://www.jumia.com.eg/catalog/product?keep_param=valid_sku_123")
        self.assertNotIn("#", canonical)
        self.assertNotIn("utm_", canonical)
        self.assertNotIn("fbclid", canonical)

    def test_query_parameter_sorting_determinism(self):
        """Query parameters in different orders must produce identical canonical URLs."""
        u1 = "https://2b.com.eg/laptops?z_param=last&a_param=first&m_param=middle"
        u2 = "https://2b.com.eg/laptops?m_param=middle&z_param=last&a_param=first"
        u3 = "https://2b.com.eg/laptops?a_param=first&m_param=middle&z_param=last"
        c1 = canonicalize_url(u1)
        c2 = canonicalize_url(u2)
        c3 = canonicalize_url(u3)
        self.assertEqual(c1, c2)
        self.assertEqual(c2, c3)
        self.assertEqual(c1, "https://2b.com.eg/laptops?a_param=first&m_param=middle&z_param=last")

    def test_amazon_asin_normalization_variants(self):
        """Verify Amazon URLs with various path structures reduce to /dp/{ASIN}."""
        variants = [
            ("https://www.amazon.eg/Apple-MacBook-Air-13-inch/dp/B08N5WRWNW/?ref=sr_1_1", "https://www.amazon.eg/dp/B08N5WRWNW"),
            ("https://amazon.eg/gp/product/B08N5WRWNW?tag=deal01-21", "https://amazon.eg/dp/B08N5WRWNW"),
            ("HTTP://WWW.AMAZON.EG/dp/b08n5wrwnw/", "https://www.amazon.eg/dp/B08N5WRWNW"),
            ("https://www.amazon.eg/لابتوب-اسوس-روج-ستريكس/dp/B0CX234XYZ?th=1", "https://www.amazon.eg/dp/B0CX234XYZ?th=1"),
        ]
        for raw, expected in variants:
            with self.subTest(raw=raw):
                self.assertEqual(canonicalize_url(raw), expected)

    def test_international_and_arabic_paths(self):
        """URLs containing Arabic slugs and search queries must be preserved and cleaned."""
        raw = "https://www.noon.com/egypt-ar/حفاضات-بامبرز-مقاس-4/p-12345/?utm_source=cpc#reviews"
        canonical = canonicalize_url(raw)
        self.assertNotIn("utm_source", canonical)
        self.assertNotIn("#reviews", canonical)
        self.assertTrue(canonical.startswith("https://www.noon.com/egypt-ar/"))

    def test_malformed_and_empty_urls(self):
        """Ensure empty or invalid inputs raise ValueError."""
        invalid_inputs = ["", "   ", "#", "   #   "]
        for bad in invalid_inputs:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    canonicalize_url(bad)


class TestCategoryClassifierAdversarial(unittest.TestCase):
    """Adversarial stress-testing of regex classifier rules and Arabic normalization."""

    def test_laptop_vs_accessories_english(self):
        """English laptop accessories must never be tagged as LAPTOPS."""
        accessories = [
            ("Lenovo 15.6 Laptop Everyday Backpack B515", CategoryEnum.CLOTHING_ADULT_KIDS),
            ("Dell Pro Sleeve 15 for Laptop", CategoryEnum.CLOTHING_ADULT_KIDS),
            ("UGREEN Ergonomic Aluminum Laptop Stand", CategoryEnum.HOUSEHOLD_GENERAL),
            ("Baseus 65W GaN USB-C Laptop Charger", CategoryEnum.HOUSEHOLD_GENERAL),
            ("Razer Protective Vinyl Laptop Skin Sticker", CategoryEnum.HOUSEHOLD_GENERAL),
        ]
        for title, expected in accessories:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.AMAZON_EG)
                self.assertNotEqual(cat, CategoryEnum.LAPTOPS, f"'{title}' should not be LAPTOPS")

    def test_laptop_vs_accessories_arabic_ta_marbuta(self):
        """Arabic laptop accessories with Ta Marbuta (ة) must not be tagged as LAPTOPS."""
        accessories = [
            "شنطة ظهر لابتوب مقاس 15.6 بوصة",
            "حقيبة لابتوب مقاومة للماء",
            "حامل لابتوب معدني قابل للطي",
            "قاعدة تبريد لابتوب مزودة بمروحة",
        ]
        for title in accessories:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.AMAZON_EG)
                self.assertNotEqual(cat, CategoryEnum.LAPTOPS, f"'{title}' with 'ة' must not be LAPTOPS")

    def test_laptop_vs_accessories_arabic_ha_vulnerability(self):
        """
        Adversarial Challenge: Arabic laptop accessories ending in Ha (ه) instead of Ta Marbuta (ة).
        Exposes whether normalize_arabic vs LAPTOP_ACCESSORY_EXCLUSION has a mismatch bug.
        """
        accessories_with_ha = [
            "شنطه لابتوب 15.6 بوصه ضد الصدمات",
            "حقيبه لابتوب ظهر خفيفه",
            "قاعده لابتوب معدنيه قابله للتعديل",
            "سماعه لابتوب بلوتوث لاسلكيه",
            "وصله لابتوب يو اس بي تايب سي",
        ]
        for title in accessories_with_ha:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.AMAZON_EG)
                self.assertNotEqual(
                    cat, CategoryEnum.LAPTOPS,
                    f"BUG DETECTED: Accessory '{title}' spelled with 'ه' was classified as LAPTOPS!"
                )

    def test_genuine_laptops_detection(self):
        """Genuine laptops must reliably be tagged as LAPTOPS."""
        laptops = [
            "ASUS ROG Strix SCAR 18 G834JYR Core i9-14900HX RTX 4090",
            "Apple MacBook Pro 16 M3 Max 36GB 1TB",
            "Lenovo Legion Pro 7i 16 Gaming Laptop",
            "Dell XPS 15 9530 Core i7-13700H RTX 4060",
            "لابتوب ايسوس روج ستريكس اسكار 18 جيمنج",
            "حاسوب محمول اتش بي بافيليون 15 رايزن 7",
            "كمبيوتر محمول ايسر نيترو 5 جيمنج",
        ]
        for title in laptops:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.TWO_B)
                self.assertEqual(cat, CategoryEnum.LAPTOPS, f"'{title}' must be classified as LAPTOPS")

    def test_arabic_laptops_without_explicit_word_laptop(self):
        """
        Adversarial Challenge: Arabic laptop listings that use brand/model transliterations
        without the literal generic word 'لابتوب'.
        """
        arabic_laptops = [
            "ابل ماك بوك برو 14 شريحة M3 شاشة ريتينا",
            "لينوفو ثينك باد E14 الجيل الخامس انتل كور i5",
            "اتش بي بافيليون 15 انتل كور i7 الجيل 13",
            "ديل لاتيتيود 5420 كور i5 رام 16 جيجا",
        ]
        for title in arabic_laptops:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.BTECH)
                self.assertEqual(
                    cat, CategoryEnum.LAPTOPS,
                    f"VULNERABILITY: Arabic laptop '{title}' missed LAPTOPS classification"
                )

    def test_baby_diapers_and_wipes(self):
        """Baby diapers and baby wipes must be classified as BABY_DIAPERS."""
        diapers_and_wipes = [
            "حفاضات بامبرز عناية مميزة مقاس 4 عبوة جامبو 120 حفاضة",
            "بامبرز كلوت مقاس 5 حماية فائقة",
            "حفاضات مولفيكس مقاس 3 ميدي 58 حفاضة",
            "فاين بيبي حفاضات اطفال مقاس 4 كبير",
            "مناديل مبللة للأطفال بامبرز سينسيتيف 56 منديل",
            "وايبس اطفال بيبي جوي مرطبة خالية من الكحول",
            "Pampers Premium Protection Size 4 108 Diapers",
            "Huggies Natural Care Baby Wipes 64 wipes",
        ]
        for title in diapers_and_wipes:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.AMAZON_EG)
                self.assertEqual(cat, CategoryEnum.BABY_DIAPERS)

    def test_baby_clothes_vs_detergent_adversarial(self):
        """
        Adversarial Challenge: Laundry detergents for baby clothes should be HOUSEHOLD_GENERAL,
        not BABY_CLOTHES.
        """
        baby_detergents = [
            "مسحوق غسيل ملابس اطفال اوتوماتيك",
            "سائل غسيل ملابس اطفال سنوفا 1 لتر",
            "اريال منظف ملابس رضع مضاد للبكتيريا",
        ]
        for title in baby_detergents:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.CARREFOUR_EG)
                self.assertEqual(
                    cat, CategoryEnum.HOUSEHOLD_GENERAL,
                    f"MISCLASSIFICATION: Baby laundry detergent '{title}' was tagged as {cat.name} instead of HOUSEHOLD_GENERAL"
                )

    def test_adult_incontinence_exclusion(self):
        """Adult diapers/incontinence products must NOT be tagged as BABY_DIAPERS."""
        adult_products = [
            "حفاضات كبار السن تينيا سليب مقاس كبير L",
            "حفاضات سلس البول لكبار السن ديبيند",
            "Tena Slip Maxi Adult Diaper Size Large",
        ]
        for title in adult_products:
            with self.subTest(title=title):
                cat = classify_deal(title, StoreEnum.AMAZON_EG)
                self.assertNotEqual(cat, CategoryEnum.BABY_DIAPERS)


class TestDeduplicationStateTransitions(unittest.TestCase):
    """Empirical verification of deduplication state transitions and spam prevention."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = DatabaseService(self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except Exception:
                pass

    def test_ten_scan_cycles_constant_price_laptop(self):
        """
        Mandatory M1 Test:
        Simulate 10 scan cycles of a single laptop item where price stays constant.
        Must verify EXACTLY 1 alert on cycle 1, and ZERO duplicate alerts on cycles 2..10.
        """
        laptop = Deal(
            id="asus_scar_18_m1",
            title="ASUS ROG Strix SCAR 18 Core i9 14900HX RTX 4090 32GB 2TB",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=175000.0,
            discount_price=159999.0,
            discount_percentage=8.6,
            url="https://2b.com.eg/asus-rog-strix-scar-18.html",
        )
        self.assertTrue(laptop.is_special_laptop)

        alerts_log = []
        for cycle in range(1, 11):
            is_alert, reason = self.db.process_and_deduplicate(laptop)
            alerts_log.append((cycle, is_alert, reason))

        # Cycle 1 must trigger NEW_DEAL
        self.assertTrue(alerts_log[0][1], "Cycle 1 must alert for new deal")
        self.assertEqual(alerts_log[0][2], "NEW_DEAL")

        # Cycles 2 to 10 must all be suppressed
        for cycle, is_alert, reason in alerts_log[1:]:
            self.assertFalse(is_alert, f"Cycle {cycle} triggered duplicate alert: {reason}")
            self.assertEqual(reason, "UNCHANGED_SUPPRESSED")

        total_alerts = sum(1 for _, is_alert, _ in alerts_log if is_alert)
        self.assertEqual(total_alerts, 1, f"Expected exactly 1 alert across 10 cycles, got {total_alerts}")


class TestPriceDropTransitionsAndCooldown(unittest.TestCase):
    """Empirical verification of price delta thresholds and 60-min cooldown guard."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db = DatabaseService(self.tmp.name)

    def tearDown(self):
        if os.path.exists(self.tmp.name):
            try:
                os.unlink(self.tmp.name)
            except Exception:
                pass

    def _set_last_notified_past(self, deal_id: str, minutes_ago: int = 70):
        """Directly adjust last_notified_at in SQLite for deterministic time testing."""
        conn = sqlite3.connect(self.tmp.name)
        past_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
        conn.execute(
            "UPDATE deals SET last_notified_at = ? WHERE id = ?",
            (past_dt.isoformat(), deal_id)
        )
        conn.commit()
        conn.close()

    def test_rapid_fire_queries_within_cooldown(self):
        """
        Within 60-min cooldown:
        - 1% drop -> COOLDOWN_SUPPRESSED (False)
        - 4.9% drop -> COOLDOWN_SUPPRESSED (False)
        - 5.0% drop -> COOLDOWN_SUPPRESSED (False)
        - 10.0% drop -> PRICE_DROP_5PCT (True) [Bypasses cooldown]
        - Price increase -> PRICE_INCREASE_SUPPRESSED (False)
        """
        base = Deal(
            id="pampers_pants_4",
            title="Pampers Pants Size 4",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=1000.0,
            discount_price=1000.0,
            discount_percentage=0.0,
            url="https://amazon.eg/dp/B001",
        )
        alert0, reason0 = self.db.process_and_deduplicate(base)
        self.assertTrue(alert0)
        self.assertEqual(reason0, "NEW_DEAL")

        # 1% drop (1000 -> 990)
        d_1 = Deal("pampers_pants_4", "Pampers Pants Size 4", StoreEnum.AMAZON_EG, CategoryEnum.BABY_DIAPERS, 1000.0, 990.0, 1.0, "https://amazon.eg/dp/B001")
        a1, r1 = self.db.process_and_deduplicate(d_1)
        self.assertFalse(a1)
        self.assertEqual(r1, "COOLDOWN_SUPPRESSED")

        # 4.9% drop (1000 -> 951)
        d_49 = Deal("pampers_pants_4", "Pampers Pants Size 4", StoreEnum.AMAZON_EG, CategoryEnum.BABY_DIAPERS, 1000.0, 951.0, 4.9, "https://amazon.eg/dp/B001")
        a49, r49 = self.db.process_and_deduplicate(d_49)
        self.assertFalse(a49)
        self.assertEqual(r49, "COOLDOWN_SUPPRESSED")

        # 5.0% drop (1000 -> 950) within cooldown
        d_50 = Deal("pampers_pants_4", "Pampers Pants Size 4", StoreEnum.AMAZON_EG, CategoryEnum.BABY_DIAPERS, 1000.0, 950.0, 5.0, "https://amazon.eg/dp/B001")
        a50, r50 = self.db.process_and_deduplicate(d_50)
        self.assertFalse(a50, "5% drop within 60-min cooldown must be suppressed")
        self.assertEqual(r50, "COOLDOWN_SUPPRESSED")

        # 10.0% drop (1000 -> 900) within cooldown -> MUST ALERT!
        d_100 = Deal("pampers_pants_4", "Pampers Pants Size 4", StoreEnum.AMAZON_EG, CategoryEnum.BABY_DIAPERS, 1000.0, 900.0, 10.0, "https://amazon.eg/dp/B001")
        a100, r100 = self.db.process_and_deduplicate(d_100)
        self.assertTrue(a100, "10% drop must bypass cooldown and alert")
        self.assertEqual(r100, "PRICE_DROP_5PCT")

        # Price increase (900 -> 950)
        d_inc = Deal("pampers_pants_4", "Pampers Pants Size 4", StoreEnum.AMAZON_EG, CategoryEnum.BABY_DIAPERS, 1000.0, 950.0, 5.0, "https://amazon.eg/dp/B001")
        ainc, rinc = self.db.process_and_deduplicate(d_inc)
        self.assertFalse(ainc)
        self.assertEqual(rinc, "PRICE_INCREASE_SUPPRESSED")

    def test_price_drops_after_cooldown_expired(self):
        """
        After 60-min cooldown expired:
        - 1.0% drop -> MINOR_DROP_SUPPRESSED (False)
        - 4.9% drop -> MINOR_DROP_SUPPRESSED (False)
        - 5.0% drop -> PRICE_DROP_5PCT (True)
        - 10.0% drop -> PRICE_DROP_5PCT (True)
        """
        base = Deal(
            id="tide_gel_3l",
            title="Tide Automatic Gel 3L",
            store=StoreEnum.NOON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1000.0,
            discount_price=1000.0,
            discount_percentage=0.0,
            url="https://noon.com/p-999",
        )
        self.db.process_and_deduplicate(base)

        # 1.0% drop after cooldown
        self._set_last_notified_past("tide_gel_3l", minutes_ago=75)
        d_1 = Deal("tide_gel_3l", "Tide Automatic Gel 3L", StoreEnum.NOON_EG, CategoryEnum.HOUSEHOLD_GENERAL, 1000.0, 990.0, 1.0, "https://noon.com/p-999")
        a1, r1 = self.db.process_and_deduplicate(d_1)
        self.assertFalse(a1)
        self.assertEqual(r1, "MINOR_DROP_SUPPRESSED")

        # 4.9% drop after cooldown
        self._set_last_notified_past("tide_gel_3l", minutes_ago=75)
        d_49 = Deal("tide_gel_3l", "Tide Automatic Gel 3L", StoreEnum.NOON_EG, CategoryEnum.HOUSEHOLD_GENERAL, 1000.0, 951.0, 4.9, "https://noon.com/p-999")
        a49, r49 = self.db.process_and_deduplicate(d_49)
        self.assertFalse(a49)
        self.assertEqual(r49, "MINOR_DROP_SUPPRESSED")

        # 5.0% drop after cooldown -> MUST ALERT!
        self._set_last_notified_past("tide_gel_3l", minutes_ago=75)
        d_50 = Deal("tide_gel_3l", "Tide Automatic Gel 3L", StoreEnum.NOON_EG, CategoryEnum.HOUSEHOLD_GENERAL, 1000.0, 950.0, 5.0, "https://noon.com/p-999")
        a50, r50 = self.db.process_and_deduplicate(d_50)
        self.assertTrue(a50, "5% drop after cooldown must alert")
        self.assertEqual(r50, "PRICE_DROP_5PCT")


if __name__ == "__main__":
    unittest.main()
