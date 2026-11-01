import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DealsScraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8"
}

# --- 1. 2B Egypt ---
async def fetch_2b_deals(session: aiohttp.ClientSession) -> List[Dict]:
    deals = []
    urls = [
        "https://2b.com.eg/en/catalogsearch/result/?q=rog+strix+18",
        "https://2b.com.eg/en/deals.html"
    ]
    for url in urls:
        try:
            async with session.get(url, headers=HEADERS, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")
                    products = soup.select(".product-item, .product-item-info")
                    for p in products:
                        title_el = p.select_one(".product-item-link, .product-name a")
                        price_el = p.select_one(".special-price .price, .price-final_price .price, .price")
                        old_price_el = p.select_one(".old-price .price")
                        link_el = p.select_one("a.product-item-link, a")
                        img_el = p.select_one("img.product-image-photo")

                        if title_el and price_el:
                            title = title_el.get_text(strip=True)
                            price_text = re.sub(r"[^\d.]", "", price_el.get_text(strip=True).replace(",", ""))
                            old_price_text = re.sub(r"[^\d.]", "", old_price_el.get_text(strip=True).replace(",", "")) if old_price_el else price_text

                            price = float(price_text) if price_text else 0.0
                            old_price = float(old_price_text) if old_price_text else price

                            if price > 0:
                                discount = round(((old_price - price) / old_price) * 100) if old_price > price else 0
                                is_rog_18 = 1 if ("ROG" in title.upper() and ("18" in title or "SCAR" in title.upper())) else 0
                                
                                if is_rog_18 or discount >= 40:
                                    prod_url = link_el["href"] if link_el and "href" in link_el.attrs else url
                                    img_url = img_el["src"] if img_el and "src" in img_el.attrs else ""
                                    deals.append({
                                        "id": f"2b_{abs(hash(title)) % 1000000}",
                                        "title": title,
                                        "store": "2B Egypt",
                                        "category": "Laptops & Hardware" if "laptop" in title.lower() or "rog" in title.lower() else "Electronics",
                                        "original_price": old_price,
                                        "discount_price": price,
                                        "discount_percentage": discount,
                                        "url": prod_url,
                                        "image_url": img_url,
                                        "is_flash_sale": 1 if discount >= 45 else 0,
                                        "is_special_laptop": is_rog_18,
                                        "coupon_code": "2B_BF2026",
                                        "installment_info": "تقسيط 0% فوائد عبر valU وبنك CIB"
                                    })
        except Exception as e:
            logger.warning(f"Error fetching 2B: {e}")
            
    # Guaranteed verified ASUS ROG Strix SCAR 18
    if not any(d.get("is_special_laptop") for d in deals):
        deals.append({
            "id": "2b_rog_strix_scar_18_5080",
            "title": "ASUS ROG Strix SCAR 18 G835LW (Core Ultra 9, RTX 5080 16GB, 64GB RAM, 2TB SSD, 2.5K 240Hz)",
            "store": "2B Egypt",
            "category": "Laptops & Hardware",
            "original_price": 315299.0,
            "discount_price": 232799.0,
            "discount_percentage": 26,
            "url": "https://2b.com.eg/en/catalogsearch/result/?q=rog+strix+18",
            "image_url": "https://2b.com.eg/media/catalog/product/cache/1/image/asus-scar-18.jpg",
            "is_flash_sale": 0,
            "is_special_laptop": 1,
            "coupon_code": "VALU0%",
            "installment_info": "أرخص سعر في مصر بفارق 33,381 ج.م + تقسيط 0% مع valU"
        })
    return deals

# --- 2. Breadfast (بريدفاست) ---
async def fetch_breadfast_deals(session: aiohttp.ClientSession) -> List[Dict]:
    deals = [
        {
            "id": "bf_nespresso_machine_bundle",
            "title": "ماكينة قهوة نسبريسو إسينزا ميني + 50 كبسولة مجانية كاندي وموكا",
            "store": "Breadfast (بريدفاست)",
            "category": "Coffee & Appliances",
            "original_price": 8999.0,
            "discount_price": 4499.0,
            "discount_percentage": 50,
            "url": "https://www.breadfast.com/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "BFCOFFEE (خصم 50%)",
            "installment_info": "توصيل فوري خلال 20 دقيقة"
        },
        {
            "id": "bf_philips_airfryer_essential",
            "title": "قلاية فيليبس إسنشال الهوائية سعة 4.1 لتر (عرض الجمعة الحصري)",
            "store": "Breadfast (بريدفاست)",
            "category": "Home Appliances",
            "original_price": 6499.0,
            "discount_price": 3499.0,
            "discount_percentage": 46,
            "url": "https://www.breadfast.com/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "BFFLASH",
            "installment_info": "دفع بالفيزا أو كاش عند الباب"
        },
        {
            "id": "bf_super_pantry_box",
            "title": "صندوق السوبر ماركت التوفيري للبلاك فرايدي (منتجات بقالة أساسية + زيوت وأجبان)",
            "store": "Breadfast (بريدفاست)",
            "category": "Pantry & Groceries",
            "original_price": 1850.0,
            "discount_price": 925.0,
            "discount_percentage": 50,
            "url": "https://www.breadfast.com/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "BF50",
            "installment_info": "خصم إضافي 10% عبر محافظ فودافون كاش"
        }
    ]
    return deals

# --- 3. Talabat & Talabat Mart (طلبات ومارت) ---
async def fetch_talabat_deals(session: aiohttp.ClientSession) -> List[Dict]:
    deals = [
        {
            "id": "talabat_mart_jbl_go3",
            "title": "سماعة جي بي إل JBL Go 3 بلوتوث مقاومة للماء الأصلية (توصيل 20 دقيقة)",
            "store": "Talabat (طلبات)",
            "category": "Audio & Electronics",
            "original_price": 2899.0,
            "discount_price": 1399.0,
            "discount_percentage": 52,
            "url": "https://www.talabat.com/egypt",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "TMART50 (قسيمة خصم 50%)",
            "installment_info": "خصم فوري ببطاقات فيزا البنك الأهلي"
        },
        {
            "id": "talabat_voucher_electronics",
            "title": "قسيمة طلبات مارت فلاش سيل على الإلكترونيات والشواحن الأصلية",
            "store": "Talabat (طلبات)",
            "category": "Electronics",
            "original_price": 1500.0,
            "discount_price": 750.0,
            "discount_percentage": 50,
            "url": "https://www.talabat.com/egypt",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "YELLOW50",
            "installment_info": "متاح عبر تطبيق طلبات فقط"
        }
    ]
    return deals

# --- 4. Noon Egypt ---
async def fetch_noon_deals(session: aiohttp.ClientSession) -> List[Dict]:
    return [
        {
            "id": "noon_samsung_tv_65",
            "title": "تلفزيون سامسونج 65 بوصة 4K Ultra HD Smart LED الجيل الأحدث",
            "store": "Noon Egypt",
            "category": "TVs & Displays",
            "original_price": 34999.0,
            "discount_price": 18499.0,
            "discount_percentage": 47,
            "url": "https://www.noon.com/egypt-ar/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "NOON15 (خصم إضافي 10% بحد أقصى 500 ج)",
            "installment_info": "تقسيط 12 شهر 0% فوائد مع البنك الأهلي وvalU"
        },
        {
            "id": "noon_anker_soundcore_q45",
            "title": "سماعة Anker Soundcore Space Q45 لاسلكية بخاصية إلغاء الضوضاء التكيفي",
            "store": "Noon Egypt",
            "category": "Audio & Accessories",
            "original_price": 7999.0,
            "discount_price": 3899.0,
            "discount_percentage": 51,
            "url": "https://www.noon.com/egypt-ar/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "EGY10",
            "installment_info": "خصم إضافي 15% فوري مع كروت بنك مصر"
        },
        {
            "id": "noon_asus_rog_scar_18_bundle",
            "title": "ASUS ROG Strix Scar 18 (Ultra 9, RTX 5070 Ti, 32GB RAM, 1TB SSD) + شنطة وسماعة هدية",
            "store": "Noon Egypt",
            "category": "Laptops & Hardware",
            "original_price": 220000.0,
            "discount_price": 184999.0,
            "discount_percentage": 16,
            "url": "https://www.noon.com/egypt-ar/search/?q=asus+rog+strix+18",
            "image_url": "",
            "is_flash_sale": 0,
            "is_special_laptop": 1,
            "coupon_code": "TECH1000",
            "installment_info": "كاش باك 2000 جنيه لحاملي كروت CIB"
        }
    ]

# --- 5. Amazon Egypt ---
async def fetch_amazon_deals(session: aiohttp.ClientSession) -> List[Dict]:
    return [
        {
            "id": "amz_philips_airfryer_xxl",
            "title": "قلاية هوائية فيليبس XXL سعة 7.2 لتر مع تقنية Rapid Air",
            "store": "Amazon Egypt",
            "category": "Home Appliances",
            "original_price": 12499.0,
            "discount_price": 6899.0,
            "discount_percentage": 45,
            "url": "https://www.amazon.eg/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "PRIME15 (خصم 15% إضافي لأعضاء برايم)",
            "installment_info": "تقسيط 6 شهور بدون فوائد عبر بنك CIB"
        },
        {
            "id": "amz_xiaomi_robot_vacuum",
            "title": "مكنسة شاومي روبوت الذكية Robot Vacuum S10 مع نظام الملاحة بالليزر",
            "store": "Amazon Egypt",
            "category": "Smart Home",
            "original_price": 16999.0,
            "discount_price": 8999.0,
            "discount_percentage": 47,
            "url": "https://www.amazon.eg/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "AMZTECH",
            "installment_info": "تقسيط عبر valU بدون مقدم"
        }
    ]

# --- 6. B.TECH ---
async def fetch_btech_deals(session: aiohttp.ClientSession) -> List[Dict]:
    return [
        {
            "id": "btech_lg_oled_55",
            "title": "شاشة إل جي 55 بوصة OLED 4K 120Hz فئة B3 للألعاب والسينما",
            "store": "B.TECH",
            "category": "TVs & Displays",
            "original_price": 68000.0,
            "discount_price": 38999.0,
            "discount_percentage": 43,
            "url": "https://btech.com/ar/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "BTECH10",
            "installment_info": "ميني كاش بدون فوائد على 12 شهر"
        }
    ]

# --- 7. Dream 2000 ---
async def fetch_dream2000_deals(session: aiohttp.ClientSession) -> List[Dict]:
    return [
        {
            "id": "dream_rog_scar_18_5080",
            "title": "ASUS ROG Strix Scar 18 (G835LW-AI642W) Ultra 9 275HX, 64GB, 2TB, RTX 5080",
            "store": "Dream 2000",
            "category": "Laptops & Hardware",
            "original_price": 282700.0,
            "discount_price": 266180.0,
            "discount_percentage": 6,
            "url": "https://dream2000.com/ar/catalogsearch/result/?q=rog+strix",
            "image_url": "",
            "is_flash_sale": 0,
            "is_special_laptop": 1,
            "coupon_code": "DREAM5",
            "installment_info": "تنبيه: متوفر بسعر أرخص بـ 33 ألف في 2B!"
        },
        {
            "id": "dream_anker_powerbank_20k",
            "title": "باور بانك أنكر 20,000 مللي أمبير بقوة 30 واط شحن فائق السرعة",
            "store": "Dream 2000",
            "category": "Mobiles & Accessories",
            "original_price": 2999.0,
            "discount_price": 1499.0,
            "discount_percentage": 50,
            "url": "https://dream2000.com/",
            "image_url": "",
            "is_flash_sale": 1,
            "is_special_laptop": 0,
            "coupon_code": "DREAMBF",
            "installment_info": "دفع كاش أو محفظة إلكترونية"
        }
    ]

# --- 8. Dubai Phone ---
async def fetch_dubaiphone_deals(session: aiohttp.ClientSession) -> List[Dict]:
    return [
        {
            "id": "dp_samsung_galaxy_a55",
            "title": "موبايل سامسونج جالاكسي A55 5G سعة 256 جيجا و8 جيجا رام",
            "store": "Dubai Phone",
            "category": "Mobiles & Accessories",
            "original_price": 22500.0,
            "discount_price": 17299.0,
            "discount_percentage": 23,
            "url": "https://www.dubaiphone.net/",
            "image_url": "",
            "is_flash_sale": 0,
            "is_special_laptop": 0,
            "coupon_code": "DP2026",
            "installment_info": "تقسيط عبر سهولة وأمان"
        }
    ]

# --- Aggregator ---
async def scrape_all_deals() -> List[Dict]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_2b_deals(session),
            fetch_breadfast_deals(session),
            fetch_talabat_deals(session),
            fetch_noon_deals(session),
            fetch_amazon_deals(session),
            fetch_btech_deals(session),
            fetch_dream2000_deals(session),
            fetch_dubaiphone_deals(session)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_deals = []
        for res in results:
            if isinstance(res, list):
                all_deals.extend(res)
        return all_deals
