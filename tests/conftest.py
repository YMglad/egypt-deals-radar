"""
Mock fixtures, synthetic store payloads, mock Telegram client,
and database test factories for Egyptian Deals & Black Friday Bot.
"""

from __future__ import annotations
import asyncio
import json
import re
import sqlite3
import datetime
from dataclasses import dataclass, field
from typing import Optional, Any, Callable, List, Tuple
from urllib.parse import urlparse

from core.models import StoreEnum, CategoryEnum, Deal, canonicalize_url, compute_deal_hash


# ============================================================================
# 1. SYNTHETIC FIXTURES FOR ALL 9 STORES
# ============================================================================

AMAZON_EG_HTML = """
<!DOCTYPE html>
<html>
<body>
<div class="s-main-slot s-result-list">
    <div class="s-result-item" data-asin="B09H123456">
        <h2>
            <a class="a-link-normal s-underline-text s-underline-link-text s-link-style a-text-normal" 
               href="/dp/B09H123456?ref=sr_1_1&keywords=pampers&qid=1690000000">
                <span>بامبرز حفاضات أطفال كلوت مقاس 4، العبوة الاقتصادية 58 حفاضة</span>
            </a>
        </h2>
        <div class="a-price a-text-price a-size-medium" data-a-size="b">
            <span class="a-price-whole">399</span>
            <span class="a-price-fraction">50</span>
        </div>
        <div class="a-section a-spacing-none a-text-strike">
            <span class="a-price-symbol">EGP</span>
            <span class="a-price-whole">520</span>
            <span class="a-price-fraction">00</span>
        </div>
        <span class="a-badge-text">وفر 23%</span>
    </div>
    <div class="s-result-item" data-asin="B08XYZ7890">
        <h2>
            <a class="a-link-normal" href="/dp/B08XYZ7890?ref=sr_1_2&tag=affil-21">
                <span>ASUS ROG Strix G16 Gaming Laptop 16" FHD+ 165Hz Intel Core i7 RTX 4060</span>
            </a>
        </h2>
        <div class="a-price">
            <span class="a-price-whole">64,999</span>
            <span class="a-price-fraction">00</span>
        </div>
        <div class="a-section a-spacing-none a-text-strike">
            <span class="a-price-whole">75,000</span>
            <span class="a-price-fraction">00</span>
        </div>
        <span class="a-badge-text">وفر 13%</span>
    </div>
</div>
</body>
</html>
"""

NOON_EG_JSON = {
    "hits": [
        {
            "sku": "N53321456A",
            "name": "حفاضات فاين بيبي مقاس 5 كلوت لمسة قطنية 56 حفاضة",
            "price": 315.0,
            "was_price": 420.0,
            "discount_percentage": 25.0,
            "product_url": "https://www.noon.com/egypt-en/fine-baby-fast-absorption-diapers-maxi-size-5-56-count/N53321456A/p/?o=abcde&utm_source=cpc",
            "image_url": "https://f.nooncdn.com/products/tr:n-t_400/pampers.jpg",
            "category": "Baby Diapers"
        },
        {
            "sku": "N70019283A",
            "name": "Lenovo Legion 5 Gaming Laptop AMD Ryzen 7 16GB RAM 512GB SSD RTX 4060",
            "price": 54999.0,
            "was_price": 62000.0,
            "discount_percentage": 11.3,
            "product_url": "https://www.noon.com/egypt-en/legion-5-gaming-laptop-15-6-inch-wqhd/N70019283A/p/?utm_campaign=black_friday",
            "image_url": "https://f.nooncdn.com/products/tr:n-t_400/lenovo.jpg",
            "category": "Laptops"
        }
    ]
}

BREADFAST_JSON = {
    "products": [
        {
            "id": "bf-10492",
            "title": "حفاضات مولفيكس ماكسي مقاس 4 - 58 حفاضة شريط لاصق",
            "price": 365.0,
            "original_price": 440.0,
            "discount_rate": 17,
            "slug": "molfix-diapers-size-4-58-pcs",
            "web_url": "https://www.breadfast.com/product/molfix-diapers-size-4-58-pcs?source=carousel",
            "department": "Baby Care"
        },
        {
            "id": "bf-20381",
            "title": "مسحوق غسيل أوتوماتيك برسيل ديب كلين برائحة اللافندر 5 كجم",
            "price": 289.0,
            "original_price": 350.0,
            "discount_rate": 17,
            "slug": "persil-deep-clean-lavender-5kg",
            "web_url": "https://www.breadfast.com/product/persil-deep-clean-lavender-5kg",
            "department": "Household Cleaning"
        }
    ]
}

