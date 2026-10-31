import os
import logging
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

GEMINI_API_KEY = "05f1e429a91687bfe744f0910f408a59"
TELEGRAM_TOKEN = "9154832991:AAFn34ZAsOjkEhrRbnsKxfERbRLoC3fWdNw"

client = genai.Client(api_key=GEMINI_API_KEY)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    prompt = f"أنت محلل رياضي وخبير في توقع نتائج المباريات. قم بتحليل وتوقع نتيجة المباراة التالية بناءً على طلب المستخدم: {user_message}. اذكر نسبة الفوز المتوقعة لكل فريق وتوقعاً منطقياً للنتيجة بشكل منظم ومبسط باللغة العربية."
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("عذراً، حدث خطأ أثناء تحليل المباراة. يرجى المحاولة لاحقاً.")

if __name__ == '__main__':
    print("Initializing bot...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("Bot is running and listening for messages...")
    app.run_polling()
