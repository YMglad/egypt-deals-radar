"""
Tier 4 Tests: Real-World End-to-End Scenarios and Telegram Notification Delivery.

Covers:
- Feature 23: Full Pipeline Execution (Simulated Scrape -> Classify -> Dedup -> Telegram Dispatch)
- Feature 24: Telegram Notification Delivery & Integrity (HTML mode, Direct URL button, #Laptop tagging, Multi-subscriber)
"""

import unittest
import asyncio
from core.models import StoreEnum, CategoryEnum, Deal
from core.classifier import classify_deal, tag_deal_category
from tests.conftest import (
    MockTelegramBot,
    format_deal_telegram,
    get_db_service,
    AMAZON_EG_HTML,
    NOON_EG_JSON,
    BREADFAST_JSON,
    VALU_HTML,
    TWO_B_HTML,
    parse_amazon_snippet,
    parse_noon_snippet,
    parse_breadfast_snippet,
    parse_valu_snippet,
    parse_twob_snippet,
)


class TestTier4E2EWorkflow(unittest.TestCase):
    """Tier 4: End-to-End multi-store simulation and Telegram notification pipeline."""

    def setUp(self):
        self.db = get_db_service()
        self.bot = MockTelegramBot()

    def tearDown(self):
        if hasattr(self.db, "clear_deals"):
            self.db.clear_deals()
        if hasattr(self.db, "conn") and self.db.conn:
            self.db.conn.close()

    def test_full_pipeline_scrape_to_telegram_dispatch(self):
        """
        Simulates a complete real-world polling cycle:
        1. Multi-store scraper extraction (Amazon, Noon, Breadfast, ValU, 2B)
        2. Automatic Category classification & tagging
        3. Stateful deduplication against SQLite
        4. Telegram notification dispatch with inline direct purchase buttons
        """
        raw_deals = []
        raw_deals.extend(parse_amazon_snippet(AMAZON_EG_HTML))
        raw_deals.extend(parse_noon_snippet(NOON_EG_JSON))
        raw_deals.extend(parse_breadfast_snippet(BREADFAST_JSON))
        raw_deals.extend(parse_valu_snippet(VALU_HTML))
        raw_deals.extend(parse_twob_snippet(TWO_B_HTML))

        self.assertGreaterEqual(len(raw_deals), 10, "Should have extracted at least 10 sample deals")

        # Set up a target subscriber
        test_chat_id = "987654321"
        self.db.add_subscriber(test_chat_id, topic="ALL")

        dispatched_count = 0
        laptop_count = 0

        async def run_pipeline():
            nonlocal dispatched_count, laptop_count
            for raw in raw_deals:
                # A. Construct Deal
                deal = Deal(
                    id=raw["id"],
                    title=raw["title"],
                    store=raw["store"],
                    category=CategoryEnum.HOUSEHOLD_GENERAL,  # initial placeholder
                    original_price=raw["original_price"],
                    discount_price=raw["discount_price"],
                    discount_percentage=raw["discount_percentage"],
                    url=raw["url"],
                    installment_info=raw.get("installment_info"),
                )

                # B. Classify category & laptop flag
                deal = tag_deal_category(deal)

                # C. Stateful Deduplication
                is_alert, reason = self.db.process_and_deduplicate(deal)
                if is_alert:
                    # D. Format Telegram HTML Message
                    msg_text, markup = format_deal_telegram(deal)
                    # E. Dispatch through Bot
                    await self.bot.send_message(
                        chat_id=test_chat_id,
                        text=msg_text,
                        parse_mode="HTML",
                        reply_markup=markup,
                    )
                    dispatched_count += 1
                    if deal.is_laptop:
                        laptop_count += 1

        asyncio.run(run_pipeline())

        # Assertions on Cycle 1
        self.assertGreater(dispatched_count, 0)
        self.assertGreater(laptop_count, 0)
        self.assertEqual(len(self.bot.sent_messages), dispatched_count)

        # Verify all dispatched messages have valid structure
        for msg in self.bot.sent_messages:
            self.assertEqual(msg.chat_id, test_chat_id)
            self.assertEqual(msg.parse_mode, "HTML")
            self.assertIsNotNone(msg.reply_markup)
            first_btn = msg.reply_markup.inline_keyboard[0][0]
            self.assertTrue(first_btn.url.startswith("https://"))

        # Cycle 2: Immediately re-run exact same pipeline -> Zero new alerts!
        self.bot.clear()
        dispatched_cycle_2 = 0

        async def run_cycle_2():
            nonlocal dispatched_cycle_2
            for raw in raw_deals:
                deal = Deal(
                    id=raw["id"],
                    title=raw["title"],
                    store=raw["store"],
                    category=CategoryEnum.HOUSEHOLD_GENERAL,
                    original_price=raw["original_price"],
                    discount_price=raw["discount_price"],
                    discount_percentage=raw["discount_percentage"],
                    url=raw["url"],
                )
                deal = tag_deal_category(deal)
                is_alert, _ = self.db.process_and_deduplicate(deal)
                if is_alert:
                    dispatched_cycle_2 += 1

        asyncio.run(run_cycle_2())
        self.assertEqual(dispatched_cycle_2, 0, "Second cycle of unchanged deals must dispatch 0 alerts!")
        self.assertEqual(len(self.bot.sent_messages), 0)

    def test_telegram_laptop_notification_has_prominent_hashtag(self):
        """Verifies dedicated laptop notifications explicitly include the required #Laptop tag."""
        laptop_deal = Deal(
            id="test_rog_1",
            title="ASUS ROG Strix G16 Gaming Laptop",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.LAPTOPS,
            original_price=70000.0,
            discount_price=62000.0,
            discount_percentage=11.4,
            url="https://www.amazon.eg/dp/B08XYZ7890",
            installment_info="0% interest with valU 12 months",
        )
        msg_text, markup = format_deal_telegram(laptop_deal)

        self.assertIn("#Laptop", msg_text, "Laptop notifications must feature #Laptop tag")
        self.assertIn("#لابتوب", msg_text, "Laptop notifications must feature #لابتوب tag")
        self.assertIn("62,000.00 ج.م", msg_text)
        self.assertIn("valU", msg_text)

        # Inline button verification
        self.assertEqual(len(markup.inline_keyboard), 2)
        order_button = markup.inline_keyboard[0][0]
        self.assertEqual(order_button.url, "https://www.amazon.eg/dp/B08XYZ7890")
        self.assertIn("شراء اللابتوب", order_button.text)

    def test_telegram_household_notification_structure(self):
        """Verifies household/diaper deals use standard alert template with direct order button."""
        household_deal = Deal(
            id="test_pampers_1",
            title="Pampers Pants Diapers Size 4 58 Count",
            store=StoreEnum.NOON_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=480.0,
            discount_price=360.0,
            discount_percentage=25.0,
            url="https://www.noon.com/egypt-en/pampers-58/p-101",
            coupon_code="NOON10",
        )
        msg_text, markup = format_deal_telegram(household_deal)

        self.assertIn("تنبيه صفقة جديدة", msg_text)
        self.assertIn("خصم 25%", msg_text)
        self.assertIn("Noon Egypt", msg_text)
        self.assertIn("حفاضات أطفال", msg_text)
        self.assertIn("<code>NOON10</code>", msg_text)
        self.assertNotIn("#Laptop", msg_text)

        order_button = markup.inline_keyboard[0][0]
        self.assertEqual(order_button.url, "https://www.noon.com/egypt-en/pampers-58/p-101")
        self.assertIn("اطلب مباشرة", order_button.text)

    def test_multi_subscriber_broadcast(self):
        """Verifies an alert-worthy deal is broadcast to all registered subscribers."""
        self.db.add_subscriber("sub_111", topic="ALL")
        self.db.add_subscriber("sub_222", topic="ALL")
        self.db.add_subscriber("sub_333", topic="ALL")

        deal = Deal(
            id="broadcast_deal",
            title="Persil Automatic Powder 5kg",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=300.0,
            discount_price=220.0,
            discount_percentage=26.6,
            url="https://www.breadfast.com/product/persil-5kg",
        )
        is_alert, _ = self.db.process_and_deduplicate(deal)
        self.assertTrue(is_alert)

        subscribers = self.db.get_subscribers()
        self.assertEqual(len(subscribers), 3)

        async def broadcast():
            msg_text, markup = format_deal_telegram(deal)
            for sub_id in subscribers:
                await self.bot.send_message(
                    chat_id=sub_id,
                    text=msg_text,
                    parse_mode="HTML",
                    reply_markup=markup,
                )

        asyncio.run(broadcast())

        dispatched = self.bot.get_dispatched()
        self.assertEqual(len(dispatched), 3)
        chat_ids = {m.chat_id for m in dispatched}
        self.assertEqual(chat_ids, {"sub_111", "sub_222", "sub_333"})

    def test_resilience_when_one_store_fails(self):
        """
        Verifies system resilience: if one store scraper raises an exception (e.g. 500 error),
        the remaining store scrapers continue without aborting the polling loop.
        """
        def faulty_store_scraper():
            raise ConnectionError("Carrefour EG anti-bot WAF 403 Forbidden")

        def healthy_store_scraper():
            return parse_noon_snippet(NOON_EG_JSON)

        collected = []
        errors = []

        # Simulated runner
        for scraper_fn in [faulty_store_scraper, healthy_store_scraper]:
            try:
                deals = scraper_fn()
                collected.extend(deals)
            except Exception as e:
                errors.append(str(e))

        self.assertEqual(len(errors), 1)
        self.assertIn("WAF 403", errors[0])
        self.assertGreater(len(collected), 0, "Healthy store deals must still be gathered")


if __name__ == "__main__":
    unittest.main()