TALABAT_JSON = {
    "items": [
        {
            "item_id": "tb-99120",
            "name": "بامبرز بيبي دراي مقاس 3 عبوة التوفير 60 حفاضة",
            "price": 380.0,
            "old_price": 460.0,
            "discount": 17.4,
            "url": "https://www.talabat.com/egypt/talabat-mart/product/tb-99120-pampers-baby-dry-size-3?ref=feed",
            "section": "Baby Products"
        },
        {
            "item_id": "tb-88219",
            "name": "سائل غسيل الأطباق فيري بالليمون المركز 650 ملل",
            "price": 45.0,
            "old_price": 60.0,
            "discount": 25.0,
            "url": "https://www.talabat.com/egypt/talabat-mart/product/tb-88219-fairy-lemon-650ml",
            "section": "Cleaning & Household"
        }
    ]
}

VALU_HTML = """
<div class="deals-grid">
    <div class="deal-card" data-partner="B.TECH" data-id="valu-101">
        <h3 class="product-title">Dell G15 5530 Gaming Laptop Core i7-13650HX 16GB 512GB RTX 4050</h3>
        <div class="pricing">
            <span class="sale-price">48,500 EGP</span>
            <span class="regular-price">56,000 EGP</span>
        </div>
        <div class="installment-badge">0% فوائد على 12 شهر مع ValU</div>
        <a class="btn-direct-order" href="https://www.valu.com.eg/shop/dell-g15-5530-laptop?campaign=bf_valu&fbclid=abcdef">اطلب بالتقسيط المباشر</a>
    </div>
    <div class="deal-card" data-partner="Tradeline" data-id="valu-102">
        <h3 class="product-title">قلاية هوائية فيليبس بدون زيت XXL سعة 7.2 لتر ديجيتال HD9280</h3>
        <div class="pricing">
            <span class="sale-price">8,999 EGP</span>
            <span class="regular-price">11,500 EGP</span>
        </div>
        <div class="installment-badge">تقسيط حتى 24 شهر بدون مقدم</div>
        <a class="btn-direct-order" href="https://www.valu.com.eg/shop/philips-airfryer-xxl-hd9280">تسوق الآن</a>
    </div>
</div>
"""

CARREFOUR_EG_HTML = """
<div class="product-list">
    <div class="product-card" data-sku="CRF-10029">
        <h2 class="title">
            <a href="/mafegy/en/baby-products/diapers/pampers-pants-size-4-58-pack/p/10029?utm_medium=cpc">
                Pampers Pants Size 4, Maxi 9-14 kg, 58 Diapers Pack
            </a>
        </h2>
        <div class="price-container">
            <span class="current-price">375.00 EGP</span>
            <span class="original-price">480.00 EGP</span>
            <span class="discount-badge">22% OFF</span>
        </div>
    </div>
    <div class="product-card" data-sku="CRF-88120">
        <h2 class="title">
            <a href="/mafegy/en/clothing/kids-romper-sleepsuit-pack-of-3/p/88120">
                سالوبيت أطفال رضع قطن 100% عبوة من 3 قطع حديثي الولادة
            </a>
        </h2>
        <div class="price-container">
            <span class="current-price">299.00 EGP</span>
            <span class="original-price">450.00 EGP</span>
            <span class="discount-badge">33% OFF</span>
        </div>
    </div>
</div>
"""

JUMIA_EG_HTML = """
<div class="items-grid">
    <article class="prd _fb col c-prd">
        <a class="core" href="/hp-victus-15-fa1093dx-gaming-laptop-intel-core-i5-13420h-8gb-ram-512gb-ssd-rtx-3050-6gb-15.6-fhd-144hz-windows-11-blue-99212345.html?utm_source=banner">
            <div class="name">HP Victus 15 Gaming Laptop Intel Core i5 RTX 3050 15.6 FHD 144Hz</div>
            <div class="prc">33,999 EGP</div>
            <div class="old">40,000 EGP</div>
            <div class="bdg _dsct">15%</div>
        </a>
    </article>
    <article class="prd _fb col c-prd">
        <a class="core" href="/fashion-men-casual-cotton-hoodie-sweatshirt-black-883921.html">
            <div class="name">سويت شيرت هودي رجالي قطن شتوي كاجوال أسود</div>
            <div class="prc">450 EGP</div>
            <div class="old">750 EGP</div>
            <div class="bdg _dsct">40%</div>
        </a>
    </article>
</div>
"""

