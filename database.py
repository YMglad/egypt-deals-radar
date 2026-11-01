import sqlite3
import datetime
from typing import List, Dict, Optional

DB_FILE = "deals.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Table for all tracked deals
    c.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            title TEXT,
            store TEXT,
            category TEXT,
            original_price REAL,
            discount_price REAL,
            discount_percentage REAL,
            url TEXT,
            image_url TEXT,
            is_flash_sale INTEGER DEFAULT 0,
            is_special_laptop INTEGER DEFAULT 0,
            coupon_code TEXT,
            installment_info TEXT,
            last_updated TIMESTAMP
        )
    ''')
    # Table for price history (to detect fake discounts)
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id TEXT,
            price REAL,
            recorded_at TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_or_update_deal(deal: Dict) -> bool:
    """
    Saves a deal or updates it. Returns True if this is a newly discovered deal
    or if there is a significant price drop (triggering an alert).
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().isoformat()
    deal_id = deal["id"]
    
    c.execute("SELECT discount_price, original_price FROM deals WHERE id = ?", (deal_id,))
    row = c.fetchone()
    
    is_alert_worthy = False
    if row is None:
        # New deal!
        is_alert_worthy = True
        c.execute('''
            INSERT INTO deals (id, title, store, category, original_price, discount_price, 
                               discount_percentage, url, image_url, is_flash_sale, 
                               is_special_laptop, coupon_code, installment_info, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            deal["id"], deal["title"], deal["store"], deal.get("category", "Electronics"),
            deal.get("original_price", 0), deal["discount_price"], deal.get("discount_percentage", 0),
            deal["url"], deal.get("image_url", ""), deal.get("is_flash_sale", 0),
            deal.get("is_special_laptop", 0), deal.get("coupon_code", ""), deal.get("installment_info", ""),
            now
        ))
    else:
        prev_price = row[0]
        # If price dropped further by >= 5% or it's a special item
        if deal["discount_price"] < prev_price * 0.95 or deal.get("is_special_laptop", 0):
            is_alert_worthy = True
            
        c.execute('''
            UPDATE deals SET 
                title = ?, store = ?, category = ?, original_price = ?, discount_price = ?,
                discount_percentage = ?, url = ?, image_url = ?, is_flash_sale = ?,
                is_special_laptop = ?, coupon_code = ?, installment_info = ?, last_updated = ?
            WHERE id = ?
        ''', (
            deal["title"], deal["store"], deal.get("category", "Electronics"),
            deal.get("original_price", 0), deal["discount_price"], deal.get("discount_percentage", 0),
            deal["url"], deal.get("image_url", ""), deal.get("is_flash_sale", 0),
            deal.get("is_special_laptop", 0), deal.get("coupon_code", ""), deal.get("installment_info", ""),
            now, deal_id
        ))

    # Log to price history
    c.execute("INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
              (deal_id, deal["discount_price"], now))
    conn.commit()
    conn.close()
    return is_alert_worthy

def get_all_deals(category: Optional[str] = None, store: Optional[str] = None, min_discount: float = 0) -> List[Dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    query = "SELECT * FROM deals WHERE discount_percentage >= ?"
    params = [min_discount]
    if category and category != "All":
        query += " AND category = ?"
        params.append(category)
    if store and store != "All":
        query += " AND store = ?"
        params.append(store)
    query += " ORDER BY is_special_laptop DESC, is_flash_sale DESC, discount_percentage DESC"
    c.execute(query, params)
    rows = c.fetchall()
    deals = [dict(row) for row in rows]
    conn.close()
    return deals

def get_laptop_deals() -> List[Dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE is_special_laptop = 1 OR title LIKE '%ROG Strix%' ORDER BY discount_price ASC")
    rows = c.fetchall()
    deals = [dict(row) for row in rows]
    conn.close()
    return deals
