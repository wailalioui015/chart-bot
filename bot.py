import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
import google.generativeai as genai
from PIL import Image
import io

# ============================================================
#  ضع مفاتيحك هنا فقط
# ============================================================
TELEGRAM_TOKEN  = 8672321476:AAFC8yVJAL82my3gJ2EwfSiKOuEfegG5_aQchart-bot
GEMINI_API_KEY  = AQ.Ab8RN6JVBqTWyDPHucOAygnH0nOEa2wsjqNq1GT_DwoovKyjjQ
# ============================================================

logging.basicConfig(level=logging.INFO)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# ============================================================
#  سيرفر صغير يخلي Render ما يوقفش البوت (keep-alive)
# ============================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass  # ما يطبعش logs زايدة

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()

def start_keep_alive():
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    print("✅ Keep-alive server شغال على port 8080")
# ============================================================

SYSTEM_PROMPT = """أنت خبير تحليل تقني محترف في الفوركس والكريبتو.
لما يرسلوليك صورة شارت، تحلل مباشرة وتعطي النتيجة بالدارجة المغاربية/الجزائرية.

فورمات ردك يكون هكذا دايمًا:

📊 *التحليل*
[وصف قصير شنو كيشوف الشارت: trend، نمط، مستويات مهمة]

📈 *الاتجاه*: [صاعد / هابط / جانبي]

✅ *إشارة*: [BUY / SELL / WAIT]

🎯 *TP1*: [السعر]
🎯 *TP2*: [السعر]
🛡️ *SL*: [السعر]

⚠️ *المخاطرة*: [منخفضة / متوسطة / عالية]

💡 *ملاحظة*: [نصيحة قصيرة بالدارجة]

إذا ما قدرتش تشوف الأسعار واضحة في الصورة، اشرح النمط بصح وقول للمستخدم يزيد الأسعار يدويًا حسب الشارت ديالو.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "السلام عليكم! 👋\n\n"
        "أنا بوت تحليل الشارتات ديالك 📊\n\n"
        "كيفاش تخدم:\n"
        "1️⃣ صوّر الشارت من أي منصة (Ninja, Exness, MT5...)\n"
        "2️⃣ ارسليه هنا\n"
        "3️⃣ نعطيك التحليل + TP1, TP2, SL في ثواني ⚡\n\n"
        "يلاه ابعث الشارت! 🚀"
    )

async def analyze_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ كنحلل الشارت... صبر شوية 🔍")
    try:
        photo = update.message.photo[-1]
        file  = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        image = Image.open(io.BytesIO(image_bytes))
        response = model.generate_content([SYSTEM_PROMPT, image])
        await msg.edit_text(response.text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(
            f"❌ كاين مشكل: {str(e)}\n"
            "عاود حاول وابعث الصورة مرة أخرى."
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 ابعثلي صورة الشارت باش نحللها ليك!\n"
        "ما نقدرش نحلل بدون صورة 😅"
    )

def main():
    start_keep_alive()  # يصحى البوت لوحده دايماً ✅
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, analyze_chart))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ البوت شغال 24/7 بـ Gemini Flash مجاناً!")
    app.run_polling()

if __name__ == "__main__":
    main()
