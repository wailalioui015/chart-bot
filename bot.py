import os
import logging
import threading
import base64
import requests
import json
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# قاعدة بيانات في الذاكرة
# ============================================================
user_data = {}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {
            "journal": [],
            "stats": {"win": 0, "loss": 0, "wait": 0},
            "balance": 1000.0,
            "risk_percent": 2.0,
            "alerts": False,
            "multi_charts": [],
        }
    return user_data[uid]

# ============================================================
# Keep Alive
# ============================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ChartSniperBot v4.0 Pro")
    def log_message(self, format, *args):
        pass

def start_keep_alive():
    t = threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8080), KeepAlive).serve_forever())
    t.daemon = True
    t.start()

# ============================================================
# Prompt احترافي
# ============================================================
SYSTEM_PROMPT = """أنت خبير تحليل تقني محترف ومتخصص في أسواق الفوركس والكريبتو والذهب.
لديك خبرة عميقة في قراءة الشارتات وأنماط الشموع اليابانية ومستويات الدعم والمقاومة.

عند تحليل أي شارت، اتبع هذه الخطوات بدقة:
1. حدد نمط الشموع (Pin Bar, Engulfing, Doji, Inside Bar, الخ)
2. حدد الاتجاه العام من خلال الهيكل السعري
3. حدد أقرب مستوى دعم ومقاومة
4. لا تعطِ إشارة إلا إذا كان التأكيد واضحاً
5. احسب نسبة المخاطرة/الربح (R:R) ولا تدخل إذا كانت أقل من 1:2
6. اذكر الـ Timeframe إذا كان ظاهراً في الشارت
7. أعطِ قوة الإشارة من 10

قواعد صارمة:
- إذا كان السوق غير واضح، قل WAIT
- SL يجب أن يكون خلف أقرب مستوى دعم/مقاومة
- نسبة R:R لا تقل عن 1:2

الرد باللغة العربية الفصحى فقط، وبهذا الفورمات:

📊 **التحليل الفني**
[وصف دقيق للشارت]

📈 **الاتجاه العام**: [صاعد / هابط / جانبي]

🕯️ **نمط الشموع**: [اسم النمط]

✅ **الإشارة**: [BUY / SELL / WAIT]

💪 **قوة الإشارة**: [X/10]

🎯 **TP1**: [السعر]
🎯 **TP2**: [السعر]
🛡️ **SL**: [السعر]

⚖️ **نسبة R:R**: [مثال: 1:2.5]

⚠️ **مستوى المخاطرة**: [منخفض / متوسط / عالٍ]

💡 **توصية**: [نصيحة احترافية مختصرة]
"""

MULTI_PROMPT = """أنت خبير تحليل تقني محترف. لديك صورتان أو أكثر لنفس الزوج في إطارات زمنية مختلفة.
حلل كل إطار وأعطِ رأياً موحداً نهائياً.

الرد باللغة العربية الفصحى وبهذا الفورمات:

📊 **تحليل متعدد الإطارات**

🔵 **الإطار الكبير (HTF)**:
[التحليل]

🟡 **الإطار الصغير (LTF)**:
[التحليل]

✅ **الإشارة النهائية**: [BUY / SELL / WAIT]
💪 **قوة الإشارة**: [X/10]
🎯 **TP1**: [السعر]
🎯 **TP2**: [السعر]
🛡️ **SL**: [السعر]
⚖️ **نسبة R:R**: [مثال: 1:2.5]
💡 **توصية**: [نصيحة احترافية]
"""

