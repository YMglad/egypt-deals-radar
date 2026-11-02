"""
SQLite Database Service and Stateful Deduplication Engine for Egyptian Deals & Black Friday Bot.
"""

from __future__ import annotations
import sqlite3
import datetime
from typing import Optional, Any
from pathlib import Path

from core.models import StoreEnum, CategoryEnum, Deal


class DatabaseService:
    """
    Manages SQLite persistence, schema initialization/migration,
    stateful deal deduplication, price history, and subscriber management.
    """

    def __init__(self, db_path: str = "deals.db"):
        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = str(Path(db_path).resolve())
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with WAL mode and row factory."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_db(self) -> None:
        """Creates tables and applies migrations if columns are missing."""
        conn = self._get_connection()
        try:
            with conn:
                # 1. Deals table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS deals (
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
                        last_notified_price REAL,
                        last_notified_at TIMESTAMP,
                        last_updated TIMESTAMP NOT NULL
                    );
                """)

                # 2. Price History table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS price_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        deal_id TEXT NOT NULL,
                        price REAL NOT NULL,
                        recorded_at TIMESTAMP NOT NULL,
                        FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE
                    );
                """)

                # 3. Subscribers table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS subscribers (
                        chat_id TEXT PRIMARY KEY,
                        topic TEXT,
                        subscribed_at TIMESTAMP NOT NULL
                    );
                """)

                # Schema migration: check existing columns in deals
                cursor = conn.execute("PRAGMA table_info(deals);")
                existing_cols = {row["name"] for row in cursor.fetchall()}

                if "deal_hash" not in existing_cols:
                    conn.execute("ALTER TABLE deals ADD COLUMN deal_hash TEXT;")
                if "last_notified_price" not in existing_cols:
                    conn.execute("ALTER TABLE deals ADD COLUMN last_notified_price REAL;")
                if "last_notified_at" not in existing_cols:
                    conn.execute("ALTER TABLE deals ADD COLUMN last_notified_at TIMESTAMP;")

                # Indices for fast queries
                conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_category ON deals(category);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_store ON deals(store);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_laptop ON deals(is_special_laptop);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_price_history_deal ON price_history(deal_id);")
        finally:
            conn.close()

    def process_and_deduplicate(self, deal: Deal) -> tuple[bool, str]:
        """
        Statefully deduplicates incoming deals:
        - New deal -> ALERT ('NEW_DEAL'), sets last_notified_price and last_notified_at.
        - Unchanged deal -> SUPPRESS ('UNCHANGED_SUPPRESSED') (resolves the laptop alert loop bug!).
        - Price drop >= 5% compared to last_notified_price -> ALERT ('PRICE_DROP_5PCT').
        - Price drop >= 10% within 60-min cooldown -> ALERT ('PRICE_DROP_5PCT').
        - Price drop < 5% or price increase -> SUPPRESS ('MINOR_DROP_SUPPRESSED' / 'PRICE_INCREASE_SUPPRESSED').
        - Cooldown guard: <= 60 mins between alerts for same deal unless price drop >= 10%.
        
        Returns:
            (is_alert_worthy: bool, reason: str)
        """
        conn = self._get_connection()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        try:
            with conn:
                row = conn.execute(
                    "SELECT id, discount_price, deal_hash, last_notified_price, last_notified_at FROM deals WHERE id = ?",
                    (deal.id,)
                ).fetchone()

                deal_hash = deal.deal_hash or deal.compute_hash()

                # --- CASE 1: Brand New Deal ---
                if row is None:
                    try:
                        conn.execute("""
                            INSERT INTO deals (
                                id, title, store, category, original_price, discount_price,
                                discount_percentage, url, image_url, is_flash_sale,
                                is_special_laptop, coupon_code, installment_info, deal_hash,
                                last_notified_price, last_notified_at, last_updated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            deal.id, deal.title, deal.store.value, deal.category.value,
                            deal.original_price, deal.discount_price, deal.discount_percentage,
                            deal.url, deal.image_url or "", 1 if deal.is_flash_sale else 0,
                            1 if deal.is_special_laptop else 0, deal.coupon_code or "",
                            deal.installment_info or "", deal_hash, deal.discount_price,
                            now_iso, now_iso
                        ))

                        conn.execute(
                            "INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                            (deal.id, deal.discount_price, now_iso)
                        )
                        return True, "NEW_DEAL"
                    except sqlite3.IntegrityError:
                        # TOCTOU concurrency race: another thread inserted this deal simultaneously.
                        # Re-query existing row and fall through to existing deal logic cleanly.
                        row = conn.execute(
                            "SELECT id, discount_price, deal_hash, last_notified_price, last_notified_at FROM deals WHERE id = ?",
                            (deal.id,)
                        ).fetchone()
                        if row is None:
                            return False, "UNCHANGED_SUPPRESSED"

                # --- Existing Deal ---
                prev_price = float(row["discount_price"])
                last_notified_price = float(row["last_notified_price"]) if row["last_notified_price"] is not None else prev_price
                last_notified_at_str = row["last_notified_at"]

                # Parse last_notified_at timestamp
                elapsed_seconds = float("inf")
                if last_notified_at_str:
                    try:
                        notified_dt = datetime.datetime.fromisoformat(last_notified_at_str)
                        if notified_dt.tzinfo is None:
                            notified_dt = notified_dt.replace(tzinfo=datetime.timezone.utc)
                        elapsed_seconds = (now_dt - notified_dt).total_seconds()
                    except Exception:
                        elapsed_seconds = float("inf")

                is_alert_worthy = False
                reason = "UNCHANGED_SUPPRESSED"
                new_notified_price = last_notified_price
                new_notified_at = last_notified_at_str

                # Sub-case A: Identical or practically unchanged price
                if abs(deal.discount_price - prev_price) < 0.01:
                    is_alert_worthy = False
                    reason = "UNCHANGED_SUPPRESSED"

                # Sub-case B: Price dropped relative to last notified price
                elif deal.discount_price < last_notified_price:
                    drop_ratio = (last_notified_price - deal.discount_price) / last_notified_price

                    if elapsed_seconds < 3600:  # Within 60-minute cooldown
                        if drop_ratio >= 0.10:  # >= 10% drop bypasses cooldown
                            is_alert_worthy = True
                            reason = "PRICE_DROP_5PCT"
                            new_notified_price = deal.discount_price
                            new_notified_at = now_iso
                        else:
                            is_alert_worthy = False
                            reason = "COOLDOWN_SUPPRESSED"
                    else:  # Cooldown expired (>= 60 minutes)
                        if drop_ratio >= 0.05:  # >= 5% drop
                            is_alert_worthy = True
                            reason = "PRICE_DROP_5PCT"
                            new_notified_price = deal.discount_price
                            new_notified_at = now_iso
                        else:
                            is_alert_worthy = False
                            reason = "MINOR_DROP_SUPPRESSED"

                    # Record drop in price history
                    conn.execute(
                        "INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                        (deal.id, deal.discount_price, now_iso)
                    )

                # Sub-case C: Price increased
                else:
                    is_alert_worthy = False
                    reason = "PRICE_INCREASE_SUPPRESSED"
                    # Record increase in price history
                    conn.execute(
                        "INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                        (deal.id, deal.discount_price, now_iso)
                    )

                # Update deal metadata in deals table
                conn.execute("""
                    UPDATE deals SET
                        title = ?, store = ?, category = ?, original_price = ?,
                        discount_price = ?, discount_percentage = ?, url = ?,
                        image_url = ?, is_flash_sale = ?, is_special_laptop = ?,
                        coupon_code = ?, installment_info = ?, deal_hash = ?,
                        last_notified_price = ?, last_notified_at = ?, last_updated = ?
                    WHERE id = ?
                """, (
                    deal.title, deal.store.value, deal.category.value,
                    deal.original_price, deal.discount_price, deal.discount_percentage,
                    deal.url, deal.image_url or "", 1 if deal.is_flash_sale else 0,
                    1 if deal.is_special_laptop else 0, deal.coupon_code or "",
                    deal.installment_info or "", deal_hash, new_notified_price,
                    new_notified_at, now_iso, deal.id
                ))

                return is_alert_worthy, reason
        finally:
            conn.close()

    def save_deal(self, deal: Deal) -> None:
        """Inserts or updates a deal directly."""
        conn = self._get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        deal_hash = deal.deal_hash or deal.compute_hash()

        try:
            with conn:
                conn.execute("""
                    INSERT INTO deals (
                        id, title, store, category, original_price, discount_price,
                        discount_percentage, url, image_url, is_flash_sale,
                        is_special_laptop, coupon_code, installment_info, deal_hash,
                        last_notified_price, last_notified_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        store = excluded.store,
                        category = excluded.category,
                        original_price = excluded.original_price,
                        discount_price = excluded.discount_price,
                        discount_percentage = excluded.discount_percentage,
                        url = excluded.url,
                        image_url = excluded.image_url,
                        is_flash_sale = excluded.is_flash_sale,
                        is_special_laptop = excluded.is_special_laptop,
                        coupon_code = excluded.coupon_code,
                        installment_info = excluded.installment_info,
                        deal_hash = excluded.deal_hash,
                        last_updated = excluded.last_updated;
                """, (
                    deal.id, deal.title, deal.store.value, deal.category.value,
                    deal.original_price, deal.discount_price, deal.discount_percentage,
                    deal.url, deal.image_url or "", 1 if deal.is_flash_sale else 0,
                    1 if deal.is_special_laptop else 0, deal.coupon_code or "",
                    deal.installment_info or "", deal_hash, deal.discount_price,
                    now_iso, now_iso
                ))
        finally:
            conn.close()

    def get_deal_by_id(self, deal_id: str) -> Optional[Deal]:
        """Fetches a single deal by its ID."""
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
            if not row:
                return None
            return self._row_to_deal(row)
        finally:
            conn.close()

    def get_all_deals(
        self,
        category: Optional[str] = None,
        store: Optional[str] = None,
        min_discount: float = 0.0
    ) -> list[Deal]:
        """Queries deals with optional category, store, and discount filters."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM deals WHERE discount_percentage >= ?"
            params: list[Any] = [min_discount]

            if category and category.strip().lower() not in ("all", "*", ""):
                # Resolve category representation
                cat_enum = CategoryEnum.from_str(category)
                query += " AND (category = ? OR category = ?)"
                params.extend([cat_enum.value, cat_enum.name])

            if store and store.strip().lower() not in ("all", "*", ""):
                store_enum = StoreEnum.from_str(store)
                query += " AND (store = ? OR store = ?)"
                params.extend([store_enum.value, store_enum.name])

            query += " ORDER BY is_special_laptop DESC, is_flash_sale DESC, discount_percentage DESC;"
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_deal(r) for r in rows]
        finally:
            conn.close()

    def get_active_laptops(self) -> list[Deal]:
        """Fetches all active laptop deals sorted by lowest price."""
        conn = self._get_connection()
        try:
            laptop_cat_val = CategoryEnum.LAPTOPS.value
            laptop_cat_name = CategoryEnum.LAPTOPS.name
            query = """
                SELECT * FROM deals
                WHERE is_special_laptop = 1
                   OR category = ?
                   OR category = ?
                   OR title LIKE '%ROG Strix%'
                   OR title LIKE '%لابتوب%'
                   OR title LIKE '%laptop%'
                ORDER BY discount_price ASC;
            """
            rows = conn.execute(query, (laptop_cat_val, laptop_cat_name)).fetchall()
            return [self._row_to_deal(r) for r in rows]
        finally:
            conn.close()

    def add_subscriber(self, chat_id: str, topic: Optional[str] = None) -> bool:
        """Adds or updates a subscriber."""
        conn = self._get_connection()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO subscribers (chat_id, topic, subscribed_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        topic = excluded.topic,
                        subscribed_at = excluded.subscribed_at;
                """, (str(chat_id), topic or "ALL", now_iso))
            return True
        finally:
            conn.close()

    def remove_subscriber(self, chat_id: str) -> bool:
        """Removes a subscriber."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("DELETE FROM subscribers WHERE chat_id = ?", (str(chat_id),))
                return cur.rowcount > 0
        finally:
            conn.close()

    def get_subscribers(self, topic: Optional[str] = None) -> list[str]:
        """Returns list of subscribed chat IDs."""
        conn = self._get_connection()
        try:
            if topic and topic.upper() != "ALL":
                rows = conn.execute(
                    "SELECT chat_id FROM subscribers WHERE topic = ? OR topic = 'ALL' OR topic IS NULL",
                    (topic,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT chat_id FROM subscribers").fetchall()
            return [str(row["chat_id"]) for row in rows]
        finally:
            conn.close()

    def get_price_history(self, deal_id: str) -> list[dict[str, Any]]:
        """Returns recorded price history for a deal."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT price, recorded_at FROM price_history WHERE deal_id = ? ORDER BY recorded_at ASC",
                (deal_id,)
            ).fetchall()
            return [{"price": float(r["price"]), "recorded_at": r["recorded_at"]} for r in rows]
        finally:
            conn.close()

    def delete_deal(self, deal_id: str) -> bool:
        """Deletes a deal and its price history."""
        conn = self._get_connection()
        try:
            with conn:
                cur = conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
                return cur.rowcount > 0
        finally:
            conn.close()

    def clear_deals(self) -> None:
        """Clears all deals and price history (for testing purposes)."""
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("DELETE FROM price_history;")
                conn.execute("DELETE FROM deals;")
        finally:
            conn.close()

    @staticmethod
    def _row_to_deal(row: sqlite3.Row) -> Deal:
        """Converts an SQLite row to a Deal object."""
        return Deal(
            id=row["id"],
            title=row["title"],
            store=StoreEnum.from_str(row["store"]),
            category=CategoryEnum.from_str(row["category"]),
            original_price=float(row["original_price"]),
            discount_price=float(row["discount_price"]),
            discount_percentage=float(row["discount_percentage"]),
            url=row["url"],
            image_url=row["image_url"] or None,
            is_flash_sale=bool(row["is_flash_sale"]),
            is_special_laptop=bool(row["is_special_laptop"]),
            coupon_code=row["coupon_code"] or None,
            installment_info=row["installment_info"] or None,
            deal_hash=row["deal_hash"] if "deal_hash" in row.keys() else None,
        )
