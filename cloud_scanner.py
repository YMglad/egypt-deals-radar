import os
import json
import asyncio
import requests
from scraper import scrape_all_deals

BOT_TOKEN = os.getenv("BOT_TOKEN", "9060276835:AAELf_C59rVRPqWQhFPIotBEpVEVJM3FLuI")
DEALS_FILE = "deals.json"

def get_registered_chat_ids():
    """Fetches chat IDs from Telegram getUpdates or local cache."""
    chat_ids = set()
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("result", []):
                if "message" in item and "chat" in item["message"]:
                    chat_ids.add(str(item["message"]["chat"]["id"]))
    except Exception as e:
        print(f"Error fetching chat IDs: {e}")

    # Fallback to chat_ids.json
    if os.path.exists("chat_ids.json"):
        try:
            with open("chat_ids.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
                chat_ids.update(saved)
        except Exception:
            pass

    # Save back
    if chat_ids:
        with open("chat_ids.json", "w", encoding="utf-8") as f:
            json.dump(list(chat_ids), f)
            
    return list(chat_ids)

def send_telegram_alert(chat_id, deal):
    """Sends a formatted deal alert to the user's Telegram."""
    alert_header = "🚨 **تنبيه فلاش سيل عاجل!**" if deal.get("is_flash_sale") else "📢 **صفقة حقيقية قوية!**"
    if deal.get("is_special_laptop"):
        alert_header = "⭐ **تنبيه لابتوب طلبك الخاص (ASUS ROG Strix 18)!**"

    msg = (
        f"{alert_header}\n\n"
        f"🏷️ **{deal['title']}**\n"
        f"🏪 المتجر: **{deal['store']}** | القسم: {deal.get('category', '')}\n"
        f"💵 السعر الآن: **{deal['discount_price']:,.0f} ج.م** "
        f"~~({deal['original_price']:,.0f} ج.م)~~\n"
        f"🔥 نسبة الخصم: **{deal['discount_percentage']}%**\n"
    )
    if deal.get("coupon_code"):
        msg += f"🎟️ كود إضافي: `{deal['coupon_code']}`\n"
    if deal.get("installment_info"):
        msg += f"💳 التقسيط: {deal['installment_info']}\n"

    keyboard = {
        "inline_keyboard": [
            [{"text": "🛒 اشتري الآن والحق العرض ↗", "url": deal["url"]}],
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
    # Load previously seen deals
    prev_deals = {}
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE, "r", encoding="utf-8") as f:
                for d in json.load(f):
                    prev_deals[d["id"]] = d
        except Exception:
            pass

    # Scrape fresh deals
    new_deals = await scrape_all_deals()
    print(f"Scraped {len(new_deals)} deals across all platforms.")

    chat_ids = get_registered_chat_ids()
    print(f"Target Telegram Chat IDs: {chat_ids}")

    # Detect hot deals and send alerts
    for deal in new_deals:
        deal_id = deal["id"]
        is_new = deal_id not in prev_deals
        is_price_drop = False
        if not is_new and deal["discount_price"] < prev_deals[deal_id]["discount_price"] * 0.95:
            is_price_drop = True

        # Alert if new deal >= 40% discount OR ASUS ROG Strix 18
        if (is_new or is_price_drop) and (deal.get("discount_percentage", 0) >= 40 or deal.get("is_special_laptop")):
            for cid in chat_ids:
                send_telegram_alert(cid, deal)

    # Save to deals.json
    with open(DEALS_FILE, "w", encoding="utf-8") as f:
        json.dump(new_deals, f, ensure_ascii=False, indent=2)
    print("Updated deals.json successfully.")

if __name__ == "__main__":
    asyncio.run(main())
