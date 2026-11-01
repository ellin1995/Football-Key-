import os
import logging
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً بك في بوت تحليل وتوقع المباريات الرياضية! ⚽🤖\n"
        "أرسل لي اسم أي مباراة أو فريقين (مثلاً: ريال مدريد ضد برشلونة) وسأقوم بتحليلها وتوقع النتيجة لك فوراً."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"

    prompt = f"أنت محلل رياضي وخبير في توقع نتائج المباريات. قم بتحليل وتوقع نتيجة المباراة التالية بناءً على طلب المستخدم: {user_message}. اذكر نسبة الفوز المتوقعة لكل فريق وتوقعاً منطقياً للنتيجة بشكل منظم ومبسط باللغة العربية."

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
        await update.message.reply_text("عذراً، حدث خطأ أثناء تحليل المباراة. يرجى المحاولة لاحقاً.")

if __name__ == '__main__':
    print("Initializing bot with Supabase integration...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot is running and listening for messages...")
    app.run_polling()