# ============================================================
# الموديلات
# ============================================================
def analyze_with_groq(images_b64, prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    content = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    payload = {
        "model": "qwen/qwen3.8-27b",
        "max_tokens": 900,
        "messages": [{"role": "user", "content": content}]
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    result = response.json()
    if "choices" in result:
        return result["choices"][0]["message"]["content"]
    raise Exception(result.get("error", {}).get("message", str(result)))

def analyze_with_openrouter(images_b64, prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chart-bot-gnm5.onrender.com",
        "X-Title": "ChartSniperBot"
    }
    content = [{"type": "text", "text": prompt}]
    for img in images_b64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    payload = {
        "model": "google/gemini-2.5-flash-preview:free",
        "max_tokens": 900,
        "messages": [{"role": "user", "content": content}]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
    result = response.json()
    if "choices" in result:
        return result["choices"][0]["message"]["content"]
    raise Exception(result.get("error", {}).get("message", str(result)))

def analyze_images(images_bytes_list, multi=False):
    prompt = MULTI_PROMPT if multi else SYSTEM_PROMPT
    images_b64 = [base64.b64encode(img).decode("utf-8") for img in images_bytes_list]
    try:
        return analyze_with_groq(images_b64, prompt)
    except Exception as e1:
        logging.warning(f"Groq فشل: {e1}")
    try:
        return analyze_with_openrouter(images_b64, prompt)
    except Exception as e2:
        logging.warning(f"OpenRouter فشل: {e2}")
    return "⚠️ عذراً، تعذر التحليل حالياً. يرجى المحاولة مرة أخرى."

# ============================================================
# إدارة رأس المال
# ============================================================
def calc_position_size(balance, risk_percent, sl_pips):
    risk_amount = balance * (risk_percent / 100)
    if sl_pips <= 0:
        return 0.01
    lot_size = round(risk_amount / (sl_pips * 10), 2)
    return max(0.01, min(lot_size, 10.0))

# ============================================================
# أخبار الفوركس
# ============================================================
def get_forex_news():
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        response = requests.get(url, timeout=10)
        data = response.json()
        high_impact = [e for e in data if e.get("impact") == "High"][:6]
        if not high_impact:
            return "✅ لا توجد أخبار عالية التأثير هذا الأسبوع."
        news_text = "📰 *أهم الأخبار الاقتصادية هذا الأسبوع:*\n\n"
        for event in high_impact:
            news_text += f"🔴 *{event.get('title', '')}*\n"
            news_text += f"   🌍 {event.get('country', '')} | 📅 {event.get('date', '')}\n\n"
        return news_text
    except:
        return "⚠️ تعذر جلب الأخبار حالياً."

# ============================================================
# تنبيهات يومية تلقائية
# ============================================================
def daily_alert_job():
    while True:
        now = datetime.now()
        if now.hour == 8 and now.minute == 0:
            news = get_forex_news()
            for uid, data in user_data.items():
                if data.get("alerts"):
                    try:
                        bot.send_message(uid,
                            f"🌅 *صباح الخير! تنبيهك اليومي:*\n\n{news}",
                            parse_mode="Markdown"
                        )
                    except:
                        pass
            time.sleep(61)
        time.sleep(30)

def start_daily_alerts():
    t = threading.Thread(target=daily_alert_job)
    t.daemon = True
    t.start()

# ============================================================
# الكيبورد
# ============================================================
def get_main_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 تحليل شارت واحد", "📊📊 تحليل متعدد الإطارات")
    kb.row("📰 الأخبار", "💰 إدارة رأس المال")
    kb.row("📓 سجل صفقاتي", "📈 إحصائياتي")
    kb.row("🔔 التنبيهات", "ℹ️ مساعدة")
    return kb

# ============================================================
# الأوامر
# ============================================================
@bot.message_handler(commands=["start"])
def start(message):
    uid = message.from_user.id
    get_user(uid)
    bot.reply_to(message,
        "السلام عليكم ورحمة الله! 👋\n\n"
        "أنا *ChartSniperBot* 🎯\n"
        "_Analyze • Snipe • Profit_\n\n"
        "📌 *الميزات الجديدة v4.0 Pro:*\n"
        "✅ تحليل شارت واحد\n"
        "✅ تحليل متعدد الإطارات (HTF+LTF)\n"
        "✅ قوة الإشارة من 10\n"
        "✅ إدارة رأس المال (حجم اللوت)\n"
        "✅ أخبار الفوركس اليومية\n"
        "✅ تنبيهات صباحية تلقائية\n"
        "✅ جورنال وإحصائيات\n\n"
        "اختر من القائمة 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ============================================================
# معالجة الأزرار
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📊 تحليل شارت واحد")
def single_mode(message):
    uid = message.from_user.id
    get_user(uid)["multi_charts"] = []
    bot.reply_to(message, "📸 أرسل صورة الشارت وسأحللها فوراً!")

@bot.message_handler(func=lambda m: m.text == "📊📊 تحليل متعدد الإطارات")
def multi_mode(message):
    uid = message.from_user.id
    get_user(uid)["multi_charts"] = []
    bot.reply_to(message,
        "📊 *وضع التحليل المتعدد*\n\n"
        "أرسل صورتين:\n"
        "1️⃣ الإطار الكبير (H1 أو H4 أو D1)\n"
        "2️⃣ الإطار الصغير (M15 أو M5)\n\n"
        "سأحللهما معاً وأعطيك تأكيداً أقوى! 💪",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "📰 الأخبار")
def news_button(message):
    msg = bot.reply_to(message, "⏳ جارٍ جلب الأخبار...")
    news = get_forex_news()
    bot.edit_message_text(news, message.chat.id, msg.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 إدارة رأس المال")
def capital_button(message):
    uid = message.from_user.id
    user = get_user(uid)
    bot.reply_to(message,
        f"💰 *إدارة رأس المال*\n\n"
        f"💵 رأس المال الحالي: *{user['balance']}$*\n"
        f"⚠️ نسبة المخاطرة: *{user['risk_percent']}%*\n\n"
        f"لتغيير رأس المال: أرسل\n`/balance 5000`\n\n"
        f"لتغيير نسبة المخاطرة: أرسل\n`/risk 1`",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "🔔 التنبيهات")
def alerts_button(message):
    uid = message.from_user.id
    user = get_user(uid)
    status = "مفعّلة ✅" if user["alerts"] else "معطّلة ❌"
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ تفعيل", callback_data="alert_on"),
        types.InlineKeyboardButton("❌ إيقاف", callback_data="alert_off")
    )
    bot.reply_to(message,
        f"🔔 *التنبيهات الصباحية*\n\n"
        f"الحالة: {status}\n\n"
        f"عند التفعيل، ستصلك أهم الأخبار الاقتصادية كل يوم الساعة 8 صباحاً 🌅",
        parse_mode="Markdown",
        reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "📈 إحصائياتي")
def stats_button(message):
    uid = message.from_user.id
    user = get_user(uid)
    stats = user["stats"]
    total = stats["win"] + stats["loss"]
    rate = round((stats["win"] / total * 100), 1) if total > 0 else 0
    bot.reply_to(message,
        f"📈 *إحصائياتك*\n\n"
        f"✅ صفقات رابحة: *{stats['win']}*\n"
        f"❌ صفقات خاسرة: *{stats['loss']}*\n"
        f"⏸️ انتظار: *{stats['wait']}*\n"
        f"📊 الإجمالي: *{total}*\n"
        f"🎯 نسبة النجاح: *{rate}%*\n\n"
        f"💵 رأس المال: *{user['balance']}$*",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "📓 سجل صفقاتي")
def journal_button(message):
    uid = message.from_user.id
    journal = get_user(uid)["journal"]
    if not journal:
        bot.reply_to(message, "📓 سجل صفقاتك فارغ.\nأرسل شارتاً للبدء!")
        return
    text = "📓 *آخر 5 صفقات:*\n\n"
    for trade in journal[-5:]:
        emoji = "✅" if trade["result"] == "win" else "❌" if trade["result"] == "loss" else "⏸️"
        text += f"{emoji} {trade['signal']} — {trade['date']}\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "ℹ️ مساعدة")
def help_button(message):
    bot.reply_to(message,
        "📖 *دليل الاستخدام v4.0*\n\n"
        "📊 *تحليل شارت واحد*\n"
        "أرسل صورة شارت مباشرة\n\n"
        "📊📊 *تحليل متعدد الإطارات*\n"
        "أرسل صورتين (HTF + LTF) للتأكيد\n\n"
        "💰 *إدارة رأس المال*\n"
        "`/balance 5000` — تعيين رأس المال\n"
        "`/risk 2` — تعيين نسبة المخاطرة\n"
        "`/lot 20` — حساب حجم اللوت (بـ pips)\n\n"
        "🔔 *التنبيهات الصباحية*\n"
        "فعّل لتصلك الأخبار كل يوم 8 صباحاً\n\n"
        "⚠️ التحليل للأغراض التعليمية فقط.",
        parse_mode="Markdown"
    )

# ============================================================
# أوامر إدارة رأس المال
# ============================================================
@bot.message_handler(commands=["balance"])
def set_balance(message):
    uid = message.from_user.id
    try:
        amount = float(message.text.split()[1])
        get_user(uid)["balance"] = amount
        bot.reply_to(message, f"✅ تم تعيين رأس المال: *{amount}$*", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ الاستخدام الصحيح: `/balance 5000`", parse_mode="Markdown")

@bot.message_handler(commands=["risk"])
def set_risk(message):
    uid = message.from_user.id
    try:
        percent = float(message.text.split()[1])
        get_user(uid)["risk_percent"] = percent
        bot.reply_to(message, f"✅ تم تعيين نسبة المخاطرة: *{percent}%*", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ الاستخدام الصحيح: `/risk 2`", parse_mode="Markdown")

@bot.message_handler(commands=["lot"])
def calc_lot(message):
    uid = message.from_user.id
    try:
        sl_pips = float(message.text.split()[1])
        user = get_user(uid)
        lot = calc_position_size(user["balance"], user["risk_percent"], sl_pips)
        risk_amount = user["balance"] * (user["risk_percent"] / 100)
        bot.reply_to(message,
            f"💰 *حجم اللوت المناسب*\n\n"
            f"💵 رأس المال: *{user['balance']}$*\n"
            f"⚠️ المخاطرة: *{user['risk_percent']}%* = *{risk_amount}$*\n"
            f"📏 SL: *{sl_pips} pips*\n"
            f"📊 حجم اللوت: *{lot} lot*",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(message, "❌ الاستخدام الصحيح: `/lot 20` (عدد pips الـ SL)", parse_mode="Markdown")

# ============================================================
# Callbacks
# ============================================================
@bot.callback_query_handler(func=lambda c: c.data in ["alert_on", "alert_off"])
def handle_alerts(call):
    uid = call.from_user.id
    get_user(uid)["alerts"] = (call.data == "alert_on")
    status = "مفعّلة ✅" if call.data == "alert_on" else "معطّلة ❌"
    bot.answer_callback_query(call.id, f"التنبيهات {status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("win_") or c.data.startswith("loss_"))
def handle_trade_result(call):
    parts = call.data.split("_")
    result = parts[0]
    uid = int(parts[1])
    user = get_user(uid)
    if user["journal"]:
        user["journal"][-1]["result"] = result
        if result == "win":
            user["stats"]["win"] += 1
        else:
            user["stats"]["loss"] += 1
        if user["stats"]["wait"] > 0:
            user["stats"]["wait"] -= 1
    emoji = "✅ رابحة!" if result == "win" else "❌ خاسرة."
    bot.answer_callback_query(call.id, f"تم تسجيل الصفقة {emoji}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# ============================================================
# تحليل الصور
# ============================================================
@bot.message_handler(content_types=["photo"])
def analyze_chart(message):
    uid = message.from_user.id
    user = get_user(uid)
    multi_charts = user["multi_charts"]

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    image_bytes = bot.download_file(file_info.file_path)

    # وضع التحليل المتعدد
    if len(multi_charts) == 0 and message.caption and "multi" in message.caption.lower():
        multi_charts.append(image_bytes)
        bot.reply_to(message, "✅ تم استلام الصورة الأولى!\nأرسل الصورة الثانية الآن 📸")
        return

    if len(multi_charts) == 1:
        multi_charts.append(image_bytes)
        msg = bot.reply_to(message, "⏳ جارٍ تحليل الإطارين معاً... 🔍")
        try:
            analysis = analyze_images(multi_charts, multi=True)
            user["multi_charts"] = []
            signal = "WAIT"
            if "BUY" in analysis.upper(): signal = "BUY"
            elif "SELL" in analysis.upper(): signal = "SELL"
            user["journal"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "signal": signal, "result": "wait"})
            if signal == "WAIT": user["stats"]["wait"] += 1
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("✅ رابحة", callback_data=f"win_{uid}"),
                types.InlineKeyboardButton("❌ خاسرة", callback_data=f"loss_{uid}")
            )
            bot.edit_message_text(analysis + "\n\n_سجّل نتيجة صفقتك:_", message.chat.id, msg.message_id, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ: {str(e)}", message.chat.id, msg.message_id)
        return

    # تحليل شارت واحد
    msg = bot.reply_to(message, "⏳ جارٍ تحليل الشارت... يرجى الانتظار 🔍")
    try:
        analysis = analyze_images([image_bytes])
        signal = "WAIT"
        if "BUY" in analysis.upper(): signal = "BUY"
        elif "SELL" in analysis.upper(): signal = "SELL"
        user["journal"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "signal": signal, "result": "wait"})
        if signal == "WAIT": user["stats"]["wait"] += 1

        # حساب حجم اللوت تلقائياً
        lot_info = ""
        if user["balance"] > 0:
            lot = calc_position_size(user["balance"], user["risk_percent"], 20)
            lot_info = f"\n\n💰 *حجم اللوت المقترح*: {lot} lot\n_(بناءً على {user['risk_percent']}% مخاطرة من {user['balance']}$)_"

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ رابحة", callback_data=f"win_{uid}"),
            types.InlineKeyboardButton("❌ خاسرة", callback_data=f"loss_{uid}")
        )
        bot.edit_message_text(
            analysis + lot_info + "\n\n_سجّل نتيجة صفقتك:_",
            message.chat.id, msg.message_id,
            parse_mode="Markdown", reply_markup=markup
        )
    except Exception as e:
        bot.edit_message_text(f"❌ حدث خطأ: {str(e)}\nالرجاء المحاولة مرة أخرى.", message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.reply_to(message, "📸 أرسل لي صورة الشارت!\n\nاكتب /start للقائمة الرئيسية", reply_markup=get_main_keyboard())

def main():
    start_keep_alive()
    start_daily_alerts()
    print("✅ ChartSniperBot v4.0 Pro شغال!")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
