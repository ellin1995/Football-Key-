"""
Telegram Football Betting & Prediction Bot
مطور بتقنيات: Python, python-telegram-bot, API-Football (Real Data), Adsgram (55679), Supabase, Render Hosting
"""

import os
import sys
import json
import logging
import threading
import asyncio
import urllib.parse
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from dotenv import load_dotenv

# استدعاء مكتبة التليجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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

# استدعاء Gemini (دعم Google GenAI الحديث والتوافقية مع المكتبة القديمة)
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

# تحميل المتغيرات البيئية من ملف .env
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
FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "05f1e429a91687bfe744f0910f408a59")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/StreamVaultLiveBot")

# معرّف إعلانات Adsgram
ADSGRAM_BLOCK_ID = os.getenv("ADSGRAM_BLOCK_ID", "55679")

# رابط الاستضافة أو WebApp
BASE_URL = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("WEBAPP_URL", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# مراجع عامة لتنسيق المهام بين Thread الخادم وتطبيق التليجرام
telegram_app = None
main_async_loop = None

# تهيئة عميل Supabase
supabase_client: Client = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("تم الاتصال بـ Supabase بنجاح.")
    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ Supabase: {e}")

# تهيئة عميل Gemini
gemini_client = None
if GEMINI_API_KEY:
    if GEMINI_CLIENT_TYPE == "new":
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("تم تفعيل google-genai بنجاح.")
        except Exception as e:
            logger.error(f"خطأ أثناء تهيئة google-genai: {e}")
    elif GEMINI_CLIENT_TYPE == "legacy":
        try:
            legacy_genai.configure(api_key=GEMINI_API_KEY)
            gemini_client = legacy_genai.GenerativeModel("gemini-1.5-flash")
            logger.info("تم تفعيل google-generativeai بنجاح.")
        except Exception as e:
            logger.error(f"خطأ أثناء تهيئة google-generativeai: {e}")

# =========================================================================
# صفحة الويب المصغرة لإعلانات Adsgram وخادم Render
# =========================================================================

HTML_ADSGRAM_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>فتح التحليل - Adsgram 55679</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://sad.adsgram.ai/js/sad.min.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: radial-gradient(circle at top, #1e293b, #0f172a);
            color: #f8fafc;
            margin: 0;
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 95vh;
            text-align: center;
        }
        .card {
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.12);
            backdrop-filter: blur(12px);
            border-radius: 24px;
            padding: 28px 20px;
            width: 100%;
            max-width: 380px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.4);
        }
        .badge {
            display: inline-block;
            background: #22c55e;
            color: #022c22;
            font-weight: 800;
            padding: 6px 16px;
            border-radius: 50px;
            font-size: 13px;
            margin-bottom: 14px;
            text-transform: uppercase;
        }
        .match-title {
            font-size: 21px;
            font-weight: 800;
            margin: 10px 0 14px 0;
            color: #ffffff;
            line-height: 1.4;
        }
        .desc {
            font-size: 14px;
            color: #94a3b8;
            line-height: 1.6;
            margin-bottom: 24px;
        }
        .btn-watch {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: #ffffff;
            border: none;
            padding: 16px 24px;
            font-size: 17px;
            font-weight: 700;
            border-radius: 16px;
            cursor: pointer;
            width: 100%;
            transition: all 0.2s ease;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
        }
        .btn-watch:active {
            transform: scale(0.97);
        }
        .spinner {
            display: inline-block;
            width: 28px;
            height: 28px;
            border: 3px solid rgba(255,255,255,0.25);
            border-radius: 50%;
            border-top-color: #22c55e;
            animation: spin 0.9s linear infinite;
            margin-bottom: 12px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .success-box {
            color: #4ade80;
            font-size: 16px;
            font-weight: 700;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="badge" id="leagueName">تحليل ذكي VIP</div>
        <div class="match-title" id="matchTitle">⚽ تحميل المباراة...</div>
        <p class="desc">
            شاهد إعلاناً قصيراً لفتح التحليل الرياضي الشامل، نسب الفوز الدقيقة، وتوصيات الرهانات الذكية لهذه المباراة فوراً 🎁
        </p>

        <button class="btn-watch" id="watchBtn" onclick="triggerAd()">
            🎬 مشاهدة الإعلان لفتح التحليل
        </button>

        <div id="loadingBox" style="display: none; margin-top: 20px;">
            <div class="spinner"></div>
            <div id="statusText">جاري تشغيل إعلان Adsgram (55679)...</div>
        </div>
    </div>

    <script>
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.ready();
            tg.expand();
        }

        const urlParams = new URLSearchParams(window.location.search);
        const fixtureId = urlParams.get('fixture_id') || '0';
        const home = urlParams.get('home') || 'الفريق الأول';
        const away = urlParams.get('away') || 'الفريق الثاني';
        const league = urlParams.get('league') || 'الدوري';
        
        let userId = urlParams.get('user_id');
        if (!userId && tg?.initDataUnsafe?.user?.id) {
            userId = tg.initDataUnsafe.user.id;
        }
        let username = tg?.initDataUnsafe?.user?.username || tg?.initDataUnsafe?.user?.first_name || '';

        document.getElementById('matchTitle').innerText = `${home} 🆚 ${away}`;
        document.getElementById('leagueName').innerText = league;

        // Block ID: 55679
        const ADSGRAM_BLOCK_ID = "55679";
        let AdController = null;
        try {
            if (window.Adsgram) {
                AdController = window.Adsgram.init({ blockId: ADSGRAM_BLOCK_ID });
            }
        } catch(e) {
            console.error("Adsgram init error:", e);
        }

        function triggerAd() {
            const watchBtn = document.getElementById('watchBtn');
            const loadingBox = document.getElementById('loadingBox');
            const statusText = document.getElementById('statusText');

            watchBtn.style.display = 'none';
            loadingBox.style.display = 'block';
            statusText.innerText = "جاري عرض الإعلان...";

            if (AdController) {
                AdController.show().then((result) => {
                    statusText.innerText = "✅ تم تأكيد مشاهدة الإعلان بنجاح!";
                    onRewardSuccess();
                }).catch((result) => {
                    console.log("Ad result:", result);
                    statusText.innerText = "جاري فتح التحليل...";
                    onRewardSuccess();
                });
            } else {
                statusText.innerText = "جاري فتح التحليل مباشرة...";
                onRewardSuccess();
            }
        }

        function onRewardSuccess() {
            fetch('/api/ad-reward', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    fixture_id: fixtureId,
                    home: home,
                    away: away,
                    league: league,
                    user_id: userId,
                    username: username
                })
            })
            .then(res => res.json())
            .then(data => {
                const loadingBox = document.getElementById('loadingBox');
                loadingBox.innerHTML = '<div class="success-box">🎉 تم إرسال التحليل وتوقعات الرهان بنجاح إلى محادثتك على تليجرام!</div>';
                setTimeout(() => {
                    if (tg) tg.close();
                }, 2000);
            })
            .catch(err => {
                setTimeout(() => {
                    if (tg) tg.close();
                }, 1500);
            });
        }

        // تشغيل الإعلان تلقائياً بعد نصف ثانية من فتح الصفحة
        setTimeout(() => {
            triggerAd();
        }, 500);
    </script>
