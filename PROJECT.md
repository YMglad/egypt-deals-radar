# Project: Egyptian Deals & Black Friday Telegram Bot

## Architecture
A real-time, asynchronous deals monitoring and Telegram notification system engineered for high concurrency, 1–2 minute polling cycles, and zero downtime.

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 Continuous Polling Engine              │
                  │              (1-2 min interval, crash-proof)           │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
      ┌───────────────────────────────┐               ┌───────────────────────────────┐
      │     Scraper Engine (Async)    │               │     Database / Deduplication  │
      │  Concurrent fetch 9 retailers │               │      (SQLite + Content Hash)  │
      │  Strict 3-5s timeout per store│               │                               │
      │  - Amazon EG    - Carrefour   │               │  - Canonical deal ID & hash   │
      │  - Noon EG      - Jumia       │               │  - Stateful dedup (>=5% drop) │
      │  - Breadfast    - B.Tech      │               │  - Laptop spam bug resolved   │
      │  - Talabat      - 2B          │               │  - Price history tracking     │
      │  - ValU                       │               └───────────────┬───────────────┘
      └───────────────┬───────────────┘                               │
                      │                                               │
                      ▼                                               │
      ┌───────────────────────────────┐                               │
      │      Category Classifier      │                               │
      │  - Baby Diapers               │                               │
      │  - Baby Clothes               │                               │
      │  - Adult & Kids Clothing      │                               │
      │  - Household General          │                               │
      │  - Dedicated Laptops          │                               │
      └───────────────┬───────────────┘                               │
                      │                                               │
                      └───────────────────────┬───────────────────────┘
                                              │ Alert-Worthy Deals
                                              ▼
                              ┌───────────────────────────────┐
                              │  Telegram Notification Service│
                              │       (@Deals_egy_bot)        │
                              │                               │
                              │  - Safe HTML parse mode       │
                              │  - Direct order inline button │
                              │  - Dedicated #Laptop tagging  │
                              │  - Multi-subscriber broadcast │
                              └───────────────────────────────┘
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Canonical Deal Data Model | Dataclass with schema validation, URL canonicalization, and SHA-256 fingerprint | M1 | Spec Miner |
| 2 | Category Classifier | Arabic & English regex classification into 5 target categories | M1 | Spec Miner |
| 3 | Stateful Deduplication Engine | Hash & price-delta based alert suppression, resolving laptop alert spam bug | M1 | Spec Miner |
| 4 | Database Persistence Layer | SQLite schema with deals, price_history, and subscribers tables | M1 | Codebase Survey |
| 5 | Base Scraper Framework | BaseStoreScraper interface with async timeout protection & fallback fixtures | M2 | Store Survey |
| 6 | Amazon Egypt Scraper | Scrapes household, diapers, and laptops with canonical ASIN direct order links | M2 | Store Survey |
| 7 | Noon Egypt Scraper | Scrapes household, baby, clothing, and laptops with direct order URLs | M2 | Store Survey |
| 8 | Breadfast Scraper | Scrapes household essentials, baby diapers, and groceries with direct deep links | M2 | Store Survey |
| 9 | Talabat Scraper | Scrapes Talabat Mart groceries and household offers with direct links | M2 | Store Survey |
| 10 | ValU Deals Scraper | Scrapes ValU partner promotions (0% interest electronics/household) | M2 | Store Survey |
| 11 | Carrefour Egypt Scraper | Scrapes baby, household, and electronic deals with direct URLs | M2 | Store Survey |
| 12 | Jumia Egypt Scraper | Scrapes fashion, baby, household, and laptops with direct URLs | M2 | Store Survey |
| 13 | B.Tech Scraper | Scrapes laptops and home appliances with Mini Cash installment info & URLs | M2 | Store Survey |
| 14 | 2B Egypt Scraper | Scrapes laptops and electronics with direct product URLs | M2 | Store Survey |
| 15 | Scraper Engine Orchestrator | Concurrent async execution of all 9 store scrapers with timeout bounds | M2 | Store Survey |
| 16 | Telegram HTML Formatter | Crash-proof HTML message rendering with html.escape and discount banners | M3 | Spec Miner |
| 17 | Direct Order Links Button | Verified clickable InlineKeyboardButton leading to checkout/product page | M3 | R2 Mandate |
| 18 | Dedicated Laptop Tracking | Visibly isolated formatting, prominent #Laptop tag, and /laptop command | M3 | R3 Mandate |
| 19 | Subscriber Management | Multi-user / channel persistence for Telegram notifications | M3 | Codebase Survey |
| 20 | Continuous Polling Engine | 1-2 minute polling loop (60-120s, default 90s) with crash immunity | M4 | R1 Mandate |
| 21 | Webhook & API Endpoints | Health check (/health), deal inventory API (/api/deals) | M4 | Codebase Survey |
| 22 | Application Entrypoint Refactor | Clean async lifecycle binding FastAPI, Telegram bot, and Poller | M4 | Codebase Survey |
| 23 | E2E Testing Suite (Tiers 1-4) | Comprehensive unit, boundary, integration, and opaque-box E2E tests | E2E Track / M5 | Acceptance Criteria |
| 24 | Final Acceptance Verification | Verification of all acceptance criteria, coverage hardening, and Victory Audit | M5 | System Directive |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Data Models, Classifier & Deduplication Engine | Features 1, 2, 3, 4 | none | DONE |
| M2 | Modular Scraper Engine & 9 Store Adapters | Features 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15 | M1 | PLANNED |
| M3 | Telegram Notification Service & Laptop Tracking | Features 16, 17, 18, 19 | M1 | PLANNED |
| M4 | Polling Engine & Application Lifecycle | Features 20, 21, 22 | M1, M2, M3 | PLANNED |
| M5 | Final E2E Integration, Full Test Pass & Hardening | Features 23, 24 | M4, E2E Track | PLANNED |
| E2E | Opaque-Box E2E Testing Track | Comprehensive 4-tier test suite & harness | M1 interface specs | DONE |

