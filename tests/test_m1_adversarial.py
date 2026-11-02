"""
Milestone 1 (M1) Empirical Adversarial Stress-Test Suite.
Authored by Teamwork Challenger to empirically verify:
1. Concurrency & SQLite locking under multi-threaded and async load (WAL mode validation).
2. Database schema integrity & legacy migration on actual legacy deals.db.
3. Subscriber management (deduplication, topic filtering, removal, scale).
4. Serialization integrity (Deal.to_dict / from_dict roundtrips with missing/corrupt fields).
5. Stateful deduplication state machine edge cases & laptop alert loop prevention.
6. Classifier adversarial inputs and boundary conditions.
"""

import asyncio
import concurrent.futures
import datetime
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from typing import List, Tuple, Dict, Any

from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url, compute_deal_hash
from core.classifier import classify_deal
from database.db_service import DatabaseService


class TestM1ConcurrencyAndLocking(unittest.TestCase):
    """Stress tests concurrency and locking behavior under multi-threaded & async load."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_concurrency.db")
        self.db = DatabaseService(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_wal_mode_active(self):
        """Verify WAL mode is enabled and active on SQLite connections."""
        conn = self.db._get_connection()
        try:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertEqual(mode.lower(), "wal", f"Expected WAL mode, got {mode}")
        finally:
            conn.close()

    def test_concurrent_distinct_deal_inserts(self):
        """
        Spawn 30 threads simultaneously calling process_and_deduplicate with distinct deals.
        Checks if SQLite WAL mode handles concurrent write transactions without locking exceptions.
        """
        num_threads = 30
        deals = [
            Deal(
                id=f"deal_thread_{i}",
                title=f"Concurrent Test Deal {i}",
                store=StoreEnum.AMAZON_EG,
                category=CategoryEnum.HOUSEHOLD_GENERAL,
                original_price=100.0 + i,
                discount_price=80.0 + i,
                discount_percentage=20.0,
                url=f"https://www.amazon.eg/dp/B0000000{i:02d}",
            )
            for i in range(num_threads)
        ]

        results: List[Tuple[bool, str]] = []
        errors: List[Exception] = []

        def worker(deal: Deal):
            try:
                res = self.db.process_and_deduplicate(deal)
                results.append(res)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, deal) for deal in deals]
            concurrent.futures.wait(futures)

        self.assertEqual(len(errors), 0, f"Encountered concurrency errors: {errors}")
        self.assertEqual(len(results), num_threads)
        for is_alert, reason in results:
            self.assertTrue(is_alert)
            self.assertEqual(reason, "NEW_DEAL")

        all_deals = self.db.get_all_deals()
        self.assertEqual(len(all_deals), num_threads)

    def test_concurrent_same_deal_race_condition(self):
        """
        Spawn 25 threads simultaneously attempting process_and_deduplicate on the EXACT SAME brand new deal.
        Tests race condition between SELECT and INSERT in process_and_deduplicate (TOCTOU).
        """
        num_threads = 25
        race_deal = Deal(
            id="race_deal_999",
            title="ASUS ROG Strix Scar 18 Race Deal",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=120000.0,
            discount_price=110000.0,
            discount_percentage=8.3,
            url="https://2b.com.eg/p/race-deal-999",
        )

        results: List[Tuple[bool, str]] = []
        errors: List[Exception] = []

        def worker():
            try:
                res = self.db.process_and_deduplicate(race_deal)
                results.append(res)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_threads)]
            concurrent.futures.wait(futures)

        # Verify that at least 1 thread succeeded and the deal exists in DB
        db_deal = self.db.get_deal_by_id("race_deal_999")
        self.assertIsNotNone(db_deal)

        # Document finding for report: TOCTOU race condition exists if errors occur
        integrity_errors = [e for e in errors if isinstance(e, sqlite3.IntegrityError)]
        print(f"\n[EMPIRICAL OBSERVATION] Concurrent same-deal race condition produced {len(integrity_errors)} IntegrityError exceptions out of {num_threads} concurrent threads.")
        self.assertGreater(len(results), 0, "At least one thread must succeed in persisting the deal")

    def test_concurrent_mixed_readers_and_writers(self):
        """
        Spawn 20 writer threads and 20 reader threads executing concurrently for 1.5 seconds.
        Ensures WAL mode allows readers to read while writers write without 'database is locked'.
        """
        stop_time = time.time() + 1.5
        errors: List[Exception] = []
        reads_count = [0]
        writes_count = [0]

        def writer(worker_id: int):
            seq = 0
            while time.time() < stop_time:
                deal = Deal(
                    id=f"mixed_writer_{worker_id}_{seq}",
                    title=f"Writer {worker_id} Deal {seq}",
                    store=StoreEnum.NOON_EG,
                    category=CategoryEnum.BABY_CLOTHES,
                    original_price=500.0,
                    discount_price=450.0,
                    discount_percentage=10.0,
                    url=f"https://www.noon.com/egypt-en/p-{worker_id}-{seq}",
                )
                try:
                    self.db.process_and_deduplicate(deal)
                    writes_count[0] += 1
                except Exception as e:
                    errors.append(e)
                    break
                seq += 1
                time.sleep(0.005)

        def reader(worker_id: int):
            while time.time() < stop_time:
                try:
                    deals = self.db.get_all_deals()
                    laptops = self.db.get_active_laptops()
                    reads_count[0] += 1
                except Exception as e:
                    errors.append(e)
                    break
                time.sleep(0.005)

        with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
            futures = [executor.submit(writer, i) for i in range(20)] + \
                      [executor.submit(reader, i) for i in range(20)]
            concurrent.futures.wait(futures)

        self.assertEqual(len(errors), 0, f"Mixed readers/writers failed with errors: {errors}")
        self.assertGreater(writes_count[0], 20, "Expected multiple successful writes")
        self.assertGreater(reads_count[0], 20, "Expected multiple successful reads")

    def test_asyncio_task_concurrency(self):
        """Verify concurrent calls within asyncio event loop using asyncio.to_thread."""
        async def run_async_test():
            deals = [
                Deal(
                    id=f"async_deal_{i}",
                    title=f"Async Deal {i}",
                    store=StoreEnum.CARREFOUR_EG,
                    category=CategoryEnum.HOUSEHOLD_GENERAL,
                    original_price=200.0,
                    discount_price=160.0,
                    discount_percentage=20.0,
                    url=f"https://www.carrefouregypt.com/p/{i}",
                )
                for i in range(20)
            ]

            tasks = [asyncio.to_thread(self.db.process_and_deduplicate, d) for d in deals]
            res = await asyncio.gather(*tasks, return_exceptions=True)
            return res

        results = asyncio.run(run_async_test())
        exceptions = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(len(exceptions), 0, f"Async tasks encountered exceptions: {exceptions}")
        self.assertEqual(len(results), 20)


class TestM1SchemaIntegrityAndMigration(unittest.TestCase):
    """Stress tests database migrations on real legacy deals.db copies and legacy schemas."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workspace_deals_db = "C:/Users/GO/.gemini/antigravity/scratch/egypt-black-friday-bot/deals.db"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_migration_from_unmigrated_legacy_database(self):
        """
        Creates an exact replica of the unmigrated prototype deals.db (14 columns, no deal_hash,
        no last_notified_price, no last_notified_at, no subscribers table) with 18 realistic rows.
        Verifies that DatabaseService.init_db() correctly:
        - Adds all 3 new columns
        - Creates subscribers table
        - Preserves all 18 existing rows
        - Allows reading and stateful deduplication without errors
        """
        unmigrated_db = os.path.join(self.temp_dir, "legacy_unmigrated.db")
        conn = sqlite3.connect(unmigrated_db)
        with conn:
            conn.execute("""
                CREATE TABLE deals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    store TEXT NOT NULL,
                    category TEXT NOT NULL,
                    original_price REAL NOT NULL,
                    discount_price REAL NOT NULL,
                    discount_percentage REAL NOT NULL,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    is_flash_sale INTEGER DEFAULT 0,
                    is_special_laptop INTEGER DEFAULT 0,
                    coupon_code TEXT,
                    installment_info TEXT,
                    last_updated TIMESTAMP NOT NULL
                );
            """)
            conn.execute("""
                CREATE TABLE price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deal_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    recorded_at TIMESTAMP NOT NULL,
                    FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE
                );
            """)

            # Insert 18 synthetic legacy rows
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            for i in range(18):
                is_lap = 1 if i == 0 else 0
                cat = "لابتوبات وأجهزة" if is_lap else "مستلزمات منزلية"
                conn.execute("""
                    INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"legacy_deal_{i}", f"Legacy Deal {i}", "Amazon Egypt", cat,
                    1000.0, 800.0, 20.0, f"https://www.amazon.eg/dp/B0000{i:05d}",
                    "", 0, is_lap, "", "", now_iso
                ))
        conn.close()

        # Pre-migration verification
        conn_pre = sqlite3.connect(unmigrated_db)
        pre_cols = [r[1] for r in conn_pre.execute("PRAGMA table_info(deals);").fetchall()]
        pre_count = conn_pre.execute("SELECT COUNT(*) FROM deals;").fetchone()[0]
        pre_tables = [r[0] for r in conn_pre.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        conn_pre.close()

        self.assertNotIn("deal_hash", pre_cols)
        self.assertNotIn("last_notified_price", pre_cols)
        self.assertNotIn("last_notified_at", pre_cols)
        self.assertNotIn("subscribers", pre_tables)
        self.assertEqual(pre_count, 18)

        # Trigger migration via DatabaseService
        db = DatabaseService(unmigrated_db)

        # Post-migration verification
        conn_post = sqlite3.connect(unmigrated_db)
        post_cols = [r[1] for r in conn_post.execute("PRAGMA table_info(deals);").fetchall()]
        post_count = conn_post.execute("SELECT COUNT(*) FROM deals;").fetchone()[0]
        post_tables = [r[0] for r in conn_post.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        conn_post.close()

        self.assertIn("deal_hash", post_cols)
        self.assertIn("last_notified_price", post_cols)
        self.assertIn("last_notified_at", post_cols)
        self.assertIn("subscribers", post_tables)
        self.assertEqual(post_count, 18, "Legacy row count was altered by migration!")

        # Verify all 18 deals load properly
        all_deals = db.get_all_deals()
        self.assertEqual(len(all_deals), 18)

        # Verify unchanged deduplication on legacy deal
        first_deal = all_deals[0]
        is_alert, reason = db.process_and_deduplicate(first_deal)
        self.assertFalse(is_alert, "Unchanged legacy deal should NOT trigger alert!")
        self.assertEqual(reason, "UNCHANGED_SUPPRESSED")

        # Verify price drop on legacy deal
        dropped_deal = Deal(
            id=first_deal.id,
            title=first_deal.title,
            store=first_deal.store,
            category=first_deal.category,
            original_price=first_deal.original_price,
            discount_price=round(first_deal.discount_price * 0.85, 2),
            discount_percentage=first_deal.discount_percentage,
            url=first_deal.url,
        )
        is_alert_drop, reason_drop = db.process_and_deduplicate(dropped_deal)
        self.assertTrue(is_alert_drop, "15% price drop on legacy deal should trigger alert!")
        self.assertEqual(reason_drop, "PRICE_DROP_5PCT")

    def test_workspace_deals_db_health(self):
        """Verifies the live project database (deals.db) has all migrated columns and 18 deals."""
        db = DatabaseService(self.workspace_deals_db)
        deals = db.get_all_deals()
        self.assertEqual(len(deals), 18)
        conn = sqlite3.connect(self.workspace_deals_db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(deals);").fetchall()]
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        conn.close()
        self.assertIn("deal_hash", cols)
        self.assertIn("last_notified_price", cols)
        self.assertIn("last_notified_at", cols)
        self.assertIn("subscribers", tables)

    def test_schema_migration_idempotence(self):
        """Calling init_db multiple times on an already migrated database must be safe and idempotent."""
        temp_db = os.path.join(self.temp_dir, "idempotent.db")
        db = DatabaseService(temp_db)

        for _ in range(5):
            db.init_db()

        conn = sqlite3.connect(temp_db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(deals);").fetchall()]
        conn.close()

        self.assertEqual(cols.count("deal_hash"), 1)
        self.assertEqual(cols.count("last_notified_price"), 1)
        self.assertEqual(cols.count("last_notified_at"), 1)

    def test_partial_legacy_schema_migration(self):
        """
        Test migration on a legacy database schema having legacy columns
        (including is_special_laptop) where only 1 or 2 of the 3 new columns exist.
        """
        temp_db = os.path.join(self.temp_dir, "partial.db")
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            CREATE TABLE deals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                store TEXT NOT NULL,
                category TEXT NOT NULL,
                original_price REAL NOT NULL,
                discount_price REAL NOT NULL,
                discount_percentage REAL NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                is_flash_sale INTEGER DEFAULT 0,
                is_special_laptop INTEGER DEFAULT 0,
                coupon_code TEXT,
                installment_info TEXT,
                deal_hash TEXT,
                last_updated TIMESTAMP NOT NULL
            );
        """)
        conn.commit()
        conn.close()

        db = DatabaseService(temp_db)

        conn = sqlite3.connect(temp_db)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(deals);").fetchall()]
        conn.close()

        self.assertIn("deal_hash", cols)
        self.assertIn("last_notified_price", cols)
        self.assertIn("last_notified_at", cols)


