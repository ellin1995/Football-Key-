"""
Telegram Football Betting & Prediction Bot
مطور بتقنيات: Python, python-telegram-bot, Google Gemini AI, Supabase, Render Hosting
"""

import os
import sys
import logging
import threading
import asyncio
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

# استدعاء مكتبة التليجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# استدعاء Supabase
try:
    from supabase import create_client, Client
except ImportError:
    Client = None
    create_client = None

# استدعاء Gemini (دعم Google GenAI الحديث مع التوافقية العكسية)
GEMINI_CLIENT_TYPE = None
try:
    from google import genai
    from google.genai import types
    GEMINI_CLIENT_TYPE = "new"
except ImportError:
    try:
        import google.generativeai as legacy_genai
        GEMINI_CLIENT_TYPE = "legacy"
    except ImportError:
        GEMINI_CLIENT_TYPE = None

# تحميل المتغيرات البيئية من ملف .env إن وجد
load_dotenv()

# إعداد التسجيل (Logging)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("FootballBot")

# =========================================================================
# الإعدادات والمفاتيح الأساسية
# =========================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9154832991:AAFn34ZAsOjkEhrRbnsKxfERbRLoC3fWdNw")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "05f1e429a91687bfe744f0910f408a59")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/StreamVaultLiveBot")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# تهيئة عميل Supabase
supabase_client: Client = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("تم الاتصال بـ Supabase بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في الاتصال بقاعدة بيانات Supabase: {e}")
else:
    logger.warning("لم يتم تعيين SUPABASE_URL أو SUPABASE_KEY. سيتم تشغيل البوت بدون حفظ البيانات في قاعدة البيانات حتى يتم إدخالها.")

# تهيئة عميل Gemini
gemini_client = None
if GEMINI_CLIENT_TYPE == "new":
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("تم تهيئة مكتبة google-genai الحديثة بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء تهيئة google-genai: {e}")
elif GEMINI_CLIENT_TYPE == "legacy":
    try:
        legacy_genai.configure(api_key=GEMINI_API_KEY)
        gemini_client = legacy_genai.GenerativeModel("gemini-1.5-flash")
        logger.info("تم تهيئة مكتبة google-generativeai بنجاح.")
    except Exception as e:
        logger.error(f"خطأ أثناء تهيئة google-generativeai: {e}")

# =========================================================================
# خادم الويب المصغر (Mini Web Server) للتوافق مع Render (Port 10000)
# =========================================================================
class RenderHealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        response_html = """
        <html>
            <head><title>Football Prediction Bot Status</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #0f172a; color: #f8fafc;">
                <h1 style="color: #22c55e;">⚽ Football Bot is Running!</h1>
                <p>Status: Healthy & Listening to Telegram Updates</p>
                <p>Deployed on Render Free Tier</p>
            </body>
        </html>
        """
        self.wfile.write(response_html.encode("utf-8"))

    def log_message(self, format, *args):
        # منع تكرار سجلات الـ Health Check في شاشة الكونسول
        return

def start_render_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), RenderHealthServer)
    logger.info(f"تم تشغيل خادم الويب المصغر على المنفذ {port} لتثبيت استضافة Render.")
    server.serve_forever()

# =========================================================================
# جلب المباريات اليومية (الدوريات الكبرى) عبر الرياضة APIs
# =========================================================================
LEAGUES_KEYWORDS = [
    "premier league", "la liga", "serie a", "bundesliga", "champions league",
    "uefa champions league", "الدوري الإنجليزي", "الدوري الإسباني", "الدوري الإيطالي", "الدوري الألماني"
]