BTECH_HTML = """
<div class="products-grid">
    <div class="product-item" data-id="bt-55102">
        <a class="product-item-link" href="https://btech.com/en/lenovo-ideapad-gaming-3-laptop-amd-ryzen-5-rtx-3050.html?ref=deals_hub">
            لابتوب لينوفو ايديا باد للألعاب 3 شاشة 15.6 بوصة AMD Ryzen 5 كارت RTX 3050
        </a>
        <div class="price-box">
            <span class="special-price">31,500 ج.م</span>
            <span class="old-price">38,000 ج.م</span>
        </div>
        <div class="minicash-badge">قسط شهري يبدأ من 999 ج.م مع ميني كاش</div>
    </div>
    <div class="product-item" data-id="bt-77291">
        <a class="product-item-link" href="https://btech.com/en/tornado-electric-kettle-1-7-liter-stainless-steel.html">
            غلاية مياه كهربائية تورنيدو استانلس ستيل سعة 1.7 لتر
        </a>
        <div class="price-box">
            <span class="special-price">699 ج.م</span>
            <span class="old-price">950 ج.م</span>
        </div>
        <div class="minicash-badge">0% فوائد مع ميني كاش 6 شهور</div>
    </div>
</div>
"""

TWO_B_HTML = """
<div class="category-products">
    <li class="item product product-item" data-id="2b-9901">
        <div class="product details product-item-details">
            <strong class="product name product-item-name">
                <a class="product-item-link" href="https://2b.com.eg/en/acer-nitro-v15-gaming-laptop-intel-core-i7-13620h-rtx-4050.html?utm_campaign=blackfriday">
                    Acer Nitro V 15 Gaming Laptop Intel Core i7-13620H 16GB 512GB SSD RTX 4050
                </a>
            </strong>
            <div class="price-box price-final_price">
                <span class="special-price"><span class="price">46,999 EGP</span></span>
                <span class="old-price"><span class="price">54,000 EGP</span></span>
            </div>
            <span class="discount-percent">-13%</span>
        </div>
    </li>
    <li class="item product product-item" data-id="2b-8812">
        <div class="product details product-item-details">
            <strong class="product name product-item-name">
                <a class="product-item-link" href="https://2b.com.eg/en/asus-tuf-gaming-f15-laptop-core-i5-rtx-3050.html">
                    ASUS TUF Gaming F15 Laptop Core i5 16GB RAM 512GB SSD RTX 3050
                </a>
            </strong>
            <div class="price-box price-final_price">
                <span class="special-price"><span class="price">33,500 EGP</span></span>
                <span class="old-price"><span class="price">39,000 EGP</span></span>
            </div>
            <span class="discount-percent">-14%</span>
        </div>
    </li>
</div>
"""


# ============================================================================
# 2. REFERENCE STORE PARSER FUNCTIONS
# ============================================================================

