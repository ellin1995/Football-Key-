import os
import logging
import threading
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from google import genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
from supabase import create_client, Client

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

GEMINI_API_KEY = "05f1e429a91687bfe744f0910f408a59"
TELEGRAM_TOKEN = "9154832991:AAFn34ZAsOjkEhrRbnsKxfERbRLoC3fWdNw"

SUPABASE_URL = "https://ddywqmupodubrwlaflem.supabase.co"
SUPABASE_KEY = "sb_publishable_r1wS_YGGkexuVtRvvBy40Q_Qm-i672h"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = genai.Client(api_key=GEMINI_API_KEY)

# خادم الويب المصغر لإرضاء Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Football Prediction Bot is active!")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

# جلب مباريات الدوريات الكبرى فقط (يمكنك ربطها بـ API رياضي حقيقي لاحقاً)
def get_major_leagues_matches():
    # فلترة مخصصة لأبرز مباريات الدوريات الكبرى (إنجليزي، إسباني، إيطالي، ألماني، أبطال أوروبا)
    matches = [
        {"name": "🇪🇸 ريال مدريد ضد برشلونة (الدوري الإسباني)", "id": "Real Madrid vs Barcelona La Liga"},
        {"name": "🇬🇧 مانشستر سيتي ضد أرسنال (الدوري الإنجليزي)", "id": "Manchester City vs Arsenal Premier League"},
        {"name": "🇮🇹 إنتر ميلان ضد يوفنتوس (الدوري الإيطالي)", "id": "Inter Milan vs Juventus Serie A"},
        {"name": "🇩🇪 بايرن ميونخ ضد دورتموند (الدوري الألماني)", "id": "Bayern Munich vs Dortmund Bundesliga"},
        {"name": "🇪🇺 ريال مدريد ضد باريس سان جيرمان (دوري الأبطال)", "id": "Real Madrid vs PSG UEFA Champions League"}
    ]
    return matches

# أمر /start لعرض قائمة الدوريات الكبرى
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = get_major_leagues_matches()
    keyboard = []
    
    for match in matches:
        keyboard.append([InlineKeyboardButton(match['name'], callback_data=match['id'])])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🏆 **أهلاً بك في بوت توقعات الدوريات الكبرى!**\n"
        "اختر مباراة من القائمة أدناه لتحليلها بدقة عبر الذكاء الاصطناعي، أو أرسل اسم أي مباراة أخرى:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# معالجة الضغط على أزرار المباريات
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_message = query.data
    user_id = query.effective_user.id
    username = query.effective_user.username or "Unknown"
    
    await query.message.reply_text(f"⏳ جاري تحليل مباراة: {user_message}...")
    
    prompt = f"أنت محلل رياضي خبير في الدوريات الكبرى. قم بتحليل وتوقع نتيجة المباراة التالية بدقة: {user_message}. اذكر نسب الفوز المتوقعة والتحليل الفني باختصار باللغة العربية."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        bot_reply = response.text
        
        try:
            supabase.table("predictions").insert({
                "user_id": str(user_id),
                "username": username,
                "user_message": user_message,
                "bot_reply": bot_reply
            }).execute()
        except Exception as db_err:
            print(f"Supabase Error: {db_err}")

        await query.message.reply_text(bot_reply)
        
    except Exception as e:
        print(f"Error: {e}")
        await query.message.reply_text("عذراً، حدث خطأ أثناء تحليل المباراة.")

# معالجة النصوص العادية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    
    prompt = f"أنت محلل رياضي خبير في الدوريات الكبرى. قم بتحليل وتوقع نتيجة المباراة بناءً على طلب المستخدم: {user_message}. اذكر نسبة الفوز والتحليل الفني باللغة العربية."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        bot_reply = response.text
        
        try:
            supabase.table("predictions").insert({
                "user_id": str(user_id),
                "username": username,
                "user_message": user_message,
                "bot_reply": bot_reply
            }).execute()
        except Exception as db_err:
            print(f"Supabase Error: {db_err}")

        await update.message.reply_text(bot_reply)
        
    except Exception as e:
        print(f"Error: {e}")
        await query.message.reply_text("عذراً، حدث خطأ أثناء تحليل المباراة.")

if __name__ == '__main__':
    threading.Thread(target=run_web, daemon=True).start()
    
    print("Initializing bot with Major Leagues & Supabase...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running...")
    app.run_polling()
