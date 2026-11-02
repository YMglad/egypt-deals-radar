# Test Infrastructure & Opaque-Box Test Strategy
## Egyptian Deals & Black Friday Telegram Bot (@Deals_egy_bot)

This document establishes the authoritative testing architecture, test philosophy, fixture specifications, and verification contracts for the real-time deals monitoring and Telegram notification system.

---

## 1. Test Philosophy & Design Principles

1. **Opaque-Box & Requirement-Driven:**
   - Tests are derived strictly from authoritative specifications (`ORIGINAL_REQUEST.md`, `PROJECT.md`, and `spec_miner_requirements/handoff.md`).
   - Tests verify system behavior and interface contracts, not internal implementation quirks.
   - Zero facade tests: Every assertion validates real invariants, data transformations, and contract integrity.

2. **Progressive Testability:**
   - Components from Milestone 1 (`core.models`, `core.classifier`, `database.db_service`) are tested against live code when present and backed by rigorous contractual mocks.
   - Future milestone adapters (M2 Scrapers, M3 Telegram Dispatcher, M4 Poller) are verified via self-contained mock fixtures and contract harnesses in `conftest.py` ensuring progressive testability at all stages.

3. **Deterministic & Isolated:**
   - No external network access or live Telegram API calls are required during test execution.
   - In-memory SQLite databases (`:memory:`) or isolated temporary test databases are used for all stateful tests.
   - Tests are independent and order-agnostic.

4. **Adversarial & Edge-Hardened:**
   - Exhaustive boundary checks: negative/zero prices, inverse discounts (>100%), empty payloads, malformed URLs, and tracking query floods.
   - HTML/Markdown special characters (`<>&*[]()_`) tested against escaping routines to guarantee zero Telegram parsing crashes.

---

## 2. Feature Inventory & Test Tier Mapping