class TestM1SubscriberManagement(unittest.TestCase):
    """Stress tests subscriber persistence, duplicate handling, topic filtering, and scale."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "subscribers_test.db")
        self.db = DatabaseService(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_duplicate_subscriber_prevention(self):
        """
        Adding the same chat_id multiple times must NOT duplicate rows.
        It must update the existing record (upsert).
        """
        chat_id = "123456789"
        self.assertTrue(self.db.add_subscriber(chat_id, "LAPTOPS"))
        self.assertTrue(self.db.add_subscriber(chat_id, "LAPTOPS"))
        self.assertTrue(self.db.add_subscriber(chat_id, "HOUSEHOLD_GENERAL"))

        subs = self.db.get_subscribers()
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0], chat_id)

        laptop_subs = self.db.get_subscribers("LAPTOPS")
        self.assertNotIn(chat_id, laptop_subs)
        hh_subs = self.db.get_subscribers("HOUSEHOLD_GENERAL")
        self.assertIn(chat_id, hh_subs)

    def test_topic_filtering_logic(self):
        """
        Subscribers subscribed to 'ALL' or None should receive notifications for specific topics.
        Topic-specific subscribers should only receive their topic.
        """
        self.db.add_subscriber("sub_all", "ALL")
        self.db.add_subscriber("sub_none", None)
        self.db.add_subscriber("sub_laptop", "LAPTOPS")
        self.db.add_subscriber("sub_diaper", "BABY_DIAPERS")

        laptop_subs = self.db.get_subscribers("LAPTOPS")
        self.assertIn("sub_all", laptop_subs)
        self.assertIn("sub_none", laptop_subs)
        self.assertIn("sub_laptop", laptop_subs)
        self.assertNotIn("sub_diaper", laptop_subs)

        diaper_subs = self.db.get_subscribers("BABY_DIAPERS")
        self.assertIn("sub_all", diaper_subs)
        self.assertIn("sub_none", diaper_subs)
        self.assertIn("sub_diaper", diaper_subs)
        self.assertNotIn("sub_laptop", diaper_subs)

        all_subs = self.db.get_subscribers("ALL")
        self.assertEqual(len(all_subs), 4)

        none_subs = self.db.get_subscribers(None)
        self.assertEqual(len(none_subs), 4)

    def test_subscriber_removal(self):
        """Test removing subscribers."""
        self.db.add_subscriber("rem_1", "ALL")
        self.db.add_subscriber("rem_2", "LAPTOPS")

        self.assertTrue(self.db.remove_subscriber("rem_1"))
        self.assertFalse(self.db.remove_subscriber("rem_1"))
        self.assertFalse(self.db.remove_subscriber("non_existent_99"))

        subs = self.db.get_subscribers()
        self.assertEqual(subs, ["rem_2"])

    def test_subscriber_chat_id_formatting(self):
        """Telegram chat IDs can be integer numbers or negative for channels/supergroups."""
        self.db.add_subscriber(123456789, "ALL")
        self.db.add_subscriber(-100192837465, "LAPTOPS")

        subs = self.db.get_subscribers()
        self.assertIn("123456789", subs)
        self.assertIn("-100192837465", subs)

    def test_subscriber_scale_efficiency(self):
        """Benchmark inserting 2,000 subscribers and querying them."""
        start_insert = time.time()
        conn = self.db._get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with conn:
                for i in range(2000):
                    topic = "LAPTOPS" if i % 2 == 0 else "BABY_DIAPERS"
                    conn.execute(
                        "INSERT INTO subscribers (chat_id, topic, subscribed_at) VALUES (?, ?, ?)",
                        (f"chat_{i}", topic, now_iso)
                    )
        finally:
            conn.close()
        insert_duration = time.time() - start_insert

        start_query = time.time()
        laptop_subs = self.db.get_subscribers("LAPTOPS")
        query_duration = time.time() - start_query

        self.assertEqual(len(laptop_subs), 1000)
        self.assertLess(query_duration, 0.1, f"Subscriber query took too long: {query_duration:.4f}s")


class TestM1SerializationIntegrity(unittest.TestCase):
    """Stress tests Deal.to_dict() and Deal.from_dict() serialization roundtrips."""

    def test_roundtrip_full_deal(self):
        """Roundtrip serialization with all fields explicitly populated."""
        original = Deal(
            id="full_deal_1",
            title="حفاضات فاين بيبي مقاس 5 بانتس عبوة كبيرة",
            store=StoreEnum.CARREFOUR_EG,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=450.0,
            discount_price=360.0,
            discount_percentage=20.0,
            url="https://www.carrefouregypt.com/p/diapers-finebaby-5?utm_source=fb",
            image_url="https://images.carrefour.eg/p/1.jpg",
            is_flash_sale=True,
            is_special_laptop=False,
            coupon_code="SAVE20",
            installment_info="0% interest for 6 months via ValU",
            deal_hash="abcdef1234567890",
        )

        serialized = original.to_dict()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["store"], "Carrefour Egypt")
        self.assertEqual(serialized["category"], "حفاضات أطفال")
        self.assertEqual(serialized["is_flash_sale"], 1)
        self.assertEqual(serialized["coupon_code"], "SAVE20")

        deserialized = Deal.from_dict(serialized)
        self.assertEqual(deserialized.id, original.id)
        self.assertEqual(deserialized.title, original.title)
        self.assertEqual(deserialized.store, original.store)
        self.assertEqual(deserialized.category, original.category)
        self.assertEqual(deserialized.original_price, original.original_price)
        self.assertEqual(deserialized.discount_price, original.discount_price)
        self.assertEqual(deserialized.discount_percentage, original.discount_percentage)
        self.assertEqual(deserialized.image_url, original.image_url)
        self.assertEqual(deserialized.is_flash_sale, original.is_flash_sale)
        self.assertEqual(deserialized.coupon_code, original.coupon_code)
        self.assertEqual(deserialized.installment_info, original.installment_info)

    def test_roundtrip_minimal_optional_fields_none(self):
        """Roundtrip serialization when optional fields are None."""
        deal = Deal(
            id="min_deal_1",
            title="Simple Deal",
            store=StoreEnum.AMAZON_EG,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=100.0,
            discount_price=80.0,
            discount_percentage=20.0,
            url="https://www.amazon.eg/dp/B000123456",
            image_url=None,
            is_flash_sale=False,
            is_special_laptop=False,
            coupon_code=None,
            installment_info=None,
            deal_hash=None,
        )

        d = deal.to_dict()
        self.assertEqual(d["image_url"], "")
        self.assertEqual(d["coupon_code"], "")
        self.assertEqual(d["installment_info"], "")
        self.assertIsNotNone(d["deal_hash"])

        restored = Deal.from_dict(d)
        self.assertIsNone(restored.image_url)
        self.assertIsNone(restored.coupon_code)
        self.assertIsNone(restored.installment_info)
        self.assertEqual(restored.deal_hash, d["deal_hash"])

    def test_from_dict_with_dirty_and_missing_inputs(self):
        """Verify Deal.from_dict handles missing keys, string numbers cleanly."""
        raw_data = {
            "id": 12345,
            "title": "  Untrimmed Title   With   Extra   Spaces  ",
            "store": "أمازون",
            "category": "diapers",
            "original_price": "250.75",
            "discount_price": 200,
            "url": "https://www.amazon.eg/dp/B08N5WRWNW?ref_=ast_sto_dp&tag=affiliate-21",
            "is_flash_sale": "true",
            "is_special_laptop": 0,
        }

        deal = Deal.from_dict(raw_data)
        self.assertEqual(deal.id, "12345")
        self.assertEqual(deal.title, "Untrimmed Title With Extra Spaces")
        self.assertEqual(deal.store, StoreEnum.AMAZON_EG)
        self.assertEqual(deal.category, CategoryEnum.BABY_DIAPERS)
        self.assertEqual(deal.original_price, 250.75)
        self.assertEqual(deal.discount_price, 200.0)
        self.assertEqual(deal.url, "https://www.amazon.eg/dp/B08N5WRWNW")
        self.assertTrue(deal.is_flash_sale)
        self.assertFalse(deal.is_special_laptop)

    def test_from_dict_none_price_empirical_vulnerability(self):
        """
        Empirically verifies that Deal.from_dict safely defaults to 0.0 without TypeError
        when original_price or discount_price is explicitly None (e.g. from JSON null).
        """
        deal = Deal.from_dict({"original_price": None, "discount_price": None})
        self.assertEqual(deal.original_price, 0.0)
        self.assertEqual(deal.discount_price, 0.0)
        self.assertEqual(deal.discount_percentage, 0.0)


class TestM1DeduplicationAndStatefulBugFixes(unittest.TestCase):
    """Stress tests stateful deduplication, cooldowns, and laptop loop bug verification."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "dedup_test.db")
        self.db = DatabaseService(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_laptop_spam_loop_prevention_100_cycles(self):
        """
        The critical bug in prototype database.py:73:
        'if deal["discount_price"] < prev_price * 0.95 or deal.get("is_special_laptop", 0): is_alert_worthy = True'
        caused special laptops to trigger alerts on EVERY poll cycle.
        Verify that 100 consecutive scans of an unchanged laptop produce exactly 1 alert.
        """
        laptop = Deal(
            id="laptop_strix_18",
            title="ASUS ROG Strix SCAR 18 Core i9 RTX 4090",
            store=StoreEnum.TWO_B,
            category=CategoryEnum.LAPTOPS,
            original_price=160000.0,
            discount_price=150000.0,
            discount_percentage=6.25,
            url="https://2b.com.eg/p/rog-strix-scar-18",
        )

        self.assertTrue(laptop.is_special_laptop)

        # Cycle 1: First scan -> NEW_DEAL (Alert worthy)
        a1, r1 = self.db.process_and_deduplicate(laptop)
        self.assertTrue(a1)
        self.assertEqual(r1, "NEW_DEAL")

        # Cycles 2 to 100: Subsequent unchanged scans -> Must be suppressed
        for cycle in range(2, 101):
            is_alert, reason = self.db.process_and_deduplicate(laptop)
            self.assertFalse(is_alert, f"Cycle {cycle} triggered alert for unchanged laptop!")
            self.assertEqual(reason, "UNCHANGED_SUPPRESSED")

        history = self.db.get_price_history("laptop_strix_18")
        self.assertEqual(len(history), 1)

    def test_cooldown_and_steep_price_drop_bypass(self):
        """
        Tests cooldown rules:
        - 1st scan: NEW_DEAL (Alert) at 1,000 EGP.
        - 2nd scan within 60 min: price drops to 940 EGP (6% drop, < 10%). Suppressed by cooldown.
        - 3rd scan within 60 min: price drops to 890 EGP (11% drop relative to 1,000). Bypasses cooldown (Alert).
        """
        deal = Deal(
            id="cooldown_item",
            title="Household Vacuum Cleaner",
            store=StoreEnum.BTECH,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1200.0,
            discount_price=1000.0,
            discount_percentage=16.7,
            url="https://btech.com/p/vacuum-cleaner",
        )

        a1, r1 = self.db.process_and_deduplicate(deal)
        self.assertTrue(a1)
        self.assertEqual(r1, "NEW_DEAL")

        # 6% drop (1000 -> 940) within cooldown (< 3600s)
        deal_drop_6 = Deal(
            id="cooldown_item",
            title="Household Vacuum Cleaner",
            store=StoreEnum.BTECH,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1200.0,
            discount_price=940.0,
            discount_percentage=21.7,
            url="https://btech.com/p/vacuum-cleaner",
        )
        a2, r2 = self.db.process_and_deduplicate(deal_drop_6)
        self.assertFalse(a2, "6% drop within cooldown should be suppressed")
        self.assertEqual(r2, "COOLDOWN_SUPPRESSED")

        # 11% drop (1000 -> 890) within cooldown: drop >= 10% should bypass cooldown
        deal_drop_11 = Deal(
            id="cooldown_item",
            title="Household Vacuum Cleaner",
            store=StoreEnum.BTECH,
            category=CategoryEnum.HOUSEHOLD_GENERAL,
            original_price=1200.0,
            discount_price=890.0,
            discount_percentage=25.8,
            url="https://btech.com/p/vacuum-cleaner",
        )
        a3, r3 = self.db.process_and_deduplicate(deal_drop_11)
        self.assertTrue(a3, ">= 10% drop within cooldown should trigger alert")
        self.assertEqual(r3, "PRICE_DROP_5PCT")

    def test_price_increase_behavior(self):
        """Price increase should be suppressed but logged in price_history."""
        deal = Deal(
            id="p_inc_1",
            title="Pampers Box",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=500.0,
            discount_price=400.0,
            discount_percentage=20.0,
            url="https://www.breadfast.com/p/pampers",
        )
        self.db.process_and_deduplicate(deal)

        deal_inc = Deal(
            id="p_inc_1",
            title="Pampers Box",
            store=StoreEnum.BREADFAST,
            category=CategoryEnum.BABY_DIAPERS,
            original_price=500.0,
            discount_price=450.0,
            discount_percentage=10.0,
            url="https://www.breadfast.com/p/pampers",
        )
        a2, r2 = self.db.process_and_deduplicate(deal_inc)
        self.assertFalse(a2)
        self.assertEqual(r2, "PRICE_INCREASE_SUPPRESSED")

        history = self.db.get_price_history("p_inc_1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["price"], 400.0)
        self.assertEqual(history[1]["price"], 450.0)


class TestM1ClassifierAdversarialInputs(unittest.TestCase):
    """Stress tests classifier against tricky titles, accessories, adult diapers, and edge cases."""

    def test_laptop_accessory_exclusion(self):
        """Accessories mentioning laptop terms must NOT be classified as LAPTOPS."""
        tricky_cases = [
            ("شنطة ظهر للابتوب مقاس 15.6 بوصة ضد الماء", CategoryEnum.CLOTHING_ADULT_KIDS),
            ("حقيبة لابتوب جلدية فاخرة مع حزام كتف", CategoryEnum.CLOTHING_ADULT_KIDS),
            ("جراب حماية لجهاز ماك بوك اير 13", CategoryEnum.HOUSEHOLD_GENERAL),
            ("حامل لابتوب المنيوم قابل للتعديل", CategoryEnum.HOUSEHOLD_GENERAL),
            ("قاعدة تبريد لابتوب مع 4 مراوح إضاءة RGB", CategoryEnum.HOUSEHOLD_GENERAL),
            ("Laptop sleeve case 15.6 inch water resistant", CategoryEnum.HOUSEHOLD_GENERAL),
            ("Foldable ergonomic laptop stand for desk", CategoryEnum.HOUSEHOLD_GENERAL),
        ]
        for title, expected_cat in tricky_cases:
            cat = classify_deal(title, StoreEnum.AMAZON_EG)
            self.assertNotEqual(
                cat, CategoryEnum.LAPTOPS,
                f"Accessory '{title}' was erroneously classified as LAPTOPS!"
            )

    def test_laptop_screen_protector_vulnerability(self):
        """
        Empirically demonstrates that laptop screen protector ('لاصقة حماية شاشة لابتوب')
        is misclassified as LAPTOPS because 'لاصقة' and 'شاشة' are missing from LAPTOP_ACCESSORY_EXCLUSION.
        """
        title = "لاصقة حماية شاشة لابتوب ضد التوهج"
        cat = classify_deal(title, StoreEnum.AMAZON_EG)
        # Demonstrates the empirical vulnerability
        self.assertEqual(cat, CategoryEnum.LAPTOPS)
        safe_title = title.encode("ascii", "backslashreplace").decode("ascii")
        print(f"\n[EMPIRICAL VULNERABILITY CONFIRMED] Screen protector '{safe_title}' erroneously tagged as LAPTOPS.")

    def test_genuine_laptops(self):
        """Ensure genuine laptops are cleanly recognized as LAPTOPS."""
        laptops = [
            "لابتوب ديل فوسترو 3520 انتل كور i5",
            "HP Pavilion 15 Gaming Laptop AMD Ryzen 5",
            "Apple MacBook Air 13-inch M2 chip 8GB RAM 256GB SSD",
            "Lenovo Legion Pro 5 16IRX8 Core i7 RTX 4070",
            "ASUS ROG Strix G16 Gaming Laptop 16 FHD+ 165Hz",
            "نوت بوك أيسر اسباير 3 شاشة 15.6",
        ]
        for title in laptops:
            cat = classify_deal(title, StoreEnum.BTECH)
            self.assertEqual(
                cat, CategoryEnum.LAPTOPS,
                f"Genuine laptop '{title}' was not classified as LAPTOPS!"
            )

    def test_adult_incontinence_exclusion_boundary(self):
        """Adult diapers with prefix 'لكبار' must be excluded from BABY_DIAPERS."""
        title_with_prefix = "حفاضات دراي سينيور لكبار السن مقاس وسط"
        cat = classify_deal(title_with_prefix, StoreEnum.CARREFOUR_EG)
        self.assertNotEqual(cat, CategoryEnum.BABY_DIAPERS)
        self.assertEqual(cat, CategoryEnum.HOUSEHOLD_GENERAL)

    def test_adult_incontinence_without_prefix(self):
        """Adult diapers without preposition 'لـ' match exclusion properly."""
        title = "حفاضات كبار السن تينا مقاس كبير"
        cat = classify_deal(title, StoreEnum.CARREFOUR_EG)
        self.assertNotEqual(cat, CategoryEnum.BABY_DIAPERS)

    def test_baby_diapers_genuine(self):
        """Verify genuine baby diapers are classified as BABY_DIAPERS."""
        diaper_cases = [
            "حفاضات بامبرز بيبي دراي مقاس 3 عبوة التوفير 60 حفاضة",
            "مولفيكس بانتس حفاضات اطفال كلوت مقاس 5",
            "فاين بيبي حفاضات مع لوشن البابونج مقاس 4",
            "Baby Joy diapers size 4 large 54 count",
            "بامبرز عناية مميزة مقاس 1 حديثي الولادة",
        ]
        for title in diaper_cases:
            cat = classify_deal(title, StoreEnum.AMAZON_EG)
            self.assertEqual(
                cat, CategoryEnum.BABY_DIAPERS,
                f"Baby diapers '{title}' failed classification as BABY_DIAPERS!"
            )


if __name__ == "__main__":
    unittest.main()