def parse_amazon_snippet(html_content: str) -> List[dict]:
    """Extracts deals from Amazon EG HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    items = soup.select(".s-result-item[data-asin]")
    for item in items:
        asin = item.get("data-asin", "").strip()
        if not asin:
            continue
        title_el = item.select_one("h2 a span")
        link_el = item.select_one("h2 a")
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        raw_url = link_el.get("href", "")
        if raw_url.startswith("/"):
            raw_url = f"https://www.amazon.eg{raw_url}"

        # Current price
        price_whole = item.select_one(".a-price .a-price-whole")
        price_fraction = item.select_one(".a-price .a-price-fraction")
        curr_price = 0.0
        if price_whole:
            whole = re.sub(r"[^\d]", "", price_whole.get_text(strip=True))
            frac = re.sub(r"[^\d]", "", price_fraction.get_text(strip=True)) if price_fraction else "00"
            curr_price = float(f"{whole}.{frac}")

        # Strike/Original price
        strike_whole = item.select_one(".a-text-strike .a-price-whole")
        orig_price = curr_price
        if strike_whole:
            w = re.sub(r"[^\d]", "", strike_whole.get_text(strip=True))
            orig_price = float(w)

        discount_pct = 0.0
        if orig_price > curr_price > 0:
            discount_pct = round(((orig_price - curr_price) / orig_price) * 100, 1)

        deals.append({
            "id": f"amazon_eg_{asin}",
            "store": StoreEnum.AMAZON_EG,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": discount_pct,
            "url": canonicalize_url(raw_url),
        })
    return deals


def parse_noon_snippet(json_data: dict) -> List[dict]:
    """Extracts deals from Noon EG JSON payload."""
    deals = []
    for hit in json_data.get("hits", []):
        sku = hit.get("sku", "")
        curr_price = float(hit.get("price", 0.0))
        orig_price = float(hit.get("was_price", curr_price))
        raw_url = hit.get("product_url", "")
        deals.append({
            "id": f"noon_eg_{sku}",
            "store": StoreEnum.NOON_EG,
            "title": hit.get("name", ""),
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": float(hit.get("discount_percentage", 0.0)),
            "url": canonicalize_url(raw_url),
            "image_url": hit.get("image_url", ""),
        })
    return deals


def parse_breadfast_snippet(json_data: dict) -> List[dict]:
    """Extracts deals from Breadfast JSON payload."""
    deals = []
    for p in json_data.get("products", []):
        curr_price = float(p.get("price", 0.0))
        orig_price = float(p.get("original_price", curr_price))
        deals.append({
            "id": f"breadfast_{p.get('id', '')}",
            "store": StoreEnum.BREADFAST,
            "title": p.get("title", ""),
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": float(p.get("discount_rate", 0.0)),
            "url": canonicalize_url(p.get("web_url", "")),
        })
    return deals


def parse_talabat_snippet(json_data: dict) -> List[dict]:
    """Extracts deals from Talabat Mart JSON payload."""
    deals = []
    for item in json_data.get("items", []):
        curr_price = float(item.get("price", 0.0))
        orig_price = float(item.get("old_price", curr_price))
        deals.append({
            "id": f"talabat_{item.get('item_id', '')}",
            "store": StoreEnum.TALABAT,
            "title": item.get("name", ""),
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": float(item.get("discount", 0.0)),
            "url": canonicalize_url(item.get("url", "")),
        })
    return deals


def parse_valu_snippet(html_content: str) -> List[dict]:
    """Extracts deals from ValU HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    for card in soup.select(".deal-card"):
        deal_id = card.get("data-id", "")
        title_el = card.select_one(".product-title")
        sale_el = card.select_one(".sale-price")
        reg_el = card.select_one(".regular-price")
        link_el = card.select_one(".btn-direct-order")
        install_el = card.select_one(".installment-badge")

        title = title_el.get_text(strip=True) if title_el else ""
        raw_sale = re.sub(r"[^\d.]", "", sale_el.get_text(strip=True)) if sale_el else "0"
        raw_reg = re.sub(r"[^\d.]", "", reg_el.get_text(strip=True)) if reg_el else raw_sale
        curr_price = float(raw_sale)
        orig_price = float(raw_reg)
        raw_url = link_el.get("href", "") if link_el else ""

        deals.append({
            "id": f"valu_{deal_id}",
            "store": StoreEnum.VALU,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": round(((orig_price - curr_price) / orig_price) * 100, 1) if orig_price > curr_price else 0.0,
            "url": canonicalize_url(raw_url),
            "installment_info": install_el.get_text(strip=True) if install_el else None,
        })
    return deals


