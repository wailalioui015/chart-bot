import os
import logging
import threading
import base64
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

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

    models = [
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
    ]

    last_error = ""
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": SYSTEM_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}}
                ]
            }]
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            result = response.json()
            if "candidates" in result:
                return result["candidates"][0]["content"]["parts"][0]["text"]
            last_error = result.get("error", {}).get("message", str(result))
        except Exception as e:
            last_error = str(e)

    return f"⚠️ مشكل من Gemini: {last_error}"

@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message,
        "السلام عليكم! 👋\n\n"
        "أنا بوت تحليل الشارتات ديالك 📊\n\n"
        "ابعث صورة الشارت ونعطيك TP1, TP2, SL في ثواني ⚡"
    )

@bot.message_handler(content_types=["photo"])
def analyze_chart(message):
    msg = bot.reply_to(message, "⏳ كنحلل الشارت... صبر شوية 🔍")
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        image_bytes = bot.download_file(file_info.file_path)
        analysis = analyze_with_gemini(image_bytes)
        bot.edit_message_text(analysis, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ كاين مشكل: {str(e)}\nعاود حاول.", message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.reply_to(message, "📸 ابعثلي صورة الشارت باش نحللها!")

def main():
    start_keep_alive()
    print("✅ البوت شغال!")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
