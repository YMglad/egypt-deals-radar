"""
Canonical Data Models and Enums for Egyptian Deals & Black Friday Telegram Bot.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import re
from typing import Optional, Any
from urllib.parse import urlparse, parse_qsl, urlencode, urlunsplit


class StoreEnum(str, Enum):
    """The 9 authoritative Egyptian retail and e-commerce platforms."""
    AMAZON_EG = "Amazon Egypt"
    NOON_EG = "Noon Egypt"
    BREADFAST = "Breadfast"
    TALABAT = "Talabat Egypt"
    VALU = "ValU"
    CARREFOUR_EG = "Carrefour Egypt"
    JUMIA_EG = "Jumia Egypt"
    BTECH = "B.TECH"
    TWO_B = "2B Egypt"

    @classmethod
    def from_str(cls, val: Any) -> StoreEnum:
        """Resolve store from enum, value, or common aliases."""
        if isinstance(val, StoreEnum):
            return val
        if not val or not isinstance(val, str):
            return cls.AMAZON_EG
        clean = val.strip().lower()

        alias_map = {
            "amazon": cls.AMAZON_EG,
            "amazon eg": cls.AMAZON_EG,
            "amazon egypt": cls.AMAZON_EG,
            "أمازون": cls.AMAZON_EG,
            "أمازون مصر": cls.AMAZON_EG,
            "noon": cls.NOON_EG,
            "noon eg": cls.NOON_EG,
            "noon egypt": cls.NOON_EG,
            "نون": cls.NOON_EG,
            "breadfast": cls.BREADFAST,
            "بريدفاست": cls.BREADFAST,
            "talabat": cls.TALABAT,
            "talabat eg": cls.TALABAT,
            "talabat egypt": cls.TALABAT,
            "طلبات": cls.TALABAT,
            "valu": cls.VALU,
            "فاليو": cls.VALU,
            "carrefour": cls.CARREFOUR_EG,
            "carrefour eg": cls.CARREFOUR_EG,
            "carrefour egypt": cls.CARREFOUR_EG,
            "كارفور": cls.CARREFOUR_EG,
            "jumia": cls.JUMIA_EG,
            "jumia eg": cls.JUMIA_EG,
            "jumia egypt": cls.JUMIA_EG,
            "جوميا": cls.JUMIA_EG,
            "b.tech": cls.BTECH,
            "btech": cls.BTECH,
            "بي تك": cls.BTECH,
            "2b": cls.TWO_B,
            "2b egypt": cls.TWO_B,
            "two b": cls.TWO_B,
            "توبي": cls.TWO_B,
        }
        if clean in alias_map:
            return alias_map[clean]

        for member in cls:
            if member.value.lower() == clean or member.name.lower() == clean:
                return member
        return cls.AMAZON_EG


class CategoryEnum(str, Enum):
    """The 5 target categories for Black Friday & family deals monitoring."""
    BABY_DIAPERS = "حفاضات أطفال"
    BABY_CLOTHES = "ملابس رضع وأطفال"
    CLOTHING_ADULT_KIDS = "أزياء وملابس"
    HOUSEHOLD_GENERAL = "مستلزمات منزلية"
    LAPTOPS = "لابتوبات وأجهزة"

    @classmethod
    def from_str(cls, val: Any) -> CategoryEnum:
        """Resolve category from enum, value, or common aliases."""
        if isinstance(val, CategoryEnum):
            return val
        if not val or not isinstance(val, str):
            return cls.HOUSEHOLD_GENERAL
        clean = val.strip().lower()

        alias_map = {
            "baby_diapers": cls.BABY_DIAPERS,
            "baby diapers": cls.BABY_DIAPERS,
            "diapers": cls.BABY_DIAPERS,
            "حفاضات": cls.BABY_DIAPERS,
            "حفاضات أطفال": cls.BABY_DIAPERS,
            "baby_clothes": cls.BABY_CLOTHES,
            "baby clothes": cls.BABY_CLOTHES,
            "ملابس رضع": cls.BABY_CLOTHES,
            "ملابس رضع وأطفال": cls.BABY_CLOTHES,
            "clothing_adult_kids": cls.CLOTHING_ADULT_KIDS,
            "clothing": cls.CLOTHING_ADULT_KIDS,
            "fashion": cls.CLOTHING_ADULT_KIDS,
            "أزياء": cls.CLOTHING_ADULT_KIDS,
            "أزياء وملابس": cls.CLOTHING_ADULT_KIDS,
            "household_general": cls.HOUSEHOLD_GENERAL,
            "household": cls.HOUSEHOLD_GENERAL,
            "home": cls.HOUSEHOLD_GENERAL,
            "electronics": cls.HOUSEHOLD_GENERAL,
            "مستلزمات منزلية": cls.HOUSEHOLD_GENERAL,
            "laptops": cls.LAPTOPS,
            "laptop": cls.LAPTOPS,
            "لابتوب": cls.LAPTOPS,
            "لابتوبات": cls.LAPTOPS,
            "لابتوبات وأجهزة": cls.LAPTOPS,
        }
        if clean in alias_map:
            return alias_map[clean]

        for member in cls:
            if member.value.lower() == clean or member.name.lower() == clean:
                return member
        return cls.HOUSEHOLD_GENERAL


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "ref_", "tag", "ascsubtag", "fbclid", "gclid", "_ga", "campaign_id",
    "ad_id", "gbraid", "wbraid", "source", "spm", "igshid", "msclkid",
    "dclid", "sc_channel", "sc_campaign", "sc_country", "sc_geo"
}


def canonicalize_url(raw_url: str) -> str:
    """
    Normalizes a product URL:
    - Trims whitespace and removes trailing slashes
    - Normalizes scheme to https
    - Lowercases hostname
    - Cleans tracking and analytics query parameters (UTM, ref, fbclid, etc.)
    - Preserves canonical product slugs, IDs, and ASINs
    """
    if not raw_url:
        raise ValueError("URL cannot be empty")
    cleaned = raw_url.strip()
    if not cleaned or cleaned == "#":
        raise ValueError(f"Invalid URL: '{raw_url}'")

    parsed = urlparse(cleaned)
    if not parsed.scheme:
        cleaned = "https://" + cleaned
        parsed = urlparse(cleaned)

    scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
    netloc = parsed.netloc.lower()

    # Normalize Amazon path to clean /dp/ASIN if present
    path = parsed.path
    amazon_match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", path, re.IGNORECASE)
    if amazon_match and ("amazon." in netloc or "amzn." in netloc):
        asin = amazon_match.group(1).upper()
        path = f"/dp/{asin}"

    # Strip trailing slash unless root
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter out tracking params
    query_items = parse_qsl(parsed.query, keep_blank_values=False)
    filtered = [
        (k, v) for k, v in query_items
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    # Sort query items for deterministic URLs
    filtered.sort(key=lambda x: x[0])
    clean_query = urlencode(filtered)

    return urlunsplit((scheme, netloc, path, clean_query, ""))


def compute_deal_hash(
    store: str,
    canonical_url: str,
    discount_price: float,
    coupon_code: Optional[str] = None
) -> str:
    """
    Computes a deterministic SHA-256 fingerprint for a deal.
    Changes whenever store, canonical URL, discount price, or coupon changes.
    """
    store_str = store.strip().lower()
    url_str = canonical_url.strip()
    price_str = f"{float(discount_price):.2f}"
    coupon_str = (coupon_code or "").strip().upper()

    payload = f"{store_str}|{url_str}|{price_str}|{coupon_str}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class Deal:
    """Canonical representation of an Egyptian store deal."""
    id: str
    title: str
    store: StoreEnum
    category: CategoryEnum
    original_price: float
    discount_price: float
    discount_percentage: float
    url: str
    image_url: Optional[str] = None
    is_flash_sale: bool = False
    is_special_laptop: bool = False
    coupon_code: Optional[str] = None
    installment_info: Optional[str] = None
    deal_hash: Optional[str] = None

    def __post_init__(self):
        # Enforce StoreEnum
        if not isinstance(self.store, StoreEnum):
            self.store = StoreEnum.from_str(self.store)

        # Enforce CategoryEnum
        if not isinstance(self.category, CategoryEnum):
            self.category = CategoryEnum.from_str(self.category)

        # Clean title
        self.title = " ".join(self.title.strip().split())

        # Canonicalize URL
        if self.url and str(self.url).strip().lower() not in ("", "none", "null"):
            try:
                self.url = canonicalize_url(str(self.url).strip())
            except Exception:
                pass  # Keep existing if unparseable
        else:
            self.url = ""

        # Ensure float prices
        self.original_price = float(self.original_price if self.original_price is not None else 0.0)
        self.discount_price = float(self.discount_price if self.discount_price is not None else 0.0)

        if self.original_price <= 0 and self.discount_price > 0:
            self.original_price = self.discount_price

        # Cast discount_percentage to float before evaluating <= 0, and clamp negative values to 0.0
        try:
            self.discount_percentage = float(self.discount_percentage) if self.discount_percentage is not None else 0.0
        except (ValueError, TypeError):
            self.discount_percentage = 0.0

        if self.discount_percentage < 0.0:
            self.discount_percentage = 0.0

        if self.discount_percentage <= 0.0 and self.original_price > self.discount_price > 0:
            self.discount_percentage = round(
                ((self.original_price - self.discount_price) / self.original_price) * 100, 1
            )
        else:
            self.discount_percentage = float(self.discount_percentage)

        # Auto-flag laptops
        if self.category == CategoryEnum.LAPTOPS:
            self.is_special_laptop = True

        # Compute hash if missing
        if not self.deal_hash:
            self.deal_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute SHA-256 fingerprint from store, url, discount_price, coupon_code."""
        store_val = self.store.value if isinstance(self.store, StoreEnum) else str(self.store)
        return compute_deal_hash(
            store=store_val,
            canonical_url=self.url,
            discount_price=self.discount_price,
            coupon_code=self.coupon_code
        )

    @property
    def is_laptop(self) -> bool:
        """Helper property for laptop tracking."""
        return self.is_special_laptop or self.category == CategoryEnum.LAPTOPS

    @property
    def discount_amount(self) -> float:
        """Computes monetary discount amount in EGP."""
        return max(0.0, round(self.original_price - self.discount_price, 2))

    def to_dict(self) -> dict[str, Any]:
        """Serialize Deal to dictionary with primitive values."""
        return {
            "id": self.id,
            "title": self.title,
            "store": self.store.value if isinstance(self.store, StoreEnum) else str(self.store),
            "category": self.category.value if isinstance(self.category, CategoryEnum) else str(self.category),
            "original_price": self.original_price,
            "discount_price": self.discount_price,
            "discount_percentage": self.discount_percentage,
            "url": self.url,
            "image_url": self.image_url or "",
            "is_flash_sale": 1 if self.is_flash_sale else 0,
            "is_special_laptop": 1 if self.is_special_laptop else 0,
            "coupon_code": self.coupon_code or "",
            "installment_info": self.installment_info or "",
            "deal_hash": self.deal_hash or self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Deal:
        """Deserialize Deal from dictionary."""
        store = StoreEnum.from_str(data.get("store", StoreEnum.AMAZON_EG))
        category = CategoryEnum.from_str(data.get("category", CategoryEnum.HOUSEHOLD_GENERAL))

        orig_p = data.get("original_price")
        disc_p = data.get("discount_price")
        disc_pct = data.get("discount_percentage")

        try:
            original_price = float(orig_p) if orig_p is not None else 0.0
        except (ValueError, TypeError):
            original_price = 0.0

        try:
            discount_price = float(disc_p) if disc_p is not None else 0.0
        except (ValueError, TypeError):
            discount_price = 0.0

        try:
            discount_percentage = float(disc_pct) if disc_pct is not None else 0.0
        except (ValueError, TypeError):
            discount_percentage = 0.0

        raw_url = data.get("url")
        url = str(raw_url).strip() if raw_url is not None else ""
        if url.lower() in ("none", "null"):
            url = ""

        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            store=store,
            category=category,
            original_price=original_price,
            discount_price=discount_price,
            discount_percentage=discount_percentage,
            url=url,
            image_url=data.get("image_url") or None,
            is_flash_sale=bool(data.get("is_flash_sale", False)),
            is_special_laptop=bool(data.get("is_special_laptop", False)),
            coupon_code=data.get("coupon_code") or None,
            installment_info=data.get("installment_info") or None,
            deal_hash=data.get("deal_hash") or None,
        )
