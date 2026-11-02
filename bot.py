import os
import asyncio
import logging
from typing import Optional
from dotenv import load_dotenv

# FastAPI for serving the Telegram Mini App & API
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

# Telegram Bot
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Internal modules
from database import (
    init_db,
    save_or_update_deal,
    get_all_deals,
    get_laptop_deals,
    add_subscriber,
    get_subscribers,
)
from scraper import scrape_all_deals
from core.models import CategoryEnum

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "9060276835:AAELf_C59rVRPqWQhFPIotBEpVEVJM3FLuI")
PRIMARY_CHAT_ID = os.getenv("CHAT_ID", "628511175")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://ymglad.github.io/egypt-deals-radar/")

# 90 seconds interval (1.5 minutes) for rapid real-time deal alerts
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "90"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BlackFridayBot")

init_db()
# Ensure primary chat is enrolled immediately
add_subscriber(PRIMARY_CHAT_ID)

app = FastAPI(title="Egypt Black Friday Deals Radar")

webapp_dir = os.path.join(os.path.dirname(__file__), "webapp")
if os.path.exists(webapp_dir):
    app.mount("/static", StaticFiles(directory=webapp_dir), name="static")


@app.get("/")
async def serve_webapp():
    index_file = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Deals Tracker API Running"}


@app.get("/api/deals")
async def api_get_deals(store: Optional[str] = None, category: Optional[str] = None):
    deals = get_all_deals(category=category, store=store, min_discount=0)
    return JSONResponse(deals)


@app.get("/api/laptop")
async def api_get_laptop():
    laptops = get_laptop_deals()
    return JSONResponse(laptops)


@app.get("/health")
async def health_check():
    return {"status": "ok", "scan_interval": SCAN_INTERVAL_SECONDS}