DEFAULT_HIGHLIGHT_MATCHES = [
    ("ريال مدريد 🆚 برشلونة (La Liga)", "Real Madrid vs Barcelona"),
    ("مانشستر سيتي 🆚 ليفربول (Premier League)", "Manchester City vs Liverpool"),
    ("أرسنال 🆚 تشيلسي (Premier League)", "Arsenal vs Chelsea"),
    ("بايرن ميونخ 🆚 دورتموند (Bundesliga)", "Bayern Munich vs Borussia Dortmund"),
    ("إنتر ميلان 🆚 ميلان (Serie A)", "Inter Milan vs AC Milan"),
    ("باريس سان جيرمان 🆚 أتلتيكو مدريد (UCL)", "PSG vs Atletico Madrid"),
]

def fetch_major_league_matches():
    """
    جلب جدول مباريات اليوم للدوريات الكبرى من TheSportsDB API
    مع توفير مباريات قمة بديلة تلقائياً في حال عدم وجود مباريات في نفس اليوم.
    """
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsday.php?d={today_str}&s=Soccer"
    
    matches = []
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            data = res.json()
            events = data.get("events") or []
            for event in events:
                league_name = (event.get("strLeague") or "").lower()
                # التحقق إذا كانت المباراة تنتمي لأحد الدوريات الكبرى
                if any(kw in league_name for kw in LEAGUES_KEYWORDS):
                    home = event.get("strHomeTeam", "Home")
                    away = event.get("strAwayTeam", "Away")
                    league_display = event.get("strLeague", "")
                    title = f"{home} 🆚 {away} ({league_display})"
                    match_query = f"{home} vs {away}"
                    matches.append((title, match_query))
    except Exception as e:
        logger.warning(f"تعذر جلب المباريات من TheSportsDB: {e}")

    # إذا لم تكن هناك مباريات جارية اليوم في الدوريات الكبرى (مثلاً أيام الاثنين أو منتصف الأسبوع خارج الأبطال)
    if not matches:
        return DEFAULT_HIGHLIGHT_MATCHES, False

    return matches[:8], True

# =========================================================================
# تحليل المباراة عبر Google Gemini AI
# =========================================================================
def generate_gemini_prediction(match_name: str) -> str:
    """
    إرسال استعلام إلى Gemini لتحليل المباراة وتوليد النسب، النتائج وتوصيات الرهانات.
    """
    prompt = f"""
أنت خبير ومحلل رياضي دولي متخصص في إحصائيات كرة القدم وتوقعات الرهانات الرياضية المربحة وذات القيمة العالية (Value Bets).

المباراة المطلوب تحليلها: {match_name}

المطلوب بدقة:
1.  **نسب الفوز المتوقعة (1X2):**
   - فوز الفريق الأول (%): 
   - التعادل (%): 
   - فوز الفريق الثاني (%): 
2. ⚽ **النتيجة الدقيقة المتوقعة (Exact Score):**
   - ضع النتيجة الأقرب رقمياً (مثال: 2 - 1 أو 1 - 1) مع تعليل مقتضب في سطر واحد.
3.  **أقوى مقترحات الرهانات الذكية (Smart Betting Tips):**
   - رهان الأهداف (Over/Under 2.5): مع توضيح الاحتمال.
   - تسجيل كلا الفريقين (Both Teams to Score - BTTS): نعم / لا.
   - رهان الأمان (Double Chance أو Handicap): أفضل اختيار منخفض المخاطر.
4.  **نصيحة تكتيكية حاسمة:** سطرين عن نقاط القوة والضعف ومفتاح الفوز.

شروط هامة للتنسيق:
- استخدم إيموجيات ملائمة ونسق النص باللغة العربية بأسلوب راقٍ وممتع للقراءة ومباشر.
- لا تضع إخلاء مسؤولية طويل، فقط سطر تحذيري بسيط في النهاية.
"""

    if not gemini_client:
        return (
            f" <b>تحليل لمباراة: {match_name}</b>\n\n"
            "⚠️ <i>ملاحظة: تعذر الاتصال بنموذج Gemini الذكي حالياً (يرجى التحقق من صلاحية مفتاح Gemini API Key).</i>\n\n"
            "📊 <b>التقدير المبدئي:</b>\n"
            "• نسبة الفوز: 45% - 25% - 30%\n"
            "• النتيجة المتوقعة: 2 - 1\n"
            "• اقتراح الرهان: Over 2.5 Goals أو BTTS: Yes\n"
        )

    try:
        if GEMINI_CLIENT_TYPE == "new":
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        elif GEMINI_CLIENT_TYPE == "legacy":
            response = gemini_client.generate_content(prompt)
            return response.text
    except Exception as e:
        logger.error(f"خطأ في استجابة Gemini: {e}")
        # محاولة بموديل بديل إذا كان الاسم مختلفاً
        try:
            if GEMINI_CLIENT_TYPE == "new":
                response = gemini_client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt
                )
                return response.text
        except Exception as e2:
            logger.error(f"فشلت المحاولة الثانية لـ Gemini: {e2}")

        return (
            f" <b>تحليل مباراة: {match_name}</b>\n\n"
            " تعذر استرجاع التحليل التلقائي لحظياً من خوادم الذكاء الاصطناعي بسبب ضغط الطلبات.\n"
            "يرجى إعادة المحاولة بعد ثوانٍ قليلة."
        )

