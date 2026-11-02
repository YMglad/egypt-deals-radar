import os
import json
import asyncio
import requests
from scraper import scrape_all_deals
from core.models import CategoryEnum

BOT_TOKEN = os.getenv("BOT_TOKEN", "9060276835:AAELf_C59rVRPqWQhFPIotBEpVEVJM3FLuI")
PRIMARY_CHAT_ID = "628511175"
DEALS_FILE = "deals.json"


def get_registered_chat_ids():
    """Fetches chat IDs from Telegram getUpdates or local cache, always ensuring primary user is included."""
    chat_ids = {PRIMARY_CHAT_ID}
    if os.getenv("CHAT_ID"):
        chat_ids.add(str(os.getenv("CHAT_ID")))

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("result", []):
                if "message" in item and "chat" in item["message"]:
                    chat_ids.add(str(item["message"]["chat"]["id"]))
    except Exception as e:
        print(f"Error fetching chat IDs from getUpdates: {e}")

    # Fallback to chat_ids.json
    if os.path.exists("chat_ids.json"):
        try:
            with open("chat_ids.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
                chat_ids.update([str(x) for x in saved])
        except Exception:
            pass

    # Save back
    try:
        with open("chat_ids.json", "w", encoding="utf-8") as f:
            json.dump(list(chat_ids), f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return list(chat_ids)


def send_telegram_alert(chat_id, deal):
    """Sends a formatted deal alert to the user's Telegram with direct clickable order URL."""
    cat_str = str(deal.get("category", "")).lower()

    if deal.get("is_special_laptop"):
        alert_header = "💻 **#Laptop - تنبيه سعر لابتوب ASUS ROG Strix 18!**"
    elif "حفاضات" in deal.get("category", "") or "diaper" in cat_str or "baby" in cat_str or "أطفال" in deal.get("category", ""):
        alert_header = "👶 **تنبيه عروض وتوفير مستلزمات وحفاضات الأطفال!**"
    elif "ملابس" in deal.get("category", "") or "clothing" in cat_str or "أزياء" in deal.get("category", ""):
        alert_header = "👕 **تنبيه عروض أزياء وملابس الأسرة والأطفال!**"
    elif "بقالة" in deal.get("category", "") or "groceries" in cat_str or "household" in cat_str:
        alert_header = "🛒 **تنبيه صفقات السوبرماركت ومستلزمات البيت!**"
    elif deal.get("is_flash_sale"):
        alert_header = "🚨 **صفقة فلاش سيل عاجلة - Black Friday!**"
    else:
        alert_header = "📢 **صفقة حقيقية جديدة الآن في مصر!**"

    msg = (
        f"{alert_header}\n\n"
        f"🏷️ **{deal['title']}**\n"
        f"🏪 المتجر: **{deal['store']}** | القسم: {deal.get('category', '')}\n"
        f"💵 السعر الآن: **{deal['discount_price']:,.0f} ج.م** "
        f"~~({deal['original_price']:,.0f} ج.م)~~\n"
        f"🔥 نسبة الخصم الفعلي: **{deal['discount_percentage']}%**\n"
    )
    if deal.get("coupon_code"):
        msg += f"🎟️ كود إضافي: `{deal['coupon_code']}`\n"
    if deal.get("installment_info"):
        msg += f"💳 التقسيط: {deal['installment_info']}\n"

    prod_url = deal.get("url")
    if not prod_url or not prod_url.startswith("http"):
        prod_url = "https://www.amazon.eg/"

    keyboard = {
        "inline_keyboard": [
            [{"text": "🛒 اطلب الآن مباشرة ↗", "url": prod_url}],
            [{"text": "📱 افتح تطبيق رادار الصفقات", "url": "https://ymglad.github.io/egypt-deals-radar/"}]
        ]
    }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": "Markdown",
        "reply_markup": keyboard,
        "disable_web_page_preview": False
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"Notification sent to {chat_id}: status {r.status_code}")
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")


async def main():
    print("Starting Cloud Deals Scanner...")
    prev_deals = {}
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE, "r", encoding="utf-8") as f:
                for d in json.load(f):
                    prev_deals[d["id"]] = d
        except Exception:
            pass

    # Scrape fresh deals across all 9 stores
    new_deals = await scrape_all_deals()
    print(f"Scraped {len(new_deals)} deals across all platforms.")

    chat_ids = get_registered_chat_ids()
    print(f"Target Telegram Chat IDs: {chat_ids}")

    # Detect hot deals and broadcast
    for deal in new_deals:
        deal_id = deal["id"]
        is_new = deal_id not in prev_deals
        is_price_drop = False
        if not is_new and deal["discount_price"] < prev_deals[deal_id]["discount_price"] * 0.95:
            is_price_drop = True

        cat_str = str(deal.get("category", "")).lower()
        is_laptop = (
            cat_str == "laptops" or
            cat_str == CategoryEnum.LAPTOPS.value.lower() or
            "laptop" in cat_str
        )

        # ISOLATION: Normal laptops do NOT send periodic broadcasts
        if is_laptop and not deal.get("is_special_laptop"):
            continue

        # Send alert if new deal or price drop >= 5% or special laptop
        if is_new or is_price_drop:
            for cid in chat_ids:
                send_telegram_alert(cid, deal)
                await asyncio.sleep(0.3)

    # Save updated list to deals.json
    with open(DEALS_FILE, "w", encoding="utf-8") as f:
        json.dump([d if isinstance(d, dict) else d.to_dict() for d in new_deals], f, ensure_ascii=False, indent=2)
    print("Updated deals.json successfully.")


if __name__ == "__main__":
    asyncio.run(main())