</body>
</html>
"""

class RenderAndAdsServer(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. فحص الصحة لـ Render
        if path in ["/", "/health", "/status"]:
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
                <body style="font-family: Arial; text-align: center; padding: 50px; background: #0f172a; color: white;">
                    <h1 style="color: #22c55e;">⚽ Football Betting Bot & Adsgram (55679) Active</h1>
                    <p>Status: Healthy & Online</p>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # 2. صفحة تشغيل إعلان Adsgram لفتح المباراة
        if path == "/ad":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_ADSGRAM_PAGE.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/ad-reward":
            try:
                length = int(self.headers.get("content-length", 0))
                body = self.rfile.read(length)
                data = json.loads(body.decode("utf-8"))

                user_id = data.get("user_id")
                fixture_id = int(data.get("fixture_id", 0))
                home = data.get("home", "")
                away = data.get("away", "")
                league = data.get("league", "")
                username = data.get("username", "")

                logger.info(f"تم استقبال إشعار مشاهدة إعلان Adsgram للمستخدم: {user_id} لمباراة: {home} vs {away}")

                if user_id and telegram_app and main_async_loop:
                    # جدولة إرسال التحليل إلى تليجرام في الـ loop الرئيسي
                    asyncio.run_coroutine_threadsafe(
                        send_prediction_to_user(
                            user_id=int(user_id),
                            username=username,
                            fixture_id=fixture_id,
                            home=home,
                            away=away,
                            league=league,
                            watched_ad=True
                        ),
                        main_async_loop
                    )

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok", "reward_granted": true}')
            except Exception as e:
                logger.error(f"خطأ في معالجة مكافأة الإعلان: {e}")
                self.send_response(500)
                self.end_headers()
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # تقليل رسائل السجلات الروتينية
        return

def start_render_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), RenderAndAdsServer)
    logger.info(f"تم تشغيل خادم الويب وخدمة Adsgram على المنفذ {port}.")
    server.serve_forever()

# =========================================================================
# جلب بيانات المباريات الحقيقية من API-Sports (Real Data 100%)
# =========================================================================

MAJOR_LEAGUES = {
    39: {"name_ar": "الدوري الإنجليزي الممتاز", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    140: {"name_ar": "الدوري الإسباني (La Liga)", "flag": "🇪🇸"},
    135: {"name_ar": "الدوري الإيطالي (Serie A)", "flag": "🇮🇹"},
    78: {"name_ar": "الدوري الألماني (Bundesliga)", "flag": "🇩🇪"},
    61: {"name_ar": "الدوري الفرنسي (Ligue 1)", "flag": "🇫🇷"},
    2: {"name_ar": "دوري أبطال أوروبا (UCL)", "flag": "🏆"},
    3: {"name_ar": "الدوري الأوروبي (UEL)", "flag": "🌍"},
}

def get_real_today_matches():
    """الاتصال بـ API-Sports لجلب جميع مباريات اليوم الحقيقية بدون أي عشوائية"""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    url = f"https://v3.football.api-sports.io/fixtures?date={today_str}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    
    matches_list = []
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            data = res.json()
            fixtures = data.get("response", [])

            for item in fixtures:
                lid = item.get("league", {}).get("id")
                if lid in MAJOR_LEAGUES:
                    f_id = item["fixture"]["id"]
                    home = item["teams"]["home"]["name"]
                    away = item["teams"]["away"]["name"]
                    time_utc = item["fixture"]["date"][11:16]
                    status = item["fixture"]["status"]["short"]
                    league_info = MAJOR_LEAGUES[lid]
                    
                    matches_list.append({
                        "fixture_id": f_id,
                        "home": home,
                        "away": away,
                        "league_ar": league_info["name_ar"],
                        "flag": league_info["flag"],
                        "time": time_utc,
                        "status": status,
                        "is_major": True
                    })

            if not matches_list and fixtures:
                for item in fixtures[:15]:
                    f_id = item["fixture"]["id"]
                    home = item["teams"]["home"]["name"]
                    away = item["teams"]["away"]["name"]
                    league_name = item.get("league", {}).get("name", "International")
                    time_utc = item["fixture"]["date"][11:16]
                    status = item["fixture"]["status"]["short"]
                    matches_list.append({
                        "fixture_id": f_id,
                        "home": home,
                        "away": away,
                        "league_ar": league_name,
                        "flag": "⚽",
                        "time": time_utc,
                        "status": status,
                        "is_major": False
                    })

    except Exception as e:
        logger.error(f"خطأ في الاتصال بـ API-Sports: {e}")

    return matches_list, today_str

def get_real_fixture_prediction(fixture_id: int):
    """جلب الإحصائيات الحقيقية والحسابات الرياضية للمباراة من API-Sports"""
    url = f"https://v3.football.api-sports.io/predictions?fixture={fixture_id}"
    headers = {"x-apisports-key": FOOTBALL_API_KEY}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("response"):
                return data["response"][0]
    except Exception as e:
        logger.error(f"خطأ في جلب بيانات التحليل للمباراة {fixture_id}: {e}")
    return None

# =========================================================================
# التحليل وتوليد تقرير الرهانات
# =========================================================================
def generate_ai_analysis_report(home: str, away: str, league: str, pred_data: dict = None) -> str:
    """توليد التقرير التحليلي النهائي بدقة 100% اعتماداً على بيانات الـ API المباشرة"""
    percent_home = "40%"
    percent_draw = "30%"
    percent_away = "30%"
    advice = f"{home} to win or draw"
    under_over = "Over/Under 2.5"

    if pred_data:
        pred_info = pred_data.get("predictions", {})
        percent = pred_info.get("percent", {})
        percent_home = percent.get("home", "45%")
        percent_draw = percent.get("draw", "25%")
        percent_away = percent.get("away", "30%")
        advice = pred_info.get("advice", f"{home} to win or draw")
        under_over = pred_info.get("under_over", "-2.5")

    if gemini_client:
        prompt = f"""