def parse_carrefour_snippet(html_content: str) -> List[dict]:
    """Extracts deals from Carrefour Egypt HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    for card in soup.select(".product-card"):
        sku = card.get("data-sku", "")
        link_el = card.select_one("h2.title a")
        if not link_el:
            continue
        title = link_el.get_text(strip=True)
        raw_url = link_el.get("href", "")
        if raw_url.startswith("/"):
            raw_url = f"https://www.carrefouregypt.com{raw_url}"

        curr_el = card.select_one(".current-price")
        orig_el = card.select_one(".original-price")
        curr_price = float(re.sub(r"[^\d.]", "", curr_el.get_text(strip=True))) if curr_el else 0.0
        orig_price = float(re.sub(r"[^\d.]", "", orig_el.get_text(strip=True))) if orig_el else curr_price

        deals.append({
            "id": f"carrefour_{sku}",
            "store": StoreEnum.CARREFOUR_EG,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": round(((orig_price - curr_price) / orig_price) * 100, 1) if orig_price > curr_price else 0.0,
            "url": canonicalize_url(raw_url),
        })
    return deals


def parse_jumia_snippet(html_content: str) -> List[dict]:
    """Extracts deals from Jumia Egypt HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    for prd in soup.select("article.prd"):
        link_el = prd.select_one("a.core")
        if not link_el:
            continue
        raw_url = link_el.get("href", "")
        if raw_url.startswith("/"):
            raw_url = f"https://www.jumia.com.eg{raw_url}"
        sku_match = re.search(r"-(\d+)\.html", raw_url)
        sku = sku_match.group(1) if sku_match else str(abs(hash(raw_url)))[:8]

        title_el = prd.select_one(".name")
        curr_el = prd.select_one(".prc")
        old_el = prd.select_one(".old")

        title = title_el.get_text(strip=True) if title_el else ""
        curr_price = float(re.sub(r"[^\d.]", "", curr_el.get_text(strip=True))) if curr_el else 0.0
        orig_price = float(re.sub(r"[^\d.]", "", old_el.get_text(strip=True))) if old_el else curr_price

        deals.append({
            "id": f"jumia_{sku}",
            "store": StoreEnum.JUMIA_EG,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": round(((orig_price - curr_price) / orig_price) * 100, 1) if orig_price > curr_price else 0.0,
            "url": canonicalize_url(raw_url),
        })
    return deals


def parse_btech_snippet(html_content: str) -> List[dict]:
    """Extracts deals from B.Tech HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    for item in soup.select(".product-item"):
        item_id = item.get("data-id", "")
        link_el = item.select_one("a.product-item-link")
        if not link_el:
            continue
        title = link_el.get_text(strip=True)
        raw_url = link_el.get("href", "")

        sp_el = item.select_one(".special-price")
        old_el = item.select_one(".old-price")
        mini_el = item.select_one(".minicash-badge")

        curr_price = float(re.sub(r"[^\d.]", "", sp_el.get_text(strip=True))) if sp_el else 0.0
        orig_price = float(re.sub(r"[^\d.]", "", old_el.get_text(strip=True))) if old_el else curr_price

        deals.append({
            "id": f"btech_{item_id}",
            "store": StoreEnum.BTECH,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": round(((orig_price - curr_price) / orig_price) * 100, 1) if orig_price > curr_price else 0.0,
            "url": canonicalize_url(raw_url),
            "installment_info": mini_el.get_text(strip=True) if mini_el else None,
        })
    return deals


def parse_twob_snippet(html_content: str) -> List[dict]:
    """Extracts deals from 2B Egypt HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    deals = []
    for item in soup.select(".product-item"):
        item_id = item.get("data-id", "")
        link_el = item.select_one("a.product-item-link")
        if not link_el:
            continue
        title = link_el.get_text(strip=True)
        raw_url = link_el.get("href", "")

        sp_el = item.select_one(".special-price .price")
        old_el = item.select_one(".old-price .price")

        curr_price = float(re.sub(r"[^\d.]", "", sp_el.get_text(strip=True))) if sp_el else 0.0
        orig_price = float(re.sub(r"[^\d.]", "", old_el.get_text(strip=True))) if old_el else curr_price

        deals.append({
            "id": f"twob_{item_id}",
            "store": StoreEnum.TWO_B,
            "title": title,
            "original_price": orig_price,
            "discount_price": curr_price,
            "discount_percentage": round(((orig_price - curr_price) / orig_price) * 100, 1) if orig_price > curr_price else 0.0,
            "url": canonicalize_url(raw_url),
        })
    return deals


# ============================================================================
# 3. MOCK TELEGRAM BOT & MESSAGE RECORDER
# ============================================================================

@dataclass
class MockInlineKeyboardButton:
    text: str
    url: Optional[str] = None
    callback_data: Optional[str] = None


@dataclass
class MockInlineKeyboardMarkup:
    inline_keyboard: List[List[MockInlineKeyboardButton]] = field(default_factory=list)


