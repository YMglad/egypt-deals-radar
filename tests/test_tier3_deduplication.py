"""
Tier 3 Tests: Stateful Deduplication, Laptop Spam Prevention, Price Deltas, and Cooldown.

Covers:
- Feature 18: Brand New Deal -> ALERT (NEW_DEAL)
- Feature 19: Unchanged Deal -> SUPPRESS (UNCHANGED_SUPPRESSED)
- Feature 20: Laptop Alert Spam Prevention (Fix for database.py:73 prototype flaw)
- Feature 21: Price Drop Delta Threshold (>= 5% alerts, < 5% or increases suppressed)
- Feature 22: Cooldown Guard Enforcement (60 min cooldown unless >= 10% drop)
- Database persistence: price history, subscribers, category/store queries
"""

import unittest
import datetime
from core.models import StoreEnum, CategoryEnum, Deal
from tests.conftest import get_db_service


class TestTier3DeduplicationEngine(unittest.TestCase):
    """Tier 3: Stateful Deduplication Decision Matrix & State Machine."""

    def setUp(self):
        """Initializes a clean, isolated SQLite test database for each test."""
        self.db = get_db_service()

    def tearDown(self):
        """Cleans up database connection and removes test database file."""
        if hasattr(self.db, "clear_deals"):
            self.db.clear_deals()
        if hasattr(self.db, "conn") and self.db.conn:
            self.db.conn.close()

    def test_new_deal_triggers_alert(self):
        """Case 1: Brand new deal (never alerted before) must return is_alert_worthy=True."""
        deal = Deal(
            id="amazon_diaper_1",
            title="Pampers Pants Size 4",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=450.0,
            discount_price=350.0,
            discount_percentage=22.2,
            url="https://www.amazon.eg/dp/B09ABC1234",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal)
        self.assertTrue(is_alert, "New deal must be alert worthy")
        self.assertEqual(reason, "NEW_DEAL")

        # Verify saved in deals table
        all_deals = self.db.get_all_deals()
        self.assertEqual(len(all_deals), 1)
        self.assertEqual(all_deals[0].id, "amazon_diaper_1")

    def test_unchanged_deal_next_poll_is_suppressed(self):
        """Case 2: Polling identical deal next cycle must return is_alert_worthy=False."""
        deal = Deal(
            id="noon_persil_1",
            title="Persil Automatic Gel 3.9L",
            store=StoreEnum.NOON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=300.0,
            discount_price=240.0,
            discount_percentage=20.0,
            url="https://www.noon.com/egypt-en/p-101",
        )
        # Cycle 1: First poll -> ALERT
        is_alert1, reason1 = self.db.process_and_deduplicate(deal)
        self.assertTrue(is_alert1)
        self.assertEqual(reason1, "NEW_DEAL")

        # Cycle 2: Second poll (90s later, unchanged) -> SUPPRESSED
        is_alert2, reason2 = self.db.process_and_deduplicate(deal)
        self.assertFalse(is_alert2, "Unchanged deal must NOT trigger repeat alert")
        self.assertEqual(reason2, "UNCHANGED_SUPPRESSED")

    def test_laptop_spam_prevention_bug_resolution(self):
        """
        Case 3: CRITICAL FIX for prototype flaw (database.py:73).
        In the old prototype, 'if is_special_laptop:' caused laptop deals to re-alert every 90s!
        This test verifies laptop deals with unchanged prices are SUPPRESSED on repeated polls.
        """
        laptop_deal = Deal(
            id="jumia_legion_5",
            title="Lenovo Legion 5 AMD Ryzen 7 RTX 4060",
            store=StoreEnum.JUMIA_EG,
            category=CategoryEnum.LAPTOPS,
            original_price=60000.0,
            discount_price=52000.0,
            discount_percentage=13.3,
            url="https://www.jumia.com.eg/lenovo-legion-5.html",
        )
        self.assertTrue(laptop_deal.is_special_laptop)

        # Poll 1: Initial discovery -> ALERT
        is_alert1, reason1 = self.db.process_and_deduplicate(laptop_deal)
        self.assertTrue(is_alert1, "Initial laptop discovery must trigger alert")
        self.assertEqual(reason1, "NEW_DEAL")

        # Poll 2: 90 seconds later, same price -> MUST BE SUPPRESSED!
        is_alert2, reason2 = self.db.process_and_deduplicate(laptop_deal)
        self.assertFalse(is_alert2, "Unchanged laptop must be SUPPRESSED, NOT spammed!")
        self.assertEqual(reason2, "UNCHANGED_SUPPRESSED")

        # Poll 3: Another 90 seconds later -> MUST STILL BE SUPPRESSED!
        is_alert3, reason3 = self.db.process_and_deduplicate(laptop_deal)
        self.assertFalse(is_alert3, "Unchanged laptop must remain SUPPRESSED!")
        self.assertEqual(reason3, "UNCHANGED_SUPPRESSED")

    def test_minor_price_drop_below_5pct_is_suppressed(self):
        """Case 4: Price drops by only 2% (< 5% threshold) -> SUPPRESS alert."""
        deal = Deal(
            id="talabat_fairy",
            title="Fairy Liquid 650ml",
            store=StoreEnum.TALABAT,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=60.0,
            discount_price=50.0,
            discount_percentage=16.6,
            url="https://www.talabat.com/fairy",
        )
        self.db.process_and_deduplicate(deal)

        # Price drops from 50.0 to 49.0 (2% drop)
        deal_minor_drop = Deal(
            id="talabat_fairy",
            title="Fairy Liquid 650ml",
            store=StoreEnum.TALABAT,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=60.0,
            discount_price=49.0,
            discount_percentage=18.3,
            url="https://www.talabat.com/fairy",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal_minor_drop)
        self.assertFalse(is_alert, "Minor price drop < 5% must be suppressed")
        self.assertIn("SUPPRESSED", reason)

    def test_price_increase_is_suppressed(self):
        """Case 5: Price increases from 100 to 120 -> SUPPRESS alert."""
        deal = Deal(
            id="valu_appl_1",
            title="Air Fryer XXL",
            store=StoreEnum.VALU,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=10000.0,
            discount_price=7500.0,
            discount_percentage=25.0,
            url="https://www.valu.com.eg/airfryer",
        )
        self.db.process_and_deduplicate(deal)

        # Price goes back up to 8500.0
        deal_increase = Deal(
            id="valu_appl_1",
            title="Air Fryer XXL",
            store=StoreEnum.VALU,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=10000.0,
            discount_price=8500.0,
            discount_percentage=15.0,
            url="https://www.valu.com.eg/airfryer",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal_increase)
        self.assertFalse(is_alert, "Price increase must not trigger deal alert")
        self.assertIn("SUPPRESSED", reason)

    def test_significant_price_drop_ge_5pct_triggers_alert(self):
        """Case 6: Price drops by >= 5% after cooldown window -> ALERT."""
        deal = Deal(
            id="btech_kettle",
            title="Tornado Electric Kettle",
            store=StoreEnum.BTECH,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1000.0,
            discount_price=800.0,
            discount_percentage=20.0,
            url="https://btech.com/kettle.html",
        )
        self.db.process_and_deduplicate(deal)

        # Simulate time passage > 60 minutes ago
        past_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=70)).isoformat()
        if hasattr(self.db, "_get_connection"):
            conn = self.db._get_connection()
            with conn:
                conn.execute("UPDATE deals SET last_notified_at = ? WHERE id = ?", (past_time, deal.id))
            conn.close()

        # Price drops from 800 to 740 (7.5% drop >= 5%)
        deal_drop = Deal(
            id="btech_kettle",
            title="Tornado Electric Kettle",
            store=StoreEnum.BTECH,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1000.0,
            discount_price=740.0,
            discount_percentage=26.0,
            url="https://btech.com/kettle.html",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal_drop)
        self.assertTrue(is_alert, "Price drop >= 5% after cooldown must trigger alert")
        self.assertEqual(reason, "PRICE_DROP_5PCT")

    def test_cooldown_guard_suppresses_drop_under_10pct_within_60_mins(self):
        """Case 7: Cooldown guard suppresses a 6% drop that occurred only 10 minutes after initial alert."""
        deal = Deal(
            id="carrefour_diaper",
            title="Pampers Maxi Size 4",
            store=StoreEnum.CARREFOUR_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=500.0,
            discount_price=400.0,
            discount_percentage=20.0,
            url="https://www.carrefouregypt.com/p/101",
        )
        self.db.process_and_deduplicate(deal)

        # 10 minutes later (recent), price drops by 6% to 376.0 (between 5% and 10%)
        recent_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=10)).isoformat()
        if hasattr(self.db, "_get_connection"):
            conn = self.db._get_connection()
            with conn:
                conn.execute("UPDATE deals SET last_notified_at = ? WHERE id = ?", (recent_time, deal.id))
            conn.close()

        deal_drop_6pct = Deal(
            id="carrefour_diaper",
            title="Pampers Maxi Size 4",
            store=StoreEnum.CARREFOUR_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=500.0,
            discount_price=376.0,
            discount_percentage=24.8,
            url="https://www.carrefouregypt.com/p/101",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal_drop_6pct)
        self.assertFalse(is_alert, "Drop < 10% within 60 min cooldown must be suppressed")
        self.assertIn("COOLDOWN", reason)

    def test_cooldown_bypass_on_massive_price_drop_ge_10pct(self):
        """Case 8: A massive price drop >= 10% bypasses the 60-minute cooldown and immediately alerts."""
        deal = Deal(
            id="twob_victus",
            title="HP Victus Gaming Laptop",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=40000.0,
            discount_price=35000.0,
            discount_percentage=12.5,
            url="https://2b.com.eg/victus",
        )
        self.db.process_and_deduplicate(deal)

        # Recent notification 5 minutes ago
        recent_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
        if hasattr(self.db, "_get_connection"):
            conn = self.db._get_connection()
            with conn:
                conn.execute("UPDATE deals SET last_notified_at = ? WHERE id = ?", (recent_time, deal.id))
            conn.close()

        # Massive 15% drop from 35000 to 29750
        deal_massive_drop = Deal(
            id="twob_victus",
            title="HP Victus Gaming Laptop",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=40000.0,
            discount_price=29750.0,
            discount_percentage=25.6,
            url="https://2b.com.eg/victus",
        )
        is_alert, reason = self.db.process_and_deduplicate(deal_massive_drop)
        self.assertTrue(is_alert, "Massive drop >= 10% must bypass cooldown and trigger alert")
        self.assertEqual(reason, "PRICE_DROP_5PCT")

    def test_price_history_and_subscribers_persistence(self):
        """Verifies price history logging and subscriber add/query functions."""
        deal = Deal(
            id="sub_test_deal",
            title="Baby Diapers",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=300.0,
            discount_price=250.0,
            discount_percentage=16.6,
            url="https://breadfast.com/diapers",
        )
        self.db.process_and_deduplicate(deal)

        # Verify price history has 1 record
        if hasattr(self.db, "get_price_history"):
            history = self.db.get_price_history("sub_test_deal")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["price"], 250.0)

        # Test subscriber management
        self.db.add_subscriber("12345678", topic="ALL")
        self.db.add_subscriber("87654321", topic="LAPTOPS")

        subs_all = self.db.get_subscribers()
        self.assertIn("12345678", subs_all)
        self.assertIn("87654321", subs_all)

        subs_laptop = self.db.get_subscribers(topic="LAPTOPS")
        self.assertIn("87654321", subs_laptop)


if __name__ == "__main__":
    unittest.main()