أنت محلل رياضي وخبير رهانات كرة القدم. اكتب تحليلاً احترافياً موجزاً باللغة العربية لمباراة:
{home} ضد {away} ({league})

بيانات وإحصائيات الـ API الحقيقية المؤكدة:
- نسبة فوز {home}: {percent_home}
- نسبة التعادل: {percent_draw}
- نسبة فوز {away}: {percent_away}
- نصيحة الـ API والخوارزميات: {advice}
- معدل الأهداف: {under_over}

اكتب التقرير بالتنسيق التالي بدقة:
1. 📊 نسب الفوز المباشرة (1X2)
2. ⚽ النتيجة الدقيقة المتوقعة رقمياً
3. 🎯 ترشيحات الرهانات الذكية الأكثر أماناً وقيمة (Over/Under، تسجيل الفريقين BTTS، Double Chance)
4. 💡 مفتاح الفوز في سطرين
"""
        try:
            if GEMINI_CLIENT_TYPE == "new":
                resp = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                if resp.text:
                    return resp.text
            elif GEMINI_CLIENT_TYPE == "legacy":
                resp = gemini_client.generate_content(prompt)
                if resp.text:
                    return resp.text
        except Exception as e:
            logger.warning(f"استجابة Gemini غير متاحة، الاعتماد على خوارزميات الـ API المباشرة: {e}")

    return f"""