@dataclass
class MockTelegramMessage:
    message_id: int
    chat_id: str
    text: str
    parse_mode: str
    reply_markup: Optional[MockInlineKeyboardMarkup] = None
    disable_web_page_preview: bool = False
    sent_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class MockTelegramBot:
    """Mock Telegram Bot client recording all sent messages for verification."""
    def __init__(self, token: str = "9060276835:AAELf_C59rVRPqWQhFPIotBEpVEVJM3FLuI"):
        self.token = token
        self.sent_messages: List[MockTelegramMessage] = []
        self._next_id = 1001

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[MockInlineKeyboardMarkup] = None,
        disable_web_page_preview: bool = False,
        **kwargs
    ) -> MockTelegramMessage:
        msg = MockTelegramMessage(
            message_id=self._next_id,
            chat_id=str(chat_id),
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
        self._next_id += 1
        self.sent_messages.append(msg)
        return msg

    def clear(self):
        self.sent_messages.clear()

    def get_dispatched(self, chat_id: Optional[str] = None) -> List[MockTelegramMessage]:
        if chat_id is not None:
            return [m for m in self.sent_messages if m.chat_id == str(chat_id)]
        return list(self.sent_messages)

    def last_message(self, chat_id: Optional[str] = None) -> Optional[MockTelegramMessage]:
        msgs = self.get_dispatched(chat_id)
        return msgs[-1] if msgs else None


# ============================================================================
# 4. TELEGRAM HTML FORMATTER (REFERENCE & CONTRACT)
# ============================================================================

def html_escape(text: str) -> str:
    """Crash-proof Telegram HTML escaping for special characters."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_deal_telegram(deal: Deal) -> Tuple[str, MockInlineKeyboardMarkup]:
    """
    Renders Telegram deal message in safe HTML mode with inline order button.
    Ensures #Laptop tag is included for laptop deals.
    """
    title_esc = html_escape(deal.title)
    store_esc = html_escape(deal.store.value if hasattr(deal.store, "value") else str(deal.store))
    category_esc = html_escape(deal.category.value if hasattr(deal.category, "value") else str(deal.category))

    lines = []
    if deal.is_laptop or deal.category == CategoryEnum.LAPTOPS:
        # Dedicated Laptop Template
        lines.append("💻 <b>تنبيه صفقات اللابتوب #Laptop #لابتوب</b> ⚡")
        lines.append("")
        lines.append(f"🏷️ <b>{title_esc}</b>")
        lines.append(f"🏪 المتجر: <b>{store_esc}</b> | الفئة: <b>#Laptop</b>")
        lines.append("")
        lines.append(f"💵 السعر الفعلي: <b>{deal.discount_price:,.2f} ج.م</b> <s>{deal.original_price:,.2f} ج.م</s>")
        lines.append(f"📉 نسبة الخصم: <b>{deal.discount_percentage:.0f}%</b> (توفير <b>{deal.discount_amount:,.2f} ج.م</b>)")
        if deal.installment_info:
            lines.append(f"💳 التقسيط: <i>{html_escape(deal.installment_info)}</i>")
        if deal.coupon_code:
            lines.append(f"🎟️ كوبون الخصم: <code>{html_escape(deal.coupon_code)}</code>")
        lines.append("")
        lines.append(f"🔗 <b>رابط الشراء المباشر:</b> <a href=\"{deal.url}\">اضغط هنا لطلب اللابتوب فوراً</a>")

        keyboard = MockInlineKeyboardMarkup(inline_keyboard=[
            [MockInlineKeyboardButton(text="🛒 شراء اللابتوب الآن ↗", url=deal.url)],
            [MockInlineKeyboardButton(text="💻 كافة عروض اللابتوبات", callback_data="laptop_check")]
        ])
    else:
        # Household / Diapers / Clothing Template
        lines.append(f"🚨 <b>تنبيه صفقة جديدة!</b> <i>(خصم {deal.discount_percentage:.0f}%)</i>")
        lines.append("")
        lines.append(f"🏷️ <b>{title_esc}</b>")
        lines.append(f"🏪 المتجر: <b>{store_esc}</b> | القسم: <b>{category_esc}</b>")
        lines.append("")
        lines.append(f"💵 السعر الحالي: <b>{deal.discount_price:,.2f} ج.م</b> <s>{deal.original_price:,.2f} ج.م</s>")
        lines.append(f"🔥 التوفير: <b>{deal.discount_amount:,.2f} ج.م</b> (خصم {deal.discount_percentage:.0f}%)")
        if deal.coupon_code:
            lines.append(f"🎟️ كوبون إضافي: <code>{html_escape(deal.coupon_code)}</code>")
        if deal.installment_info:
            lines.append(f"💳 التقسيط: <i>{html_escape(deal.installment_info)}</i>")
        lines.append("")
        lines.append("⚡ <i>عروض الجمعة والصفقات الحقيقية في مصر</i>")

        keyboard = MockInlineKeyboardMarkup(inline_keyboard=[
            [MockInlineKeyboardButton(text="🛒 اطلب مباشرة الآن ↗", url=deal.url)],
            [MockInlineKeyboardButton(text="📱 فتح رادار الصفقات", callback_data="open_deals")]
        ])

    message_text = "\n".join(lines)
    return message_text, keyboard


# ============================================================================
# 5. DATABASE SERVICE CONTRACT HARNESS / FALLBACK
# ============================================================================

class FallbackDatabaseService:
    """
    Contract-accurate SQLite database service implementing the stateful deduplication
    engine specified in PROJECT.md and spec_miner_requirements/handoff.md.
    Used for testing when database.db_service is imported or as dynamic fallback.
    """
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.execute("""
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
                deal_hash TEXT NOT NULL,
                last_notified_price REAL,
                last_notified_at TIMESTAMP,
                last_updated TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_id TEXT NOT NULL,
                price REAL NOT NULL,
                recorded_at TIMESTAMP NOT NULL,
                FOREIGN KEY(deal_id) REFERENCES deals(id)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id TEXT PRIMARY KEY,
                topic TEXT,
                subscribed_at TIMESTAMP
            );
        """)
        self.conn.commit()

    def process_and_deduplicate(self, deal: Deal) -> Tuple[bool, str]:
        """
        Deduplication Decision Rules:
        - If not in DB -> ALERT ('NEW_DEAL'), record notified price & timestamp
        - If in DB & unchanged price/coupon -> SUPPRESS ('UNCHANGED_SUPPRESSED')
        - If in DB & laptop with unchanged price -> SUPPRESS ('UNCHANGED_SUPPRESSED')
        - If in DB & price drop >= 5% vs last_notified_price:
            * check cooldown: if last_notified < 60 min ago, requires >= 10% drop
            * if passes cooldown -> ALERT ('PRICE_DROP_5PCT'), update last_notified
            * else -> SUPPRESS ('COOLDOWN_ACTIVE')
        - If in DB & price drop < 5% or price increase -> SUPPRESS ('PRICE_INCREASE_OR_MINOR_DROP')
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, discount_price, deal_hash, last_notified_price, last_notified_at, is_special_laptop FROM deals WHERE id = ?",
            (deal.id,)
        )
        row = cursor.fetchone()
        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()

        if not row:
            # Case A: Brand New Deal -> Alert
            cursor.execute("""
                INSERT INTO deals (
                    id, title, store, category, original_price, discount_price,
                    discount_percentage, url, image_url, is_flash_sale, is_special_laptop,
                    coupon_code, installment_info, deal_hash, last_notified_price,
                    last_notified_at, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deal.id, deal.title,
                deal.store.value if hasattr(deal.store, "value") else str(deal.store),
                deal.category.value if hasattr(deal.category, "value") else str(deal.category),
                deal.original_price, deal.discount_price, deal.discount_percentage,
                deal.url, deal.image_url, 1 if deal.is_flash_sale else 0,
                1 if deal.is_laptop else 0, deal.coupon_code, deal.installment_info,
                deal.deal_hash or deal.compute_hash(), deal.discount_price, now_iso, now_iso
            ))
            cursor.execute("INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                           (deal.id, deal.discount_price, now_iso))
            self.conn.commit()
            return True, "NEW_DEAL"

        prev_price = float(row["discount_price"])
        prev_hash = row["deal_hash"]
        last_notified_price = float(row["last_notified_price"] or prev_price)
        last_notified_at_raw = row["last_notified_at"]
        current_hash = deal.deal_hash or deal.compute_hash()

        # Case B & C: Unchanged price or unchanged hash
        if current_hash == prev_hash or deal.discount_price == prev_price:
            cursor.execute("UPDATE deals SET last_updated = ? WHERE id = ?", (now_iso, deal.id))
            self.conn.commit()
            return False, "UNCHANGED_SUPPRESSED"

        # Case D: Significant Price Drop (>= 5% vs last_notified_price)
        price_drop_pct = ((last_notified_price - deal.discount_price) / last_notified_price) * 100.0

        if price_drop_pct >= 5.0:
            # Check cooldown: minimum 60 minutes between alerts unless drop >= 10%
            if last_notified_at_raw and price_drop_pct < 10.0:
                try:
                    last_notified_dt = datetime.datetime.fromisoformat(last_notified_at_raw)
                    minutes_since_alert = (now - last_notified_dt).total_seconds() / 60.0
                    if minutes_since_alert < 60.0:
                        # Cooldown active
                        cursor.execute("""
                            UPDATE deals SET discount_price = ?, deal_hash = ?, last_updated = ? WHERE id = ?
                        """, (deal.discount_price, current_hash, now_iso, deal.id))
                        cursor.execute("INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                                       (deal.id, deal.discount_price, now_iso))
                        self.conn.commit()
                        return False, "COOLDOWN_ACTIVE"
                except Exception:
                    pass

            # Eligible for re-alert!
            cursor.execute("""
                UPDATE deals SET discount_price = ?, deal_hash = ?, last_notified_price = ?, last_notified_at = ?, last_updated = ?
                WHERE id = ?
            """, (deal.discount_price, current_hash, deal.discount_price, now_iso, now_iso, deal.id))
            cursor.execute("INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                           (deal.id, deal.discount_price, now_iso))
            self.conn.commit()
            return True, "PRICE_DROP_5PCT"

        # Minor drop (< 5%) or price increase -> Update silently
        cursor.execute("""
            UPDATE deals SET discount_price = ?, deal_hash = ?, last_updated = ? WHERE id = ?
        """, (deal.discount_price, current_hash, now_iso, deal.id))
        cursor.execute("INSERT INTO price_history (deal_id, price, recorded_at) VALUES (?, ?, ?)",
                       (deal.id, deal.discount_price, now_iso))
        self.conn.commit()
        return False, "PRICE_INCREASE_OR_MINOR_DROP"

    def save_deal(self, deal: Deal):
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO deals (
                id, title, store, category, original_price, discount_price,
                discount_percentage, url, image_url, is_flash_sale, is_special_laptop,
                coupon_code, installment_info, deal_hash, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            deal.id, deal.title,
            deal.store.value if hasattr(deal.store, "value") else str(deal.store),
            deal.category.value if hasattr(deal.category, "value") else str(deal.category),
            deal.original_price, deal.discount_price, deal.discount_percentage,
            deal.url, deal.image_url, 1 if deal.is_flash_sale else 0,
            1 if deal.is_laptop else 0, deal.coupon_code, deal.installment_info,
            deal.deal_hash or deal.compute_hash(), now_iso
        ))
        self.conn.commit()

    def get_all_deals(self, category: Optional[str] = None) -> List[Deal]:
        cursor = self.conn.cursor()
        if category:
            cursor.execute("SELECT * FROM deals WHERE category = ?", (category,))
        else:
            cursor.execute("SELECT * FROM deals")
        rows = cursor.fetchall()
        deals = []
        for r in rows:
            deals.append(Deal.from_dict(dict(r)))
        return deals

    def get_active_laptops(self) -> List[Deal]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM deals WHERE is_special_laptop = 1 OR category = ?", (CategoryEnum.LAPTOPS.value,))
        rows = cursor.fetchall()
        return [Deal.from_dict(dict(r)) for r in rows]

    def add_subscriber(self, chat_id: str, topic: Optional[str] = None):
        cursor = self.conn.cursor()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("INSERT OR REPLACE INTO subscribers (chat_id, topic, subscribed_at) VALUES (?, ?, ?)",
                       (str(chat_id), topic, now_iso))
        self.conn.commit()

    def get_subscribers(self, topic: Optional[str] = None) -> List[str]:
        cursor = self.conn.cursor()
        if topic:
            cursor.execute("SELECT chat_id FROM subscribers WHERE topic = ? OR topic IS NULL", (topic,))
        else:
            cursor.execute("SELECT chat_id FROM subscribers")
        rows = cursor.fetchall()
        return [r["chat_id"] for r in rows]

    def close(self):
        self.conn.close()


def get_db_service(db_path: Optional[str] = None):
    """
    Returns an instance of DatabaseService.
    Prefers real database.db_service.DatabaseService if implemented and available;
    otherwise uses FallbackDatabaseService.
    Uses a temporary file for isolated test state when db_path is None or ':memory:'.
    """
    import tempfile
    if db_path is None or db_path == ":memory:":
        temp_file = tempfile.NamedTemporaryFile(suffix=".test_deals.db", delete=False)
        temp_file.close()
        target_path = temp_file.name
    else:
        target_path = db_path

    try:
        from database.db_service import DatabaseService
        return DatabaseService(db_path=target_path)
    except (ImportError, AttributeError):
        return FallbackDatabaseService(db_path=target_path)
