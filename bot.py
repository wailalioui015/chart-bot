import os
import logging
import threading
import base64
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

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

def analyze_with_openrouter(image_bytes):
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chart-bot-gnm5.onrender.com",
        "X-Title": "ChartSniperBot"
    }
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": SYSTEM_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }
        ]
    }
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=30
    )
    
    result = response.json()
    
    if "choices" in result:
        return result["choices"][0]["message"]["content"]
    
    error = result.get("error", {}).get("message", str(result))
    return f"⚠️ مشكل: {error}"

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
        analysis = analyze_with_openrouter(image_bytes)
        bot.edit_message_text(analysis, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ كاين مشكل: {str(e)}\nعاود حاول.", message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.reply_to(message, "📸 ابعثلي صورة الشارت باش نحللها!")

def main():
    start_keep_alive()
    print("✅ البوت شغال مع OpenRouter!")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