## Code Layout
```
egypt-black-friday-bot/
├── core/
│   ├── __init__.py
│   ├── models.py            # Canonical Deal, StoreEnum, CategoryEnum
│   └── classifier.py        # Category regex classification rules
├── database/
│   ├── __init__.py
│   └── db_service.py        # SQLite persistence, schema, and stateful deduplication
├── scrapers/
│   ├── __init__.py
│   ├── base.py              # BaseStoreScraper interface & timeout wrapper
│   ├── engine.py            # Concurrent ScraperEngine orchestrator
│   ├── amazon_eg.py         # Amazon Egypt scraper adapter
│   ├── noon_eg.py           # Noon Egypt scraper adapter
│   ├── breadfast.py         # Breadfast scraper adapter
│   ├── talabat.py           # Talabat Egypt scraper adapter
│   ├── valu.py              # ValU deals scraper adapter
│   ├── carrefour_eg.py      # Carrefour Egypt scraper adapter
│   ├── jumia_eg.py          # Jumia Egypt scraper adapter
│   ├── btech.py             # B.Tech scraper adapter
│   └── two_b.py             # 2B Egypt scraper adapter
├── services/
│   ├── __init__.py
│   ├── telegram_service.py  # Telegram alert formatter & dispatcher
│   └── polling_service.py   # Continuous 1-2 min polling loop
├── bot.py                   # Main entrypoint (FastAPI + Telegram Polling runner)
├── tests/
│   ├── conftest.py          # Mock fixtures, sample HTML, mock Telegram bot
│   ├── test_tier1_models_classifier.py
│   ├── test_tier1_scrapers.py
│   ├── test_tier2_boundary_corner.py
│   ├── test_tier3_deduplication.py
│   └── test_tier4_e2e_workflow.py
├── run_tests.py             # Self-contained test runner
├── PROJECT.md
├── TEST_INFRA.md
└── TEST_READY.md
```

## Interface Contracts

### 1. `core.models`
```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class StoreEnum(str, Enum):
    AMAZON_EG = "Amazon Egypt"
    NOON_EG = "Noon Egypt"
    BREADFAST = "Breadfast"
    TALABAT = "Talabat Egypt"
    VALU = "ValU"
    CARREFOUR_EG = "Carrefour Egypt"
    JUMIA_EG = "Jumia Egypt"
    BTECH = "B.TECH"
    TWO_B = "2B Egypt"

class CategoryEnum(str, Enum):
    BABY_DIAPERS = "حفاضات أطفال"
    BABY_CLOTHES = "ملابس رضع وأطفال"
    CLOTHING_ADULT_KIDS = "أزياء وملابس"
    HOUSEHOLD_GENERAL = "مستلزمات منزلية"
    LAPTOPS = "لابتوبات وأجهزة"

@dataclass
class Deal:
    id: str                   # store_code:sku
    title: str
    store: StoreEnum
    category: CategoryEnum
    original_price: float
    discount_price: float
    discount_percentage: float
    url: str                  # Canonical, direct clickable purchase link
    image_url: Optional[str] = None
    is_flash_sale: bool = False
    is_special_laptop: bool = False
    coupon_code: Optional[str] = None
    installment_info: Optional[str] = None
    deal_hash: Optional[str] = None  # SHA-256 fingerprint

    def compute_hash(self) -> str: ...
```

### 2. `core.classifier`
```python
def classify_deal(title: str, store: StoreEnum, raw_category: Optional[str] = None) -> CategoryEnum: ...
```

### 3. `database.db_service`
```python
class DatabaseService:
    def __init__(self, db_path: str = "deals.db"): ...
    def init_db(self): ...
    def process_and_deduplicate(self, deal: Deal) -> tuple[bool, str]:
        """Returns (is_alert_worthy, reason) where reason in ('NEW_DEAL', 'PRICE_DROP_5PCT', 'UNCHANGED_SUPPRESSED')"""
    def save_deal(self, deal: Deal): ...
    def get_all_deals(self, category: Optional[str] = None) -> list[Deal]: ...
    def get_active_laptops(self) -> list[Deal]: ...
    def add_subscriber(self, chat_id: str, topic: Optional[str] = None): ...
    def get_subscribers(self, topic: Optional[str] = None) -> list[str]: ...
```

### 4. `scrapers.base` & `scrapers.engine`
```python
class BaseStoreScraper:
    store: StoreEnum
    async def scrape(self) -> list[Deal]: ...

class ScraperEngine:
    def __init__(self, scrapers: list[BaseStoreScraper] = None, timeout_per_store: float = 4.0): ...
    async def scrape_all(self) -> list[Deal]: ...
```

### 5. `services.telegram_service`
```python
class TelegramNotificationService:
    def __init__(self, bot_token: str, db_service: DatabaseService): ...
    def format_deal_message(self, deal: Deal) -> tuple[str, InlineKeyboardMarkup]:
        """Returns HTML-formatted text and inline keyboard markup with direct order button"""
    async def broadcast_deal(self, deal: Deal, bot: Optional[Bot] = None) -> int:
        """Broadcasts deal to all registered subscribers / channels, tagging #Laptop if laptop"""
```

### 6. `services.polling_service`
```python
class PollingService:
    def __init__(self, scraper_engine: ScraperEngine, db_service: DatabaseService, telegram_service: TelegramNotificationService, poll_interval: int = 90): ...
    async def run_once(self) -> dict: ...
    async def run_loop(self): ...
```