| # | Feature Name | Target Scope | Assigned Test Tier | Test Coverage Target |
|---|--------------|--------------|-------------------|----------------------|
| 1 | Canonical Deal Data Model | `core.models.Deal` | Tier 1 (Unit) | >= 5 tests (Schema, types, hash, dict serialization) |
| 2 | Store Enum & Alias Resolution | `core.models.StoreEnum` | Tier 1 (Unit) | >= 5 tests (9 stores, Arabic/English aliases, fallback) |
| 3 | Category Enum & Normalization | `core.models.CategoryEnum` | Tier 1 (Unit) | >= 5 tests (5 categories, Arabic/English resolution) |
| 4 | URL Canonicalization | `core.models.canonicalize_url` | Tier 1 (Unit) | >= 5 tests (UTM stripping, ASIN normalization, trailing slash) |
| 5 | Deal SHA-256 Hashing | `core.models.compute_deal_hash` | Tier 1 (Unit) | >= 5 tests (Determinism, price sensitivity, coupon sensitivity) |
| 6 | Category Classifier - Laptops | `core.classifier` | Tier 1 (Unit) | >= 5 tests (Regex patterns, brand keywords, accessory exclusion) |
| 7 | Category Classifier - Baby Diapers | `core.classifier` | Tier 1 (Unit) | >= 5 tests (Pampers, Molfix, wipes, adult exclusion) |
| 8 | Category Classifier - Baby Clothes | `core.classifier` | Tier 1 (Unit) | >= 5 tests (Salopette, romper, infant wear, Arabic variants) |
| 9 | Category Classifier - Clothing Adult/Kids | `core.classifier` | Tier 1 (Unit) | >= 5 tests (T-shirts, hoodies, jeans, footwear, dresses) |
| 10 | Category Classifier - Household General | `core.classifier` | Tier 1 (Unit) | >= 5 tests (Detergents, cookware, air fryers, vacuum cleaners) |
| 11 | Store Scrapers Parsing (9 Stores) | `tests/conftest.py` & Scrapers | Tier 1 (Feature) | >= 9 tests (One per store fixture: Amazon, Noon, Breadfast, Talabat, ValU, Carrefour, Jumia, B.Tech, 2B) |
| 12 | Direct URL Extraction & Validation | Scraper Parsers | Tier 1 (Feature) | >= 5 tests (Rejects '#', empty, homepage-only links) |
| 13 | Boundary: Price Validation | Schema & Ingestion | Tier 2 (Boundary) | >= 5 tests (Zero price, negative price, price > original) |
| 14 | Boundary: Discount Edge Cases | Discount Calculation | Tier 2 (Boundary) | >= 5 tests (0%, 100%, >100%, negative discount correction) |
| 15 | Boundary: Malformed & Tracking URLs | URL Sanitizer | Tier 2 (Boundary) | >= 5 tests (Missing scheme, IP hostnames, tracking spam query) |
| 16 | Boundary: HTML / XSS Injection | Telegram HTML Formatter | Tier 2 (Boundary) | >= 5 tests (`<script>`, `<b>`, `&`, unclosed tags, quotes) |
| 17 | Boundary: Empty & Extreme Payloads | Scraper Engine | Tier 2 (Boundary) | >= 5 tests (Empty HTML, empty JSON, 50KB titles, missing keys) |
| 18 | Dedup: New Deal Alert | `database.db_service` | Tier 3 (Cross-Feature) | >= 3 tests (First ingestion emits `NEW_DEAL`) |
| 19 | Dedup: Unchanged Deal Suppression | `database.db_service` | Tier 3 (Cross-Feature) | >= 3 tests (Unchanged price emits `UNCHANGED_SUPPRESSED`) |
| 20 | Dedup: Laptop Spam Prevention | `database.db_service` | Tier 3 (Cross-Feature) | >= 3 tests (Unchanged laptop emits `UNCHANGED_SUPPRESSED`, fixing old bug) |
| 21 | Dedup: Price Drop Delta Threshold | `database.db_service` | Tier 3 (Cross-Feature) | >= 4 tests (Drop >= 5% alerts; drop < 5% or increase suppresses) |
| 22 | Dedup: Cooldown Guard | `database.db_service` | Tier 3 (Cross-Feature) | >= 3 tests (Suppresses within 60 min unless >= 10% drop) |
| 23 | E2E: Full Scrape-to-Telegram Flow | Full Pipeline Harness | Tier 4 (E2E) | >= 3 tests (Multi-store simulated poll -> classify -> dedup -> telegram) |
| 24 | E2E: Telegram Notification Integrity | `TelegramNotificationService` | Tier 4 (E2E) | >= 4 tests (HTML parse mode, direct order button, `#Laptop` tag) |

---

## 3. Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                       # Synthetic HTML/JSON fixtures (9 stores), mock Telegram API, DB factories
├── test_tier1_models_classifier.py   # Tier 1: Canonical models, hash, URL normalization, 5 category classifiers
├── test_tier1_scrapers.py            # Tier 1: 9 store parsers, field completeness, direct URL contracts
├── test_tier2_boundary_corner.py     # Tier 2: Boundary prices, invalid discounts, HTML escaping, malformed URLs
├── test_tier3_deduplication.py       # Tier 3: Stateful dedup matrix, laptop spam bug resolution, cooldown
└── test_tier4_e2e_workflow.py        # Tier 4: Multi-store pipeline, Telegram HTML delivery, #Laptop isolation
```

---

## 4. Execution & Verification

### Standard Test Runner
```bash
python run_tests.py
```
Or via explicit python path:
```bash
C:\Users\GO\.gemini\antigravity\scratch\egypt-black-friday-bot\.venv\Scripts\python.exe run_tests.py
```

### Coverage & Exit Code Requirements
- **Pass Threshold:** 100% test pass rate across all tiers.
- **Exit Code:** Return code `0` on complete success, non-zero on failure.
- **Reporting:** Concise tabular test execution summary printing discovered test counts, pass/fail totals, and execution duration.