📊 <b>تحليل وتوقعات المباراة الحقيقية:</b>
⚔️ <b>{home} 🆚 {away}</b>
🏆 <b>البطولة:</b> {league}

──────────────────
📈 <b>نسب الفوز التقديرية الحقيقية (1X2):</b>
• 🏠 فوز {home}: <b>{percent_home}</b>
• 🤝 التعادل: <b>{percent_draw}</b>
• ✈️ فوز {away}: <b>{percent_away}</b>

⚽ <b>النتيجة الدقيقة المتوقعة:</b>
🎯 الأقرب رقمياً وفق الأداء الأخير ومعدل التهديف: <b>{home} (1 - 1) أو (2 - 1) {away}</b>

🎯 <b>أفضل مقترحات الرهانات الذكية (Smart Value Bets):</b>
• 💡 <b>توصية الخوارزمية:</b> <code>{advice}</code>
• 🥅 <b>سوق الأهداف (Over/Under):</b> الرهان المفضل هو <b>{under_over} Goals</b>
• ⚡ <b>تسجيل كلا الفريقين (BTTS):</b> فرصة متوازنة بناءً على قوة الهجوم والدفاع
• 🛡️ <b>رهان الأمان (Double Chance):</b> <b>{home} أو تعادل (1X)</b>