# --- Telegram Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    logger.info(f"User started bot: {chat_id}")
    
    # Store subscriber persistently without overwriting other users
    add_subscriber(chat_id)
        
    welcome_text = (
        "👋 **أهلاً بك في رادار عروض البلاك فرايدي مصر 2026!**\n\n"
        "⚡ **النظام يعمل الآن بتحديث فوري كل 1–2 دقيقة على هاتفك مباشرة!**\n\n"
        "🛒 **الأقسام المشمولة:**\n"
        "• 👶 **حفاضات الأطفال ومستلزمات البيبي** (Pampers, Molfix, Fine Baby, Bebem)\n"
        "• 👕 **ملابس الأطفال وأزياء الرضع**\n"
        "• 👗 **ملابس الكبار والصغار** (قطونيل، ديفاكتو، وماركات كبرى)\n"
        "• 🏠 **مستلزمات البيت والبقالة والأجهزة** (بريدفاست، طلبات مارت، أمازون، نون، كارفور، جوميا، فاليو، وبي تك)\n"
        "• 💻 **#Laptop - قسم خاص ومستقل للابتوب ASUS ROG Strix 18**\n\n"
        "📱 **ستصلك التنبيهات فوراً مع روابط طلب مباشرة لشراء المنتج بنقرة واحدة!**"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔥 افتح رادار الصفقات على الموبايل", web_app=WebAppInfo(url=WEBAPP_URL))],
        [
            InlineKeyboardButton("💻 فحص لابتوب ROG Strix 18", callback_data="laptop_check"),
            InlineKeyboardButton("⚡ فحص العروض فوراً", callback_data="scan_now")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)


async def laptop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    laptops = get_laptop_deals()
    if not laptops:
        await update.message.reply_text("جاري استخراج بيانات ASUS ROG Strix 18 من 2B وDream2000 وNoon...")
        return
        
    msg = "💻 **#Laptop - موقف أسعار ASUS ROG Strix 18 اللحظي في مصر:**\n\n"
    for l in laptops[:2]:
        msg += (
            f"🔹 **{l['title']}**\n"
            f"🏪 المتجر: **{l['store']}**\n"
            f"💰 السعر الفعلي: **{l['discount_price']:,.0f} ج.م**\n"
            f"📉 الخصم: {l['discount_percentage']}%\n"
            f"💳 ملاحظة: {l.get('installment_info', '')}\n"
            f"🔗 [رابط الشراء المباشر]({l['url']})\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔎 جاري فحص كافة المتاجر والتطبيقات الآن (Amazon, Noon, Breadfast, Talabat, Carrefour, Jumia, ValU, B.Tech, 2B)...")
    deals = await scrape_all_deals()
    for deal in deals:
        save_or_update_deal(deal)
        
    msg = f"✅ تم الفحص! تم رصد {len(deals)} عرضاً حقيقياً الآن في مختلف الفئات:\n\n"
    for d in deals[:4]:
        tag = "#Laptop 💻" if d.get("is_special_laptop") else f"🏷️ {d.get('category', 'عرض')}"
        msg += (
            f"{tag}\n"
            f"**{d['title']}**\n"
            f"🏪 {d['store']} | خصم **{d['discount_percentage']}%**\n"
            f"💵 السعر: **{d['discount_price']:,.0f} ج.م** ~~({d['original_price']:,.0f} ج.م)~~\n"
            f"🔗 [اطلب مباشرة من هنا]({d['url']})\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=False)


async def check_deals_periodic(bot):
    """
    Background worker: scans every 90 seconds and sends new deals / flash sales
    directly to all subscribed users on Telegram with a direct order button.
    """
    logger.info(f"Starting periodic deals checker every {SCAN_INTERVAL_SECONDS} seconds...")
    add_subscriber(PRIMARY_CHAT_ID)
    
    while True:
        try:
            logger.info("Executing periodic scan across all Egyptian retail platforms...")
            new_deals = await scrape_all_deals()
            
            # Fetch all subscribers and ensure primary user is always included
            subscribers = set(get_subscribers())
            subscribers.add(PRIMARY_CHAT_ID)
            if os.getenv("CHAT_ID"):
                subscribers.add(str(os.getenv("CHAT_ID")))
                
            for deal in new_deals:
                is_alert = save_or_update_deal(deal)
                if not is_alert:
                    continue
                    
                cat_str = str(deal.get("category", "")).lower()
                is_laptop = (
                    cat_str == "laptops" or 
                    cat_str == CategoryEnum.LAPTOPS.value.lower() or 
                    "laptop" in cat_str
                )
                
                # ISOLATION: Standard general laptops do not flood periodic alerts.
                # Only the special ASUS ROG Strix 18 alerts if price changed.
                if is_laptop and not deal.get("is_special_laptop"):
                    continue
                    
                # Determine appropriate Arabic banner
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
                    f"💵 السعر الفعلي: **{deal['discount_price']:,.0f} ج.م** "
                    f"~~({deal['original_price']:,.0f} ج.م)~~\n"
                    f"🔥 نسبة الخصم: **{deal['discount_percentage']}%**\n"
                )
                if deal.get("coupon_code"):
                    msg += f"🎟️ كود الخصم: `{deal['coupon_code']}`\n"
                if deal.get("installment_info"):
                    msg += f"💳 التقسيط: {deal['installment_info']}\n"
                    
                prod_url = deal.get("url")
                if not prod_url or not prod_url.startswith("http"):
                    prod_url = "https://www.amazon.eg/"
                    
                keyboard = [[InlineKeyboardButton("🛒 اطلب الآن مباشرة ↗", url=prod_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                for target_chat in subscribers:
                    try:
                        await bot.send_message(
                            chat_id=target_chat,
                            text=msg,
                            parse_mode="Markdown",
                            reply_markup=reply_markup,
                            disable_web_page_preview=False
                        )
                        logger.info(f"Telegram notification sent to {target_chat} for: {deal['title']}")
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.error(f"Failed to send Telegram message to {target_chat}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in scan cycle: {e}")
            
        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


async def main():
    bot_app = None
    if BOT_TOKEN:
        bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
        bot_app.add_handler(CommandHandler("start", start_command))
        bot_app.add_handler(CommandHandler("laptop", laptop_command))
        bot_app.add_handler(CommandHandler("deals", scan_command))
        bot_app.add_handler(CommandHandler("scan", scan_command))
        await bot_app.initialize()
        await bot_app.start()
        await bot_app.updater.start_polling()
        logger.info("Telegram Bot connected and listening.")
        
        asyncio.create_task(check_deals_periodic(bot_app.bot))
    else:
        logger.warning("BOT_TOKEN is not set.")

    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
