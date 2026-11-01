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
from database import init_db, save_or_update_deal, get_all_deals, get_laptop_deals
from scraper import scrape_all_deals

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://egypt-black-friday-bot.onrender.com")

# Interval requested by user: Every 10 minutes (600 seconds)
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "600"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("BlackFridayBot")

# Initialize database
init_db()

# Create FastAPI app
app = FastAPI(title="Egypt Black Friday Deals Radar")

webapp_dir = os.path.join(os.path.dirname(__file__), "webapp")
if os.path.exists(webapp_dir):
    app.mount("/static", StaticFiles(directory=webapp_dir), name="static")

@app.get("/")
async def serve_webapp():
    index_file = os.path.join(webapp_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Deals Tracker API Running"}

@app.get("/app.js")
async def serve_app_js():
    js_file = os.path.join(webapp_dir, "app.js")
    return FileResponse(js_file)

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

# --- Telegram Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"User started bot: {chat_id}")
    
    global CHAT_ID
    CHAT_ID = str(chat_id)
        
    welcome_text = (
        "👋 **أهلاً بك في رادار عروض البلاك فرايدي مصر 2026!**\n\n"
        "⚡ **النظام يعمل الآن بتحديث فوري كل 10 دقائق على هذا الشات مباشرة!**\n\n"
        "🏪 **المواقع والتطبيقات المشمولة في المراقبة:**\n"
        "1. **Noon Egypt** (الجمعة الصفراء والفلاش سيل)\n"
        "2. **Amazon Egypt** (عروض الجمعة البيضاء وبرايم)\n"
        "3. **Breadfast (بريدفاست)** (عروض البقالة، القهوة، والأجهزة)\n"
        "4. **Talabat (طلبات ومارت)** (قسائم خصم 50% وإلكترونيات)\n"
        "5. **2B Egypt** (عروض الهاردوير واللابتوبات)\n"
        "6. **B.TECH** (عروض الأجهزة وميني كاش بدون فوائد)\n"
        "7. **Dream 2000** (الموبايلات والإلكترونيات)\n"
        "8. **Dubai Phone** (الهواتف والإكسسوارات)\n"
        "9. **valU Group** (شراكات التقسيط 0% فوائد ومصاريف)\n\n"
        "⭐ **طلبك الخاص:** تتبع فوري لحظي لأي هبوط في سعر **ASUS ROG Strix 18**!\n\n"
        "📱 **اضغط بالأسفل لفتح التطبيق التفاعلي أو اطلب فحصاً فورياً:**"
    )
    
    app_url = WEBAPP_URL if WEBAPP_URL.startswith("https") else "https://telegram.org"
    
    keyboard = [
        [InlineKeyboardButton("🔥 افتح رادار الصفقات (Mini App)", web_app=WebAppInfo(url=app_url))],
        [
            InlineKeyboardButton("💻 لابتوب ROG Strix 18", callback_data="laptop_check"),
            InlineKeyboardButton("⚡ فحص العروض الآن", callback_data="scan_now")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def laptop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    laptops = get_laptop_deals()
    if not laptops:
        await update.message.reply_text("جاري استخراج بيانات ASUS ROG Strix 18 من 2B وDream2000 وNoon...")
        return
        
    msg = "💻 **موقف أسعار ASUS ROG Strix 18 اللحظي في مصر:**\n\n"
    for l in laptops[:3]:
        msg += (
            f"🔹 **{l['title']}**\n"
            f"🏪 المتجر: **{l['store']}**\n"
            f"💰 السعر الفعلي: **{l['discount_price']:,.0f} ج.م**\n"
            f"📉 الخصم: {l['discount_percentage']}%\n"
            f"💳 التفاصيل: {l.get('installment_info', '')}\n"
            f"🔗 [رابط الشراء المباشر]({l['url']})\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual trigger to scan immediately without waiting 10 minutes."""
    await update.message.reply_text("🔎 جاري فحص كافة المتاجر والتطبيقات الآن (Noon, Amazon, Breadfast, Talabat, 2B, B.TECH)...")
    deals = await scrape_all_deals()
    for deal in deals:
        save_or_update_deal(deal)
        
    hot_deals = [d for d in deals if d.get("discount_percentage", 0) >= 40 or d.get("is_special_laptop")]
    msg = f"✅ تم الفحص! تم رصد {len(hot_deals)} صفقة استثنائية حالياً:\n\n"
    for d in hot_deals[:5]:
        msg += (
            f"🔥 **{d['title']}**\n"
            f"🏪 {d['store']} | خصم **{d['discount_percentage']}%**\n"
            f"💵 السعر: **{d['discount_price']:,.0f} ج.م** ~~({d['original_price']:,.0f} ج.م)~~\n"
            f"🔗 [رابط الشراء]({d['url']})\n\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def check_deals_periodic(bot):
    """
    Background worker: scans every 10 minutes and sends new deals / flash sales
    directly to the Telegram chat.
    """
    logger.info(f"Starting periodic deals checker every {SCAN_INTERVAL_SECONDS} seconds (10 minutes)...")
    while True:
        try:
            logger.info("Executing 10-minute scheduled scan across all platforms...")
            new_deals = await scrape_all_deals()
            
            for deal in new_deals:
                is_alert = save_or_update_deal(deal)
                # Alert triggers if new deal with >= 40% discount OR ASUS ROG Strix 18
                if is_alert and CHAT_ID:
                    alert_header = "🚨 **فلاش سيل عاجل (تحديث الـ 10 دقائق)!**" if deal.get("is_flash_sale") else "📢 **صفقة حقيقية جديدة!**"
                    if deal.get("is_special_laptop"):
                        alert_header = "⭐ **تنبيه لابتوب طلبك الخاص (ASUS ROG Strix 18)!**"
                        
                    msg = (
                        f"{alert_header}\n\n"
                        f"🏷️ **{deal['title']}**\n"
                        f"🏪 المتجر: **{deal['store']}** | القسم: {deal.get('category', '')}\n"
                        f"💵 السعر الحالي: **{deal['discount_price']:,.0f} ج.م** "
                        f"~~({deal['original_price']:,.0f} ج.م)~~\n"
                        f"🔥 نسبة الخصم الفعلي: **{deal['discount_percentage']}%**\n"
                    )
                    if deal.get("coupon_code"):
                        msg += f"🎟️ كود إضافي: `{deal['coupon_code']}`\n"
                    if deal.get("installment_info"):
                        msg += f"💳 التقسيط: {deal['installment_info']}\n"
                        
                    keyboard = [[InlineKeyboardButton("🛒 اشتري الآن والحق العرض ↗", url=deal["url"])]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    try:
                        await bot.send_message(
                            chat_id=CHAT_ID,
                            text=msg,
                            parse_mode="Markdown",
                            reply_markup=reply_markup,
                            disable_web_page_preview=False
                        )
                        logger.info(f"Telegram notification sent for: {deal['title']}")
                    except Exception as e:
                        logger.error(f"Failed to send Telegram message: {e}")
                        
        except Exception as e:
            logger.error(f"Error in 10-minute scan cycle: {e}")
            
        # Wait 10 minutes (600 seconds)
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
        
        # Start the 10-minute automated background scanner
        asyncio.create_task(check_deals_periodic(bot_app.bot))
    else:
        logger.warning("BOT_TOKEN is not set yet in .env! Running FastAPI server only.")

    port = int(os.getenv("PORT", 8080))
    config = uvicorn.Config(app=app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
