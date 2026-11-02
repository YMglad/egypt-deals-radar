"""
Database package for Egyptian Deals & Black Friday Telegram Bot.
Exposes DatabaseService and legacy compatibility functions (init_db, save_or_update_deal, get_all_deals, get_laptop_deals).
"""

from typing import List, Dict, Optional, Any
from core.models import Deal
from database.db_service import DatabaseService

_service: Optional[DatabaseService] = None


def get_service(db_path: str = "deals.db") -> DatabaseService:
    """Returns singleton DatabaseService instance."""
    global _service
    if _service is None or _service.db_path != db_path:
        _service = DatabaseService(db_path)
    return _service


def init_db(db_path: str = "deals.db") -> None:
    """Initializes the database tables and runs migrations."""
    get_service(db_path).init_db()


def save_or_update_deal(deal: Dict[str, Any], db_path: str = "deals.db") -> bool:
    """
    Saves a deal or updates it with stateful deduplication.
    Returns True if this is an alert-worthy event (new deal or significant price drop >= 5%).
    Suppresses alerts for unchanged laptops, fixing the old database.py:73 bug.
    """
    if isinstance(deal, Deal):
        deal_obj = deal
    else:
        deal_obj = Deal.from_dict(deal)

    is_alert_worthy, _ = get_service(db_path).process_and_deduplicate(deal_obj)
    return is_alert_worthy


def get_all_deals(
    category: Optional[str] = None,
    store: Optional[str] = None,
    min_discount: float = 0,
    db_path: str = "deals.db"
) -> List[Dict[str, Any]]:
    """Fetches all deals matching filters, returned as dictionaries."""
    deals = get_service(db_path).get_all_deals(category=category, store=store, min_discount=min_discount)
    return [d.to_dict() for d in deals]


def get_laptop_deals(db_path: str = "deals.db") -> List[Dict[str, Any]]:
    """Fetches active laptop deals, returned as dictionaries."""
    deals = get_service(db_path).get_active_laptops()
    return [d.to_dict() for d in deals]


def add_subscriber(chat_id: str, topic: Optional[str] = "ALL", db_path: str = "deals.db") -> bool:
    """Adds a subscriber chat ID to the database."""
    return get_service(db_path).add_subscriber(chat_id, topic)


def get_subscribers(topic: Optional[str] = None, db_path: str = "deals.db") -> List[str]:
    """Retrieves all registered subscriber chat IDs."""
    return get_service(db_path).get_subscribers(topic)


__all__ = [
    "DatabaseService",
    "get_service",
    "init_db",
    "save_or_update_deal",
    "get_all_deals",
    "get_laptop_deals",
    "add_subscriber",
    "get_subscribers",
]
