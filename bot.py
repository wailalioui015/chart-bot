import os
import logging
import threading
import base64
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Updater, MessageHandler, CommandHandler, Filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def start_keep_alive():
    thread = threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8080), KeepAlive).serve_forever())
    thread.daemon = True
    thread.start()

SYSTEM_PROMPT = """أنت خبير تحليل تقني محترف في الفوركس والكريبتو.
لما يرسلوليك صورة شارت، تحلل مباشرة وتعطي النتيجة بالدارجة المغاربية/الجزائرية.

فورمات ردك يكون هكذا دايمًا:

📊 التحليل
[وصف قصير شنو كيشوف الشارت]

📈 الاتجاه: [صاعد / هابط / جانبي]

✅ إشارة: [BUY / SELL / WAIT]

🎯 TP1: [السعر]
🎯 TP2: [السعر]
🛡️ SL: [السعر]

⚠️ المخاطرة: [منخفضة / متوسطة / عالية]

💡 ملاحظة: [نصيحة قصيرة بالدارجة]
"""

def analyze_with_gemini(image_bytes):
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{
            "parts": [
                {"text": SYSTEM_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
            ]
        }]
    }
    response = requests.post(url, json=payload, timeout=30)
    result = response.json()
    return result["candidates"][0]["content"]["parts"][0]["text"]

def start(update, context):
    update.message.reply_text(
        "السلام عليكم! 👋\n\n"
        "أنا بوت تحليل الشارتات ديالك 📊\n\n"
        "ابعث صورة الشارت ونعطيك TP1, TP2, SL في ثواني ⚡"
    )

def analyze_chart(update, context):
    msg = update.message.reply_text("⏳ كنحلل الشارت... صبر شوية 🔍")
    try:
        photo = update.message.photo[-1]
        file = context.bot.get_file(photo.file_id)
        image_bytes = file.download_as_bytearray()
        analysis = analyze_with_gemini(bytes(image_bytes))
        msg.edit_text(analysis)
    except Exception as e:
        msg.edit_text(f"❌ كاين مشكل: {str(e)}\nعاود حاول.")

def handle_text(update, context):
    update.message.reply_text("📸 ابعثلي صورة الشارت باش نحللها!")

def main():
    start_keep_alive()
    print("✅ البوت شغال!")
    updater = Updater(TELEGRAM_TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.photo, analyze_chart))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
