"""
Standalone Verification Script for Milestone 2:
Executes ScraperEngine.scrape_all() and verifies that all 9 stores produce
valid Deal instances adhering to all interface contracts and schema requirements.
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import StoreEnum, CategoryEnum, Deal
from scrapers.engine import ScraperEngine


async def main():
    print("=" * 70)
    print("Milestone 2 Verification: Executing ScraperEngine.scrape_all()")
    print("=" * 70)

    engine = ScraperEngine()
    print(f"Registered store scrapers: {len(engine.scrapers)}")
    for s in engine.scrapers:
        print(f" - [{s.store.name}] {s.store.value} (timeout: {s.timeout}s)")

    print("\nStarting concurrent scraping across all 9 stores...")
    deals = await engine.scrape_all()

    print(f"\nScraping complete. Total deduplicated deals returned: {len(deals)}")
    assert len(deals) >= 18, f"Expected at least 18 deals, got {len(deals)}"

    # Check store distribution
    deals_by_store = {}
    for d in deals:
        assert isinstance(d, Deal), f"Object {d} is not an instance of Deal"
        deals_by_store.setdefault(d.store, []).append(d)

    print("\nDeals by retailer:")
    for store_enum in StoreEnum:
        store_deals = deals_by_store.get(store_enum, [])
        print(f"  * {store_enum.value:<20}: {len(store_deals):>3} deals")
        assert len(store_deals) >= 2, f"Store {store_enum} produced fewer than 2 deals ({len(store_deals)})"

    # Category and field validations
    print("\nValidating deal fields and contracts:")
    for d in deals:
        assert d.id, f"Deal missing id: {d}"
        assert d.title and len(d.title) >= 3, f"Deal title too short: {d.title}"
        assert d.discount_price > 0, f"Discount price must be > 0: {d.discount_price}"
        assert d.original_price >= d.discount_price, f"Original price must be >= discount price: {d}"
        assert d.url.startswith("https://"), f"URL must be https: {d.url}"
        assert not d.url.endswith("#"), f"URL cannot end with #: {d.url}"
        assert d.deal_hash and len(d.deal_hash) == 64, f"Invalid SHA-256 deal_hash: {d.deal_hash}"
        assert isinstance(d.category, CategoryEnum), f"Invalid category: {d.category}"

    # Laptop validation
    laptop_deals = [d for d in deals if d.category == CategoryEnum.LAPTOPS]
    print(f"\nDedicated laptop deals found: {len(laptop_deals)}")
    assert len(laptop_deals) >= 3, f"Expected at least 3 laptop deals, found {len(laptop_deals)}"
    for ld in laptop_deals:
        assert ld.is_special_laptop, f"Laptop deal {ld.title} missing is_special_laptop flag"

    print("\n" + "=" * 70)
    print("ALL M2 VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