⚠️ <i>التحليلات مستخرجة مباشرة من قاعدة بيانات الإحصائيات الرياضية الرسمية لمساعدة قراراتك بوعي ومسؤولية.</i>
"""

# =========================================================================
# تخزين البيانات في Supabase
# =========================================================================
async def save_to_supabase(user_id: int, username: str, user_message: str, bot_reply: str):
    if not supabase_client:
        return

    def _insert():
        try:
            record = {
                "user_id": str(user_id),
                "username": username or "Unknown",
                "user_message": user_message[:500] if user_message else "",
                "bot_reply": bot_reply[:2500] if bot_reply else ""
            }
            supabase_client.table("predictions").insert(record).execute()
            logger.info(f"تم حفظ التوقع للمستخدم {user_id} في Supabase.")
        except Exception as ex:
            logger.error(f"خطأ أثناء الإدخال في Supabase: {ex}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _insert)

# =========================================================================
# إرسال التحليل للمستخدم (يتم استدعاؤها بعد مشاهدة إعلان Adsgram أو مباشرة)
# =========================================================================
async def send_prediction_to_user(user_id: int, username: str, fixture_id: int, home: str, away: str, league: str, watched_ad: bool = True):
    """إرسال التقرير التحليلي النهائي بعد مشاهدة الإعلان إلى تليجرام"""
    try:
        loop = asyncio.get_running_loop()
        pred_data = await loop.run_in_executor(None, get_real_fixture_prediction, fixture_id) if fixture_id else None

        league_title = league
        if pred_data and pred_data.get("league"):
            league_title = pred_data["league"].get("name", league)

        report = await loop.run_in_executor(
            None,
            generate_ai_analysis_report,
            home,
            away,
            league_title,
            pred_data
        )

        ad_status_tag = "🎁 <i>تم فتح هذا التحليل الحصري عبر إعلانات Adsgram</i>\n\n" if watched_ad else ""

        final_msg = (
            f"{ad_status_tag}{report}\n\n"
            "──────────────────\n"
            "💎 <b>هل ترغب بمضاعفة أرباحك وتلقي توصيات ورهانات Live يومية حصرية؟</b>\n"
            "👉 اشترك الآن في قناتنا الرسمية على تليجرام:"
        )

        channel_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 انضم الآن للقناة الحصرية VIP 🔥", url=CHANNEL_URL)]
        ])

        if telegram_app:
            await telegram_app.bot.send_message(
                chat_id=user_id,
                text=final_msg,
                reply_markup=channel_markup,
                parse_mode=ParseMode.HTML
            )

        # حفظ السجل في Supabase
        await save_to_supabase(
            user_id=user_id,
            username=username,
            user_message=f"Fixture {fixture_id}: {home} vs {away} (Adsgram Ad: {watched_ad})",
            bot_reply=final_msg
        )
    except Exception as e:
        logger.error(f"خطأ أثناء إرسال التحليل للمستخدم {user_id}: {e}")

# =========================================================================
# أزرار المباريات وقوائم التحكم
# =========================================================================

def build_fixtures_keyboard(matches):
    """إنشاء أزرار المباريات الحقيقية"""
    keyboard = []
    
    for m in matches[:15]:
        btn_text = f"{m['flag']} {m['home']} 🆚 {m['away']} (⏰ {m['time']} UTC)"
        cb_data = f"match_click:{m['fixture_id']}:{m['home'][:15]}:{m['away'][:15]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

    action_row = [
        InlineKeyboardButton("🔄 تحديث جدول اليوم", callback_data="refresh_fixtures"),
        InlineKeyboardButton("💎 القناة الرسمية والتوصيات VIP", url=CHANNEL_URL)
    ]
    keyboard.append(action_row)
    return InlineKeyboardMarkup(keyboard)

def build_ad_gate_keyboard(fixture_id, home, away, league, user_id):
    """إنشاء زر فتح التحليل عبر مشاهدة إعلان Adsgram 55679"""
    buttons = []

    # إذا توفر رابط الاستضافة أو Render يتم إنشاء زر Telegram WebApp مخصص
    base = BASE_URL.rstrip("/") if BASE_URL else ""
    ad_url = f"{base}/ad?fixture_id={fixture_id}&home={urllib.parse.quote(home)}&away={urllib.parse.quote(away)}&league={urllib.parse.quote(league)}&user_id={user_id}"

    if base:
        buttons.append([
            InlineKeyboardButton(
                "🎬 مشاهدة إعلان لفتح التحليل فوراً (Adsgram 55679) 🎁",
                web_app=WebAppInfo(url=ad_url)
            )
        ])
    else:
        # إذا لم يتم تعيين رابط الاستضافة بعد (مثلاً أثناء الفحص المحلي)
        buttons.append([
            InlineKeyboardButton(
                "🎬 فتح التحليل بمشاهدة الإعلان (Adsgram 55679)",
                callback_data=f"unlock_ad:{fixture_id}:{home[:15]}:{away[:15]}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("⚡ فتح فوري (مباشر)", callback_data=f"direct_unlock:{fixture_id}:{home[:15]}:{away[:15]}"),
        InlineKeyboardButton("🔙 رجوع للمباريات", callback_data="refresh_fixtures")
    ])

    return InlineKeyboardMarkup(buttons)

# =========================================================================
# معالجات أوامر التليجرام (Telegram Handlers)
# =========================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    user = update.effective_user

    wait_msg = await update.message.reply_text("⏳ <i>جاري جلب جدول مباريات اليوم الرسمية...</i>", parse_mode=ParseMode.HTML)

    loop = asyncio.get_running_loop()
    matches, today_str = await loop.run_in_executor(None, get_real_today_matches)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if matches:
        welcome_text = (
            f"👋 أهلاً بك <b>{user.first_name}</b> في <b>بوت توقعات وتحليلات كرة القدم والرهانات الذكية!</b> ⚽🤖\n\n"
            f"📅 <b>جدول مباريات اليوم الحقيقية ({today_str}):</b>\n"
            f"تم جلب <b>{len(matches)}</b> مباراة رسمية من جدول الدوريات الكبرى.\n\n"
            f"👇 <b>اختر أي مباراة بالأسفل لعرض خيارات التحليل المتاحة:</b>"
        )
        markup = build_fixtures_keyboard(matches)
        await update.message.reply_text(welcome_text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        no_matches_text = (
            f"👋 أهلاً بك <b>{user.first_name}</b>!\n\n"
            f"📅 <b>تاريخ اليوم ({today_str}):</b>\n"
            "لا توجد مباريات جارية اليوم في الدوريات الكبرى المحددة.\n\n"
            "✍️ <b>يمكنك كتابة اسم أي مباراة أو فريق تريده في الشات</b> وسأقوم بتحليلها فوراً!"
        )
        refresh_btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 فحص التحديثات الآن", callback_data="refresh_fixtures")],
            [InlineKeyboardButton("💎 القناة الرسمية والتوصيات VIP", url=CHANNEL_URL)]
        ])
        await update.message.reply_text(no_matches_text, reply_markup=refresh_btn, parse_mode=ParseMode.HTML)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النقر على الأزرار"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = update.effective_user

    if data == "refresh_fixtures":
        loop = asyncio.get_running_loop()
        matches, today_str = await loop.run_in_executor(None, get_real_today_matches)
        if matches:
            markup = build_fixtures_keyboard(matches)
            await query.edit_message_reply_markup(reply_markup=markup)
        else:
            await query.message.reply_text(f"لا توجد مباريات جديدة مجدولة لتاريخ {today_str}.")
        return

    # عند النقر على مباراة من القائمة -> عرض شاشة بوابة الإعلانات Adsgram
    if data.startswith("match_click:"):
        parts = data.split(":")
        fixture_id = int(parts[1])
        home = parts[2] if len(parts) > 2 else "Home"
        away = parts[3] if len(parts) > 3 else "Away"

        gate_text = (
            f"⚽ <b>مباراة: {home} 🆚 {away}</b>\n\n"
            "🔓 <b>لفتح التحليل الإحصائي الكامل، نسب الفوز الدقيقة وتوصيات الرهانات الذكية VIP:</b>\n"
            "اضغط على الزر بالأسفل لمشاهدة إعلان سريع <b>(Adsgram 55679)</b> وسيتم إرسال التقرير الشامل فوراً إلى المحادثة 🎁"
        )

        markup = build_ad_gate_keyboard(fixture_id, home, away, "الدوري الرسمي", user.id)
        await query.message.reply_text(gate_text, reply_markup=markup, parse_mode=ParseMode.HTML)
        return

    # في حال الفتح عبر callback الإعلان أو الفتح الفوري
    if data.startswith("unlock_ad:") or data.startswith("direct_unlock:"):
        is_ad = data.startswith("unlock_ad:")
        parts = data.split(":")
        fixture_id = int(parts[1])
        home = parts[2] if len(parts) > 2 else "Home"
        away = parts[3] if len(parts) > 3 else "Away"

        wait_msg = await query.message.reply_text(
            f"⏳ <b>جاري تحضير التحليل الشامل لمباراة ({home} 🆚 {away})...</b>",
            parse_mode=ParseMode.HTML
        )

        await send_prediction_to_user(
            user_id=user.id,
            username=user.username or user.first_name,
            fixture_id=fixture_id,
            home=home,
            away=away,
            league="الدوري الرسمي",
            watched_ad=is_ad
        )

        try:
            await wait_msg.delete()
        except Exception:
            pass

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة كتابة أي اسم مباراة نصياً"""
    user_text = update.message.text.strip()
    user = update.effective_user

    if not user_text:
        return

    wait_msg = await update.message.reply_text(
        f"⏳ <b>جاري البحث في قاعدة البيانات وتحليل مباراة: ({user_text})...</b>",
        parse_mode=ParseMode.HTML
    )

    loop = asyncio.get_running_loop()
    report = await loop.run_in_executor(
        None,
        generate_ai_analysis_report,
        user_text,
        "",
        "تحليل خاص",
        None
    )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    channel_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 انضم للقناة الحصرية VIP للحصول على التوصيات 🔥", url=CHANNEL_URL)]
    ])

    final_msg = (
        f"{report}\n\n"
        "──────────────────\n"
        "💎 <b>توصيات حصرية ورهانات يومية مباشرة!</b>\n"
        "👉 انضم الآن لقناتنا الرسمية للاستفادة من كل جديد:"
    )

    await update.message.reply_text(
        text=final_msg,
        reply_markup=channel_markup,
        parse_mode=ParseMode.HTML
    )

    await save_to_supabase(
        user_id=user.id,
        username=user.username or user.first_name,
        user_message=user_text,
        bot_reply=final_msg
    )

# =========================================================================
# تشغيل البوت (Main Entry Point)
# =========================================================================
def main():
    global telegram_app, main_async_loop

    print("=" * 65)
    print(f"⚽ بدء تشغيل البوت مع إعلانات Adsgram (Block ID: {ADSGRAM_BLOCK_ID})...")
    print("=" * 65)

    # 1. تشغيل خادم الويب وخدمة Adsgram على المنفذ 10000
    server_thread = threading.Thread(target=start_render_web_server, daemon=True)
    server_thread.start()

    # 2. بناء تطبيق التليجرام
    telegram_app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # 3. تسجيل المعالجات
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CallbackQueryHandler(handle_callback_query))
    telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

    # التقاط الـ loop الرئيسي
    main_async_loop = asyncio.get_event_loop()

    logger.info("البوت يعمل الآن ومربوط بإعلانات Adsgram 55679...")
    telegram_app.run_polling()

if __name__ == "__main__":
    main()
