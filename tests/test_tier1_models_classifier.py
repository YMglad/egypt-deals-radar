"""
Tier 1 Tests: Canonical Data Models, Enums, URL Canonicalization,
Hash Calculation, and Category Classifier.

Covers:
- Feature 1: Canonical Deal Data Model (>= 5 tests)
- Feature 2: Store Enum & Alias Resolution (>= 5 tests)
- Feature 3: Category Enum & Alias Resolution (>= 5 tests)
- Feature 4: URL Canonicalization (>= 5 tests)
- Feature 5: SHA-256 Deal Fingerprinting (>= 5 tests)
- Feature 6: Category Classifier - Dedicated Laptops (>= 5 tests)
- Feature 7: Category Classifier - Baby Diapers (>= 5 tests)
- Feature 8: Category Classifier - Baby Clothes (>= 5 tests)
- Feature 9: Category Classifier - Adult & Kids Clothing (>= 5 tests)
- Feature 10: Category Classifier - Household General (>= 5 tests)
"""

import unittest
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


class TestCanonicalDealModel(unittest.TestCase):
    """Tier 1: Canonical Deal Data Model (Feature 1)."""

    def test_deal_creation_with_valid_attributes(self):
        """Test happy path instantiation with full attributes."""
        deal = Deal(
            id="amazon_eg_B09XYZ",
            title="Pampers Premium Protection Size 4",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=500.0,
            discount_price=350.0,
            discount_percentage=30.0,
            url="https://www.amazon.eg/dp/B09XYZ",
            image_url="https://images.amazon.com/pampers.jpg",
            is_flash_sale=True,
            coupon_code="SAVE50",
            installment_info="0% interest with valU",
        )
        self.assertEqual(deal.id, "amazon_eg_B09XYZ")
        self.assertEqual(deal.store, StoreEnum.AMAZON_EG)
        self.assertEqual(deal.category, CategoryEnum.BABY_DIAPERS)
        self.assertEqual(deal.original_price, 500.0)
        self.assertEqual(deal.discount_price, 350.0)
        self.assertEqual(deal.discount_percentage, 30.0)
        self.assertEqual(deal.discount_amount, 150.0)
        self.assertFalse(deal.is_laptop)
        self.assertIsNotNone(deal.deal_hash)

    def test_deal_discount_percentage_auto_calculation(self):
        """Verifies discount percentage is automatically computed when omitted or 0."""
        deal = Deal(
            id="noon_1",
            title="Persil Automatic Gel 3L",
            store=StoreEnum.NOON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=200.0,
            discount_price=150.0,
            discount_percentage=0.0,
            url="https://www.noon.com/egypt-en/p-101",
        )
        self.assertAlmostEqual(deal.discount_percentage, 25.0, places=1)
        self.assertEqual(deal.discount_amount, 50.0)

    def test_deal_laptop_category_auto_flags_is_special_laptop(self):
        """Verifies Deal automatically sets is_special_laptop=True when category is LAPTOPS."""
        deal = Deal(
            id="jumia_lp1",
            title="Lenovo Legion 5 Laptop",
            store=StoreEnum.JUMIA_EG,
            category=CategoryEnum.LAPTOPS,
            original_price=50000.0,
            discount_price=45000.0,
            discount_percentage=10.0,
            url="https://www.jumia.com.eg/lenovo-legion-5.html",
        )
        self.assertTrue(deal.is_special_laptop)
        self.assertTrue(deal.is_laptop)

    def test_deal_to_dict_serialization(self):
        """Verifies serialization to dictionary format with primitive types."""
        deal = Deal(
            id="breadfast_1",
            title="Baby Diapers Pack 50",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=300.0,
            discount_price=240.0,
            discount_percentage=20.0,
            url="https://www.breadfast.com/product/diapers",
            coupon_code="BF10",
        )
        d = deal.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["id"], "breadfast_1")
        self.assertEqual(d["store"], StoreEnum.BREADFAST.value)
        self.assertEqual(d["category"], CategoryEnum.BABY_DIAPERS.value)
        self.assertEqual(d["discount_price"], 240.0)
        self.assertEqual(d["coupon_code"], "BF10")
        self.assertIn("deal_hash", d)

    def test_deal_from_dict_deserialization(self):
        """Verifies deserialization from raw dictionary into Deal instance."""
        payload = {
            "id": "talabat_99",
            "title": "Fairy Dishwashing Liquid 650ml",
            "store": "Talabat Egypt",
            "category": "مستلزمات منزلية",
            "original_price": 50.0,
            "discount_price": 40.0,
            "discount_percentage": 20.0,
            "url": "https://www.talabat.com/item/99",
            "is_flash_sale": 0,
            "is_special_laptop": 0,
        }
        deal = Deal.from_dict(payload)
        self.assertEqual(deal.id, "talabat_99")
        self.assertEqual(deal.store, StoreEnum.TALABAT)
        self.assertEqual(deal.category, CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(deal.discount_price, 40.0)
        self.assertFalse(deal.is_laptop)


class TestStoreEnumResolution(unittest.TestCase):
    """Tier 1: Store Enum & Alias Resolution (Feature 2)."""

    def test_all_9_authoritative_stores_exist(self):
        """Verifies exactly the 9 authoritative Egyptian retailers are defined."""
        expected_stores = {
            "AMAZON_EG": "Amazon Egypt",
            "NOON_EG": "Noon Egypt",
            "BREADFAST": "Breadfast",
            "TALABAT": "Talabat Egypt",
            "VALU": "ValU",
            "CARREFOUR_EG": "Carrefour Egypt",
            "JUMIA_EG": "Jumia Egypt",
            "BTECH": "B.TECH",
            "TWO_B": "2B Egypt",
        }
        for name, value in expected_stores.items():
            member = getattr(StoreEnum, name)
            self.assertEqual(member.value, value)

    def test_resolve_store_from_english_aliases(self):
        """Verifies resolution from common English aliases."""
        self.assertEqual(StoreEnum.from_str("amazon"), StoreEnum.AMAZON_EG)
        self.assertEqual(StoreEnum.from_str("noon eg"), StoreEnum.NOON_EG)
        self.assertEqual(StoreEnum.from_str("carrefour egypt"), StoreEnum.CARREFOUR_EG)
        self.assertEqual(StoreEnum.from_str("btech"), StoreEnum.BTECH)
        self.assertEqual(StoreEnum.from_str("2b"), StoreEnum.TWO_B)

    def test_resolve_store_from_arabic_aliases(self):
        """Verifies resolution from Arabic store names."""
        self.assertEqual(StoreEnum.from_str("أمازون"), StoreEnum.AMAZON_EG)
        self.assertEqual(StoreEnum.from_str("نون"), StoreEnum.NOON_EG)
        self.assertEqual(StoreEnum.from_str("بريدفاست"), StoreEnum.BREADFAST)
        self.assertEqual(StoreEnum.from_str("طلبات"), StoreEnum.TALABAT)
        self.assertEqual(StoreEnum.from_str("فاليو"), StoreEnum.VALU)
        self.assertEqual(StoreEnum.from_str("كارفور"), StoreEnum.CARREFOUR_EG)
        self.assertEqual(StoreEnum.from_str("جوميا"), StoreEnum.JUMIA_EG)
        self.assertEqual(StoreEnum.from_str("بي تك"), StoreEnum.BTECH)
        self.assertEqual(StoreEnum.from_str("توبي"), StoreEnum.TWO_B)

    def test_resolve_store_from_enum_instance(self):
        """Verifies passing an existing enum instance returns itself."""
        self.assertEqual(StoreEnum.from_str(StoreEnum.CARREFOUR_EG), StoreEnum.CARREFOUR_EG)

    def test_resolve_store_unknown_fallback(self):
        """Verifies unknown store string safely falls back to default store."""
        fallback = StoreEnum.from_str("Unknown Retailer 123")
        self.assertEqual(fallback, StoreEnum.AMAZON_EG)


class TestCategoryEnumResolution(unittest.TestCase):
    """Tier 1: Category Enum & Alias Resolution (Feature 3)."""

    def test_all_5_target_categories_exist(self):
        """Verifies all 5 target categories exist with Arabic display names."""
        self.assertEqual(CategoryEnum.BABY_DIAPERS.value, "حفاضات أطفال")
        self.assertEqual(CategoryEnum.BABY_CLOTHES.value, "ملابس رضع وأطفال")
        self.assertEqual(CategoryEnum.CLOTHING_ADULT_KIDS.value, "أزياء وملابس")
        self.assertEqual(CategoryEnum.HOUSEHOLD_GENERAL.value, "مستلزمات منزلية")
        self.assertEqual(CategoryEnum.LAPTOPS.value, "لابتوبات وأجهزة")

    def test_resolve_category_english_aliases(self):
        """Verifies resolution from common English aliases."""
        self.assertEqual(CategoryEnum.from_str("baby_diapers"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(CategoryEnum.from_str("diapers"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(CategoryEnum.from_str("baby_clothes"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(CategoryEnum.from_str("clothing"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(CategoryEnum.from_str("fashion"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(CategoryEnum.from_str("household"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(CategoryEnum.from_str("laptops"), CategoryEnum.LAPTOPS)

    def test_resolve_category_arabic_names(self):
        """Verifies resolution from Arabic category names."""
        self.assertEqual(CategoryEnum.from_str("حفاضات"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(CategoryEnum.from_str("ملابس رضع"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(CategoryEnum.from_str("أزياء"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(CategoryEnum.from_str("مستلزمات منزلية"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(CategoryEnum.from_str("لابتوب"), CategoryEnum.LAPTOPS)

    def test_resolve_category_from_enum_instance(self):
        """Verifies passing CategoryEnum returns itself."""
        self.assertEqual(CategoryEnum.from_str(CategoryEnum.LAPTOPS), CategoryEnum.LAPTOPS)

    def test_resolve_category_fallback(self):
        """Verifies unknown category strings default to HOUSEHOLD_GENERAL."""
        self.assertEqual(CategoryEnum.from_str("Automotive Tires"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(CategoryEnum.from_str(None), CategoryEnum.HOUSEHOLD_GENERAL)


class TestURLCanonicalization(unittest.TestCase):
    """Tier 1: URL Canonicalization (Feature 4)."""

    def test_strips_utm_and_tracking_parameters(self):
        """Verifies removal of utm_source, utm_medium, fbclid, and ref tokens."""
        raw_url = "https://www.noon.com/p-123?utm_source=cpc&utm_medium=banner&fbclid=abc1234&page=1"
        clean = canonicalize_url(raw_url)
        self.assertNotIn("utm_source", clean)
        self.assertNotIn("utm_medium", clean)
        self.assertNotIn("fbclid", clean)
        self.assertIn("page=1", clean)

    def test_amazon_asin_canonical_path_extraction(self):
        """Verifies Amazon product links are normalized to clean /dp/ASIN format."""
        raw_amazon = "https://www.amazon.eg/Pampers-Diapers-Size-4/dp/B09ABC1234/ref=sr_1_1?tag=affil"
        clean = canonicalize_url(raw_amazon)
        self.assertEqual(clean, "https://www.amazon.eg/dp/B09ABC1234")

    def test_normalizes_http_to_https(self):
        """Verifies insecure http URLs are promoted to https."""
        clean = canonicalize_url("http://btech.com/en/laptop-1.html")
        self.assertTrue(clean.startswith("https://btech.com"))

    def test_strips_trailing_slash_on_paths(self):
        """Verifies trailing slashes are removed from path ends."""
        clean = canonicalize_url("https://2b.com.eg/en/laptops/")
        self.assertEqual(clean, "https://2b.com.eg/en/laptops")

    def test_rejects_empty_or_hash_url(self):
        """Verifies empty, whitespace, or hash '#' URLs raise ValueError."""
        with self.assertRaises(ValueError):
            canonicalize_url("")
        with self.assertRaises(ValueError):
            canonicalize_url("   ")
        with self.assertRaises(ValueError):
            canonicalize_url("#")


class TestDealHashCalculation(unittest.TestCase):
    """Tier 1: SHA-256 Deal Fingerprinting (Feature 5)."""

    def test_deal_hash_determinism(self):
        """Verifies identical inputs produce identical 64-character hex hash."""
        h1 = compute_deal_hash("Amazon Egypt", "https://amazon.eg/dp/B01", 100.0, "SAVE10")
        h2 = compute_deal_hash("Amazon Egypt", "https://amazon.eg/dp/B01", 100.0, "SAVE10")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_deal_hash_changes_with_price_change(self):
        """Verifies that altering the price produces a distinct hash."""
        h1 = compute_deal_hash("Amazon Egypt", "https://amazon.eg/dp/B01", 100.0)
        h2 = compute_deal_hash("Amazon Egypt", "https://amazon.eg/dp/B01", 95.0)
        self.assertNotEqual(h1, h2)

    def test_deal_hash_changes_with_coupon_change(self):
        """Verifies that changing coupon code alters the hash."""
        h1 = compute_deal_hash("Noon Egypt", "https://noon.com/p1", 500.0, "PROMO1")
        h2 = compute_deal_hash("Noon Egypt", "https://noon.com/p1", 500.0, "PROMO2")
        self.assertNotEqual(h1, h2)

    def test_deal_hash_changes_with_store_change(self):
        """Verifies that different stores with same URL/price produce different hashes."""
        h1 = compute_deal_hash("Noon Egypt", "https://store.com/item", 300.0)
        h2 = compute_deal_hash("Jumia Egypt", "https://store.com/item", 300.0)
        self.assertNotEqual(h1, h2)

    def test_deal_hash_none_coupon_treated_consistently(self):
        """Verifies None coupon and empty string coupon evaluate identically."""
        h1 = compute_deal_hash("Breadfast", "https://breadfast.com/p", 250.0, None)
        h2 = compute_deal_hash("Breadfast", "https://breadfast.com/p", 250.0, "")
        self.assertEqual(h1, h2)


class TestCategoryClassifierLaptops(unittest.TestCase):
    """Tier 1: Dedicated Laptops Classifier (Feature 6)."""

    def test_classifies_arabic_laptop_terms(self):
        """Verifies Arabic laptop keywords classify as LAPTOPS."""
        cat1 = classify_deal("لابتوب لينوفو ليجن للألعاب مع كارت شاشة RTX 4060")
        cat2 = classify_deal("حاسوب محمول اتش بي بافيليون 15 بوصة")
        cat3 = classify_deal("لاب توب ايسوس روج ستريكس")
        self.assertEqual(cat1, CategoryEnum.LAPTOPS)
        self.assertEqual(cat2, CategoryEnum.LAPTOPS)
        self.assertEqual(cat3, CategoryEnum.LAPTOPS)

    def test_classifies_major_laptop_gaming_brands(self):
        """Verifies brand names classify as LAPTOPS."""
        self.assertEqual(classify_deal("ASUS ROG Strix G16 Gaming 165Hz"), CategoryEnum.LAPTOPS)
        self.assertEqual(classify_deal("Lenovo Legion 5 AMD Ryzen 7"), CategoryEnum.LAPTOPS)
        self.assertEqual(classify_deal("Apple MacBook Pro 14 M3 Chip"), CategoryEnum.LAPTOPS)
        self.assertEqual(classify_deal("Dell Alienware m16 R2 Gaming"), CategoryEnum.LAPTOPS)
        self.assertEqual(classify_deal("Acer Predator Helios Neo 16"), CategoryEnum.LAPTOPS)

    def test_excludes_laptop_bags_and_sleeves(self):
        """Verifies laptop accessories (bags, backpacks, sleeves) are NOT classified as LAPTOPS."""
        cat_bag_ar = classify_deal("شنطة لابتوب مضادة للماء مقاس 15.6 بوصة")
        cat_bag_en = classify_deal("Waterproof Laptop Backpack 17 inch with USB Port")
        cat_sleeve = classify_deal("Shockproof Neoprene Laptop Sleeve Case")
        self.assertNotEqual(cat_bag_ar, CategoryEnum.LAPTOPS)
        self.assertNotEqual(cat_bag_en, CategoryEnum.LAPTOPS)
        self.assertNotEqual(cat_sleeve, CategoryEnum.LAPTOPS)

    def test_excludes_laptop_stands_and_chargers(self):
        """Verifies laptop stands, holders, and chargers are excluded from LAPTOPS."""
        cat_stand = classify_deal("حامل لابتوب المنيوم قابل للطي")
        cat_charger = classify_deal("Type-C 65W Fast Charger for Laptop")
        self.assertNotEqual(cat_stand, CategoryEnum.LAPTOPS)
        self.assertNotEqual(cat_charger, CategoryEnum.LAPTOPS)

    def test_tag_deal_category_sets_is_special_laptop(self):
        """Verifies tag_deal_category correctly distinguishes ordinary laptops from the special ASUS ROG Strix 18."""
        deal_ordinary = Deal(
            id="d1",
            title="HP Victus 15 Gaming Laptop Intel i5 RTX 3050",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=35000.0,
            discount_price=30000.0,
            discount_percentage=14.0,
            url="https://2b.com.eg/p1",
        )
        tagged_ord = tag_deal_category(deal_ordinary)
        self.assertEqual(tagged_ord.category, CategoryEnum.LAPTOPS)
        self.assertFalse(tagged_ord.is_special_laptop)

        deal_rog = Deal(
            id="d2",
            title="ASUS ROG Strix SCAR 18 G835LX Intel Ultra 9 RTX 5080",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=240000.0,
            discount_price=199999.0,
            discount_percentage=16.7,
            url="https://2b.com.eg/rog18",
        )
        tagged_rog = tag_deal_category(deal_rog)
        self.assertEqual(tagged_rog.category, CategoryEnum.LAPTOPS)
        self.assertTrue(tagged_rog.is_special_laptop)


class TestCategoryClassifierBabyDiapers(unittest.TestCase):
    """Tier 1: Baby Diapers Classifier (Feature 7)."""

    def test_classifies_pampers_and_fine_baby_in_arabic(self):
        """Verifies Arabic diaper brand names."""
        self.assertEqual(classify_deal("بامبرز كلوت عناية مميزة مقاس 4"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(classify_deal("حفاضات فاين بيبي لمسة قطنية مقاس 5"), CategoryEnum.BABY_DIAPERS)

    def test_classifies_molfix_and_baby_joy(self):
        """Verifies Molfix and Baby Joy keywords."""
        self.assertEqual(classify_deal("حفاضات مولفيكس ماكسي عبوة التوفير 58 حفاضة"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(classify_deal("بيبي جوي حفاضات كلوت مضغوط مقاس 3"), CategoryEnum.BABY_DIAPERS)

    def test_classifies_english_diapers_and_nappies(self):
        """Verifies English diaper terms."""
        self.assertEqual(classify_deal("Pampers Premium Care Diapers Size 3 60 Count"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(classify_deal("Molfix Extra Absorbent Baby Nappies Size 4"), CategoryEnum.BABY_DIAPERS)

    def test_classifies_baby_wipes(self):
        """Verifies baby wet wipes classify under diapers & baby hygiene."""
        self.assertEqual(classify_deal("مناديل مبللة للأطفال فائقة النعومة من بامبرز"), CategoryEnum.BABY_DIAPERS)
        self.assertEqual(classify_deal("Fine Baby Wet Wipes Sensitive Skin 64 Pcs"), CategoryEnum.BABY_DIAPERS)

    def test_excludes_adult_incontinence_products(self):
        """Verifies adult diapers are not misclassified as baby diapers."""
        cat_adult = classify_deal("حفاضات لكبار السن مقاس لارج تينا كبار السن")
        self.assertNotEqual(cat_adult, CategoryEnum.BABY_DIAPERS)


class TestCategoryClassifierBabyClothes(unittest.TestCase):
    """Tier 1: Baby Clothes Classifier (Feature 8)."""

    def test_classifies_salopette_and_onesies_in_arabic(self):
        """Verifies Arabic infant garment keywords."""
        self.assertEqual(classify_deal("سالوبيت بيبي قطن صيفي حديثي الولادة"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(classify_deal("سلوبيت أطفال رضع شتوي مبطن فليس"), CategoryEnum.BABY_CLOTHES)

    def test_classifies_english_infant_wear(self):
        """Verifies English terms (romper, bodysuit, onesie)."""
        self.assertEqual(classify_deal("Baby Cotton Romper Long Sleeve Pack of 3"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(classify_deal("Newborn Baby Bodysuit Set Pure Cotton"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(classify_deal("Infant Sleepsuit Onesie with Zipper"), CategoryEnum.BABY_CLOTHES)

    def test_classifies_baby_bibs_and_wear(self):
        """Verifies baby accessories like bibs and toddler wear."""
        self.assertEqual(classify_deal("بافتة أطفال قطنية مضادة للبلل 3 قطع"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(classify_deal("أطقم بيبي أولاد قطعتين خروج"), CategoryEnum.BABY_CLOTHES)

    def test_handles_arabic_letter_normalization(self):
        """Verifies diacritics and Alef variants do not break matching."""
        self.assertEqual(classify_deal("سَالُوبِيت أطْفَال رُضَّع أَقْطَان"), CategoryEnum.BABY_CLOTHES)
        self.assertEqual(classify_deal("ملابس اطفال حديثي الولاده"), CategoryEnum.BABY_CLOTHES)

    def test_classifies_baby_toddler_footies(self):
        """Verifies toddler footies and sleepwear."""
        self.assertEqual(classify_deal("Toddler Footie Cotton Pajama for Girls"), CategoryEnum.BABY_CLOTHES)


class TestCategoryClassifierAdultKidsClothing(unittest.TestCase):
    """Tier 1: Adult & Kids Clothing Classifier (Feature 9)."""

    def test_classifies_hoodies_and_sweatshirts(self):
        """Verifies hoodies and sweatshirts."""
        self.assertEqual(classify_deal("سويت شيرت هودي رجالي قطن كاجوال"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("Men's Fleece Pullover Hoodie Black"), CategoryEnum.CLOTHING_ADULT_KIDS)

    def test_classifies_shirts_and_pants(self):
        """Verifies shirts, trousers, and jeans."""
        self.assertEqual(classify_deal("بنطلون جينز رجالي سليم فيت أزرق"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("قميص كلاسيك رجالي قطن أبيض"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("Women High Waist Stretch Denim Jeans"), CategoryEnum.CLOTHING_ADULT_KIDS)

    def test_classifies_dresses_and_skirts(self):
        """Verifies women's dresses and skirts."""
        self.assertEqual(classify_deal("فستان سهرة كاجوال طويل للمحجبات"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("Floral Printed Summer Maxi Dress"), CategoryEnum.CLOTHING_ADULT_KIDS)

    def test_classifies_shoes_and_sneakers(self):
        """Verifies shoes, sneakers, and footwear."""
        self.assertEqual(classify_deal("حذاء رياضي كوتشي كاجوال أبيض للرجال"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("Nike Air Running Sneakers for Men"), CategoryEnum.CLOTHING_ADULT_KIDS)

    def test_classifies_tracksuits_and_sportswear(self):
        """Verifies tracksuits and sportswear."""
        self.assertEqual(classify_deal("ترنج رياضي خروج قطن شتوي كاجوال"), CategoryEnum.CLOTHING_ADULT_KIDS)
        self.assertEqual(classify_deal("Men's 2-Piece Athletic Tracksuit"), CategoryEnum.CLOTHING_ADULT_KIDS)


class TestCategoryClassifierHouseholdGeneral(unittest.TestCase):
    """Tier 1: Household General Classifier (Feature 10)."""

    def test_classifies_laundry_detergents(self):
        """Verifies laundry detergents (Ariel, Persil, Tide)."""
        self.assertEqual(classify_deal("مسحوق غسيل أوتوماتيك اريال داوني 7 كجم"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("برسيل جل لافندر للغسالات الأوتوماتيك 3.9 لتر"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("Tide Automatic Laundry Powder 5kg"), CategoryEnum.HOUSEHOLD_GENERAL)

    def test_classifies_dishwashing_liquids(self):
        """Verifies dishwashing detergents (Fairy, Pril)."""
        self.assertEqual(classify_deal("سائل غسيل أطباق فيري ليمون مركز 650 مل"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("Fairy Dishwashing Liquid Antibacterial"), CategoryEnum.HOUSEHOLD_GENERAL)

    def test_classifies_air_fryers_and_kitchen_appliances(self):
        """Verifies air fryers, blenders, kettles."""
        self.assertEqual(classify_deal("قلاية هوائية فيليبس بدون زيت 7.2 لتر ديجيتال"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("Philips XXL Airfryer Digital Connected"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("غلاية مياه كهربائية تورنيدو استانلس ستيل"), CategoryEnum.HOUSEHOLD_GENERAL)

    def test_classifies_cookware_and_kitchenware(self):
        """Verifies cookware, pot sets, frying pans."""
        self.assertEqual(classify_deal("طقم حلل جرانيت تركي سافلون 10 قطع"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("Non-stick Granite Frying Pan 28cm"), CategoryEnum.HOUSEHOLD_GENERAL)

    def test_classifies_bedsheets_and_home_cleaning(self):
        """Verifies bedsheets, towels, tissue papers, vacuum cleaners."""
        self.assertEqual(classify_deal("مكنسة كهربائية توشيبا 1800 وات بكيس قماش"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("بكرة مناديل مطبخ زينة عبوة 6 رول"), CategoryEnum.HOUSEHOLD_GENERAL)
        self.assertEqual(classify_deal("طقم ملايات سرير قطن مصري مطرز"), CategoryEnum.HOUSEHOLD_GENERAL)


if __name__ == "__main__":
    unittest.main()
