@echo off
chcp 65001 > nul
echo ====================================================
echo  رادار عروض البلاك فرايدي مصر 2026 - Telegram Deals Bot
echo ====================================================
echo.

set "PATH=C:\Users\GO\.local\bin;%PATH%"

if not exist ".venv\Scripts\python.exe" (
    echo [!] جاري تجهيز بيئة العمل وتثبيت الحزم...
    uv venv
    uv pip install python-telegram-bot aiohttp beautifulsoup4 python-dotenv fastapi uvicorn
)

echo [*] تشغيل خادم الويب والبوت مع تحديث كل 10 دقائق...
.venv\Scripts\python.exe bot.py
pause