# =========================================================================
# تخزين البيانات في Supabase
# =========================================================================
async def save_to_supabase(user_id: int, username: str, user_message: str, bot_reply: str):
    """
    تخزين سجل التوقع في جدول predictions على Supabase بخيط منفصل (non-blocking).
    الأعمدة المطلوبة: user_id, username, user_message, bot_reply
    """
    if not supabase_client:
        return

    def _sync_insert():
        try:
            record = {
                "user_id": str(user_id),
                "username": username or "Unknown",
                "user_message": user_message[:500] if user_message else "",
                "bot_reply": bot_reply[:2000] if bot_reply else ""
            }
            supabase_client.table("predictions").insert(record).execute()
            logger.info(f"تم حفظ توقع المستخدم {user_id} في Supabase بنجاح.")
        except Exception as ex:
            logger.error(f"فشل أثناء حفظ البيانات في Supabase: {ex}")

    # تشغيل الحفظ بشكل غير متزامن لتفادي تعطيل سرعة استجابة البوت
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_insert)

# =========================================================================
# معالجات أوامر التليجرام (Telegram Handlers)
# =========================================================================

def build_matches_keyboard(matches, is_live_today):
    """بناء لوحة أزرار تفاعلية للمباريات"""
    keyboard = []
    for title, query in matches:
        keyboard.append([InlineKeyboardButton(title, callback_data=f"match:{query[:40]}")])
    
    # زر تحديث القائمة وزر الاشتراك بالقناة
    extra_buttons = [
        InlineKeyboardButton("🔄 تحديث المباريات", callback_data="refresh_matches"),
        InlineKeyboardButton("🔥 القناة الرسمية والتوصيات VIP", url=CHANNEL_URL)
    ]
    keyboard.append(extra_buttons)
    return InlineKeyboardMarkup(keyboard)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على أمر /start وجلب المباريات"""
    user = update.effective_user
    matches, is_live = fetch_major_league_matches()
    
    status_header = "📅 <b>مباريات اليوم الحالية (الدوريات الكبرى):</b>" if is_live else "⚡ <b>أبرز مباريات القمة المختارة لهذا الأسبوع:</b>"
    
    welcome_text = (
        f"أهلاً بك يا <b>{user.first_name}</b> في <b>بوت الذكاء الاصطناعي لتحليل مباريات كرة القدم والرهانات الرياضية!</b> ⚽🤖\n\n"
        f"{status_header}\n"
        "اضغط على أي مباراة بالأسفل للحصول على التحليل الذكي وتوقعات النسب والرهانات الرابحة فوراً:\n"
        "<i>(أو يمكنك كتابة اسم أي مباراة مباشرة في الشات وسأقوم بتحليلها لك!)</i>"
    )

    reply_markup = build_matches_keyboard(matches, is_live)
    await update.message.reply_text(
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغط على أزرار المباريات التفاعلية"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    if data == "refresh_matches":
        matches, is_live = fetch_major_league_matches()
        reply_markup = build_matches_keyboard(matches, is_live)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        return

    if data.startswith("match:"):
        match_query = data.replace("match:", "")
        
        # إشعار المستخدم ببدء التحليل
        wait_message = await query.message.reply_text(
            f"⏳ <b>جاري تحليل مباراة ({match_query}) عبر الذكاء الاصطناعي وحساب أفضل نسب الرهانات...</b>",
            parse_mode=ParseMode.HTML
        )

        # توليد التحليل في Thread منفصل لعدم تجميد السيرفر
        loop = asyncio.get_running_loop()
        analysis_text = await loop.run_in_executor(None, generate_gemini_prediction, match_query)

        # إضافة الدعوة للاشتراك بالقناة
        final_response = (
            f"{analysis_text}\n\n"
            "──────────────────\n"
            "💎 <b>هل تريد الحصول على التوصيات الحصرية والصفقات المباشرة (Live Bets) بنسب ربح عالية؟</b>\n"
            "👉 لا تفوت الفرصة وانضم الآن لقناتنا المخصصة على تليجرام!"
        )

        # زر مباشر للاشتراك بالقناة
        channel_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 انضم الآن للقناة الحصرية VIP 🔥", url=CHANNEL_URL)]
        ])

        try:
            await wait_message.delete()
        except Exception:
            pass

        await query.message.reply_text(
            text=final_response,
            reply_markup=channel_button,
            parse_mode=ParseMode.HTML
        )

        # حفظ التفاعل في قاعدة بيانات Supabase
        await save_to_supabase(
            user_id=user.id,
            username=user.username or user.first_name,
            user_message=f"Button: {match_query}",
            bot_reply=final_response
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة إرسال المستخدم لاسم أي مباراة كنص"""
    user_text = update.message.text.strip()
    user = update.effective_user

    if not user_text:
        return

    # إشعار المستخدم ببدء التحليل
    wait_message = await update.message.reply_text(
        f"⏳ <b>جاري تحليل مباراة ({user_text}) وتقديم أدق التوقعات...</b>",
        parse_mode=ParseMode.HTML
    )

    loop = asyncio.get_running_loop()
    analysis_text = await loop.run_in_executor(None, generate_gemini_prediction, user_text)

    final_response = (
        f"{analysis_text}\n\n"
        "──────────────────\n"
        "💎 <b>هل تبحث عن رهانات VIP يومية ومتابعة حية مع كبار المحللين؟</b>\n"
        "👉 اشترك الآن في القناة الرسمية لمزيد من التحليلات الحصرية:"
    )

    channel_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 انضم الآن للقناة الحصرية VIP 🔥", url=CHANNEL_URL)]
    ])

    try:
        await wait_message.delete()
    except Exception:
        pass

    await update.message.reply_text(
        text=final_response,
        reply_markup=channel_button,
        parse_mode=ParseMode.HTML
    )

    # حفظ في Supabase
    await save_to_supabase(
        user_id=user.id,
        username=user.username or user.first_name,
        user_message=user_text,
        bot_reply=final_response
    )

# =========================================================================
# تشغيل التطبيق (Main Execution)
# =========================================================================
def main():
    print("=" * 60)
    print("🚀 بدء تشغيل بوت توقعات كرة القدم والرهانات الرياضية...")
    print("=" * 60)

    # 1. تشغيل خادم الويب المصغر في Thread منفصل لدعم استضافة Render المجانية
    web_thread = threading.Thread(target=start_render_web_server, daemon=True)
    web_thread.start()

    # 2. إعداد وتشغيل تطبيق التليجرام
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

    logger.info("البوت يعمل الآن وهو في انتظار رسائل المستخدمين...")
    application.run_polling()

if __name__ == "__main__":
    main()
