import os
import logging
import threading
import base64
import requests
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

TELEGRAM_TOKEN    = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY")
OPENROUTER_API_KEY= os.environ.get("OPENROUTER_API_KEY")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY")
TWELVEDATA_API_KEY= os.environ.get("TWELVEDATA_API_KEY")

logging.basicConfig(level=logging.INFO)
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ============================================================
# قاعدة بيانات
# ============================================================
user_data = {}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {
            "journal": [], "stats": {"win": 0, "loss": 0, "wait": 0},
            "balance": 1000.0, "risk_percent": 2.0,
            "alerts": False, "multi_charts": [], "weekly_signals": [],
        }
    return user_data[uid]

# ============================================================
# Keep Alive
# ============================================================
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ChartSniperBot v6.0 Ultra")
    def log_message(self, f, *a): pass

def start_keep_alive():
    t = threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8080), KeepAlive).serve_forever())
    t.daemon = True; t.start()

# ============================================================
# جلب السعر الحي من TwelveData
# ============================================================
def get_live_price(symbol="EUR/USD"):
    try:
        url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVEDATA_API_KEY}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if "price" in data:
            return float(data["price"])
    except:
        pass
    return None

def get_market_info(symbol="EUR/USD"):
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={TWELVEDATA_API_KEY}"
        r = requests.get(url, timeout=8)
        data = r.json()
        if "close" in data:
            close = float(data["close"])
            open_ = float(data["open"])
            high  = float(data["high"])
            low   = float(data["low"])
            change= round(close - open_, 5)
            pct   = round((change / open_) * 100, 2)
            arrow = "📈" if change >= 0 else "📉"
            return (
                f"💹 *{symbol} — السعر الحي*\n\n"
                f"💰 السعر الحالي: *{close}*\n"
                f"📂 الافتتاح: *{open_}*\n"
                f"⬆️ الأعلى: *{high}*\n"
                f"⬇️ الأدنى: *{low}*\n"
                f"{arrow} التغيير: *{change:+.5f}* ({pct:+.2f}%)"
            )
    except:
        pass
    return "⚠️ تعذر جلب السعر حالياً."

# ============================================================
# ULTRA PROMPT
# ============================================================
SYSTEM_PROMPT = """أنت محلل تقني خبير من المستوى الاحترافي، متخصص في أسواق الفوركس والكريبتو والذهب والمؤشرات.
لديك خبرة 20 سنة في قراءة الشارتات، وتحليل أنماط الشموع اليابانية، ومستويات الدعم والمقاومة.

══════════════════════════════
🔍 منهجية التحليل الاحترافي:
══════════════════════════════

الخطوة 1 — قراءة السياق العام:
• حدد الزوج والإطار الزمني من الشارت
• حدد الاتجاه العام (Uptrend / Downtrend / Sideways)
• حدد هيكل السوق: Higher Highs / Lower Lows
• هل السوق في Trend أم Range؟

الخطوة 2 — مستويات الدعم والمقاومة:
• حدد أقوى مستويات الدعم والمقاومة الظاهرة
• حدد مناطق القيمة العادلة (Fair Value Zones)
• حدد المناطق النفسية (مثل 1.1000، 1.1500)
• هل كسر السعر مستوى مهم؟ (Breakout / Breakdown)

الخطوة 3 — تحليل الشموع اليابانية:
• حدد النمط بدقة: Pin Bar / Engulfing / Doji / Inside Bar / Morning Star / Evening Star / Hammer / Shooting Star
• ما هي قوة الشمعة؟ (جسم كبير = إشارة قوية)
• هل الشمعة عند مستوى مهم؟ (الشمعة عند الدعم أو المقاومة = تأكيد)
• ما هو الظل (Wick)؟ ظل طويل = رفض قوي

الخطوة 4 — المؤشرات المرئية:
• هل هناك تقاطع المتوسطات المتحركة (MA Cross)؟
• هل هناك تباعد في الزخم (Momentum Divergence)؟
• هل هناك Overbought / Oversold؟
• هل هناك Order Blocks أو Fair Value Gaps؟

الخطوة 5 — تحديد نقاط الدخول والخروج:
• نقطة الدخول: عند أفضل سعر مع أقل مخاطرة
• TP1: أول هدف محافظ (R:R = 1:1.5 على الأقل)
• TP2: هدف موسع (R:R = 1:3 على الأقل)
• SL: خلف آخر قمة أو قاع + 5-10 pips أمان

الخطوة 6 — تقييم الإشارة من 10:
• توافق مع الاتجاه العام: +3
• شمعة عند مستوى مهم: +2
• نمط واضح وقوي: +2
• R:R ≥ 1:2: +2
• حجم يؤكد: +1

قواعد صارمة:
❌ لا تدخل ضد الاتجاه إلا بتأكيد قوي جداً
❌ لا تعطِ إشارة إذا R:R أقل من 1:2
❌ إذا الشارت غير واضح قل WAIT

الرد باللغة العربية الفصحى فقط بهذا الفورمات:

━━━━━━━━━━━━━━━━━━━━━━
📊 **التحليل الشامل**
━━━━━━━━━━━━━━━━━━━━━━

🔍 **قراءة الشارت:**
[الزوج والإطار الزمني — الاتجاه العام — هيكل السوق]

📐 **الدعم والمقاومة:**
• مقاومة: [السعر]
• دعم: [السعر]

🕯️ **نمط الشموع:** [الاسم بالعربية والإنجليزية]

📈 **الاتجاه العام:** [صاعد 📈 / هابط 📉 / جانبي ↔️]

━━━━━━━━━━━━━━━━━━━━━━
✅ **الإشارة:** [BUY 🟢 / SELL 🔴 / WAIT ⏸️]
━━━━━━━━━━━━━━━━━━━━━━

💪 **قوة الإشارة:** [X/10] [██████░░░░]

🎯 **نقطة الدخول:** [السعر]
🎯 **TP1:** [السعر] ([+X pips])
🎯 **TP2:** [السعر] ([+X pips])
🛡️ **SL:** [السعر] ([-X pips])

⚖️ **نسبة R:R:** [1:X]

⚠️ **مستوى المخاطرة:** [منخفض 🟢 / متوسط 🟡 / عالٍ 🔴]

💡 **التوصية الاحترافية:**
[لماذا هذه الإشارة؟ ما الذي يجب مراقبته؟ متى تخرج مبكراً؟]

⚡ **ملاحظة:** [أي معلومة إضافية مهمة]
"""

MULTI_PROMPT = """أنت محلل تقني خبير. لديك صورتان لنفس الزوج في إطارين زمنيين مختلفين.
حلل كل إطار بعمق ثم أعطِ رأياً موحداً نهائياً.

الرد باللغة العربية الفصحى بهذا الفورمات:

━━━━━━━━━━━━━━━━━━━━━━
📊 **تحليل متعدد الإطارات**
━━━━━━━━━━━━━━━━━━━━━━

🔵 **الإطار الكبير (HTF):**
• الاتجاه: [صاعد / هابط / جانبي]
• الدعم والمقاومة: [المستويات]
• النمط: [النمط الظاهر]
• الملاحظة: [التحليل]

🟡 **الإطار الصغير (LTF):**
• الاتجاه: [صاعد / هابط / جانبي]
• نمط الشموع: [النمط]
• نقطة الدخول: [السعر]
• الملاحظة: [التحليل]

🔄 **توافق الإطارين:** [متوافقان ✅ / متعارضان ⚠️]

━━━━━━━━━━━━━━━━━━━━━━
✅ **الإشارة النهائية:** [BUY 🟢 / SELL 🔴 / WAIT ⏸️]
━━━━━━━━━━━━━━━━━━━━━━

💪 **قوة الإشارة:** [X/10] [██████░░░░]
🎯 **TP1:** [السعر]
🎯 **TP2:** [السعر]
🛡️ **SL:** [السعر]
⚖️ **نسبة R:R:** [1:X]
💡 **التوصية النهائية:** [تحليل شامل]
"""

# ============================================================
# الموديلات الثلاثة
# ============================================================
def analyze_with_groq(imgs, prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    content = [{"type": "text", "text": prompt}]
    for img in imgs:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    payload = {"model": "qwen/qwen3.8-27b", "max_tokens": 900, "messages": [{"role": "user", "content": content}]}
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
    res = r.json()
    if "choices" in res: return res["choices"][0]["message"]["content"]
    raise Exception(res.get("error", {}).get("message", str(res)))

def analyze_with_gemini(imgs, prompt):
    parts = [{"text": prompt}]
    for img in imgs:
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img}})
    payload = {"contents": [{"parts": parts}]}
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json=payload, timeout=30)
    res = r.json()
    if "candidates" in res: return res["candidates"][0]["content"]["parts"][0]["text"]
    raise Exception(res.get("error", {}).get("message", str(res)))

def analyze_with_openrouter(imgs, prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chart-bot-gnm5.onrender.com",
        "X-Title": "ChartSniperBot"
    }
    content = [{"type": "text", "text": prompt}]
    for img in imgs:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}})
    payload = {"model": "google/gemini-2.5-flash-preview:free", "max_tokens": 900, "messages": [{"role": "user", "content": content}]}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
    res = r.json()
    if "choices" in res: return res["choices"][0]["message"]["content"]
    raise Exception(res.get("error", {}).get("message", str(res)))

def analyze_images(images_bytes_list, multi=False):
    prompt = MULTI_PROMPT if multi else SYSTEM_PROMPT
    imgs_b64 = [base64.b64encode(img).decode("utf-8") for img in images_bytes_list]
    # جرب الموديلات بالترتيب
    for name, func in [("Groq", analyze_with_groq), ("Gemini", analyze_with_gemini), ("OpenRouter", analyze_with_openrouter)]:
        try:
            result = func(imgs_b64, prompt)
            logging.info(f"✅ نجح {name}")
            return result
        except Exception as e:
            logging.warning(f"❌ {name} فشل: {e}")
    return "⚠️ عذراً، تعذر التحليل حالياً. يرجى المحاولة مرة أخرى."

# ============================================================
# إدارة رأس المال
# ============================================================
def calc_lot(balance, risk_pct, sl_pips):
    risk = balance * (risk_pct / 100)
    if sl_pips <= 0: return 0.01
    return max(0.01, min(round(risk / (sl_pips * 10), 2), 10.0))

# ============================================================
# أخبار الفوركس
# ============================================================
def get_forex_news():
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        data = r.json()
        high = [e for e in data if e.get("impact") == "High"][:6]
        if not high: return "✅ لا توجد أخبار عالية التأثير هذا الأسبوع."
        text = "📰 *أهم الأخبار الاقتصادية هذا الأسبوع:*\n\n"
        for e in high:
            text += f"🔴 *{e.get('title','')}*\n   🌍 {e.get('country','')} | 📅 {e.get('date','')}\n\n"
        return text
    except:
        return "⚠️ تعذر جلب الأخبار حالياً."

# ============================================================
# التقرير الأسبوعي
# ============================================================
def get_weekly_report(uid):
    u = get_user(uid)
    s = u["stats"]
    total = s["win"] + s["loss"]
    rate = round(s["win"] / total * 100, 1) if total > 0 else 0
    sigs = u.get("weekly_signals", [])
    perf = "🏆 ممتاز" if rate >= 70 else "👍 جيد" if rate >= 50 else "⚠️ يحتاج تحسين"
    return (
        f"📊 *التقرير الأسبوعي*\n━━━━━━━━━━━━━\n\n"
        f"✅ رابحة: *{s['win']}* | ❌ خاسرة: *{s['loss']}* | ⏸️ انتظار: *{s['wait']}*\n"
        f"📊 الإجمالي: *{total}* | 🎯 النجاح: *{rate}%*\n\n"
        f"📈 BUY: *{sigs.count('BUY')}* | 📉 SELL: *{sigs.count('SELL')}* | ⏸️ WAIT: *{sigs.count('WAIT')}*\n\n"
        f"💵 رأس المال: *{u['balance']}$* | ⚠️ المخاطرة: *{u['risk_percent']}%*\n\n"
        f"🏅 التقييم: {perf}"
    )

# ============================================================
# تنبيهات السيشن
# ============================================================
def session_alerts_job():
    while True:
        now = datetime.now()
        h, m = now.hour, now.minute
        for uid, data in user_data.items():
            if not data.get("alerts"): continue
            try:
                if h == 8 and m == 0:
                    bot.send_message(uid, f"🌅 *صباح الخير!*\n\n{get_forex_news()}", parse_mode="Markdown")
                if h == 10 and m == 0:
                    bot.send_message(uid, "🇬🇧 *سيشن لندن فُتح!*\n\n⚡ أعلى تقلبات الآن\n📊 GBPUSD, EURUSD, EURGBP", parse_mode="Markdown")
                if h == 15 and m == 0:
                    bot.send_message(uid, "🇺🇸 *سيشن نيويورك فُتح!*\n\n⚡ تقلبات عالية مع أوروبا\n📊 EURUSD, GBPUSD, USDJPY", parse_mode="Markdown")
            except: pass
        time.sleep(59)

def start_session_alerts():
    t = threading.Thread(target=session_alerts_job)
    t.daemon = True; t.start()

# ============================================================
# الكيبورد
# ============================================================
def get_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 تحليل شارت", "📊📊 متعدد الإطارات")
    kb.row("💹 السعر الحي", "📰 الأخبار")
    kb.row("💰 إدارة رأس المال", "📈 تقريري الأسبوعي")
    kb.row("📓 سجل صفقاتي", "🔔 التنبيهات")
    kb.row("ℹ️ مساعدة")
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
        "📌 *الإصدار v6.0 Ultra:*\n"
        "✅ تحليل عميق بـ 6 خطوات\n"
        "✅ 3 موديلات AI: Groq + Gemini + OpenRouter\n"
        "✅ أسعار حية من TwelveData\n"
        "✅ تحليل متعدد الإطارات\n"
        "✅ إدارة رأس المال الذكية\n"
        "✅ تنبيهات سيشن لندن ونيويورك\n"
        "✅ تقرير أسبوعي شامل\n\n"
        "أرسل صورة الشارت للبدء 👇",
        parse_mode="Markdown", reply_markup=get_kb()
    )

@bot.message_handler(commands=["balance"])
def set_balance(message):
    uid = message.from_user.id
    try:
        get_user(uid)["balance"] = float(message.text.split()[1])
        bot.reply_to(message, f"✅ رأس المال: *{get_user(uid)['balance']}$*", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ الاستخدام: `/balance 5000`", parse_mode="Markdown")

@bot.message_handler(commands=["risk"])
def set_risk(message):
    uid = message.from_user.id
    try:
        get_user(uid)["risk_percent"] = float(message.text.split()[1])
        bot.reply_to(message, f"✅ المخاطرة: *{get_user(uid)['risk_percent']}%*", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ الاستخدام: `/risk 2`", parse_mode="Markdown")

@bot.message_handler(commands=["lot"])
def calc_lot_cmd(message):
    uid = message.from_user.id
    try:
        sl = float(message.text.split()[1])
        u = get_user(uid)
        lot = calc_lot(u["balance"], u["risk_percent"], sl)
        risk_amt = u["balance"] * (u["risk_percent"] / 100)
        bot.reply_to(message,
            f"💰 *حجم اللوت*\n\n💵 {u['balance']}$ | ⚠️ {u['risk_percent']}% = {risk_amt}$\n📏 SL: {sl} pips\n\n📊 *اللوت: {lot}*",
            parse_mode="Markdown"
        )
    except:
        bot.reply_to(message, "❌ الاستخدام: `/lot 20`", parse_mode="Markdown")

@bot.message_handler(commands=["price"])
def price_cmd(message):
    try:
        symbol = message.text.split()[1].upper()
    except:
        symbol = "EUR/USD"
    msg = bot.reply_to(message, "⏳ جارٍ جلب السعر...")
    info = get_market_info(symbol)
    bot.edit_message_text(info, message.chat.id, msg.message_id, parse_mode="Markdown")

# ============================================================
# معالجة الأزرار
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📊 تحليل شارت")
def single_mode(message):
    get_user(message.from_user.id)["multi_charts"] = []
    bot.reply_to(message, "📸 أرسل صورة الشارت!")

@bot.message_handler(func=lambda m: m.text == "📊📊 متعدد الإطارات")
def multi_mode(message):
    get_user(message.from_user.id)["multi_charts"] = ["MULTI_MODE"]
    bot.reply_to(message,
        "📊 *وضع متعدد الإطارات*\n\n1️⃣ أرسل الإطار الكبير (H1/H4/D1)\n2️⃣ ثم الإطار الصغير (M5/M15)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "💹 السعر الحي")
def live_price_button(message):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("EUR/USD", callback_data="price_EUR/USD"),
        types.InlineKeyboardButton("GBP/USD", callback_data="price_GBP/USD"),
    )
    kb.row(
        types.InlineKeyboardButton("XAU/USD", callback_data="price_XAU/USD"),
        types.InlineKeyboardButton("USD/JPY", callback_data="price_USD/JPY"),
    )
    kb.row(
        types.InlineKeyboardButton("BTC/USD", callback_data="price_BTC/USD"),
        types.InlineKeyboardButton("NAS100", callback_data="price_NDX"),
    )
    bot.reply_to(message, "💹 *اختر الزوج للحصول على السعر الحي:*", parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📰 الأخبار")
def news_button(message):
    msg = bot.reply_to(message, "⏳ جارٍ جلب الأخبار...")
    bot.edit_message_text(get_forex_news(), message.chat.id, msg.message_id, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💰 إدارة رأس المال")
def capital_button(message):
    u = get_user(message.from_user.id)
    bot.reply_to(message,
        f"💰 *إدارة رأس المال*\n\n💵 رأس المال: *{u['balance']}$*\n⚠️ المخاطرة: *{u['risk_percent']}%*\n\n"
        f"`/balance 5000` — تغيير رأس المال\n`/risk 1` — تغيير المخاطرة\n`/lot 20` — حساب اللوت\n`/price EURUSD` — السعر الحي",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "📈 تقريري الأسبوعي")
def weekly_button(message):
    bot.reply_to(message, get_weekly_report(message.from_user.id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📓 سجل صفقاتي")
def journal_button(message):
    journal = get_user(message.from_user.id)["journal"]
    if not journal:
        bot.reply_to(message, "📓 السجل فارغ — أرسل شارتاً للبدء!")
        return
    text = "📓 *آخر 5 صفقات:*\n\n"
    for t in journal[-5:]:
        e = "✅" if t["result"]=="win" else "❌" if t["result"]=="loss" else "⏸️"
        text += f"{e} {t['signal']} — {t['date']}\n"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔔 التنبيهات")
def alerts_button(message):
    u = get_user(message.from_user.id)
    status = "مفعّلة ✅" if u["alerts"] else "معطّلة ❌"
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ تفعيل", callback_data="alert_on"),
        types.InlineKeyboardButton("❌ إيقاف", callback_data="alert_off")
    )
    bot.reply_to(message,
        f"🔔 *التنبيهات التلقائية*\n\nالحالة: {status}\n\n🌅 8:00 أخبار اليوم\n🇬🇧 10:00 سيشن لندن\n🇺🇸 15:00 سيشن نيويورك",
        parse_mode="Markdown", reply_markup=kb
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ مساعدة")
def help_button(message):
    bot.reply_to(message,
        "📖 *دليل الاستخدام v6.0*\n\n"
        "📊 تحليل شارت — تحليل عميق بـ 6 خطوات\n"
        "📊📊 متعدد الإطارات — HTF + LTF\n"
        "💹 السعر الحي — من TwelveData\n"
        "📰 الأخبار — High Impact\n"
        "💰 `/balance` `/risk` `/lot`\n"
        "🔔 تنبيهات السيشن والأخبار\n"
        "📈 تقرير أسبوعي شامل\n\n"
        "⚠️ _للأغراض التعليمية فقط_",
        parse_mode="Markdown"
    )

# ============================================================
# Callbacks
# ============================================================
@bot.callback_query_handler(func=lambda c: c.data.startswith("price_"))
def handle_price(call):
    symbol = call.data.replace("price_", "")
    bot.answer_callback_query(call.id, "⏳ جارٍ الجلب...")
    info = get_market_info(symbol)
    bot.send_message(call.message.chat.id, info, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data in ["alert_on","alert_off"])
def handle_alerts(call):
    get_user(call.from_user.id)["alerts"] = (call.data == "alert_on")
    status = "مفعّلة ✅" if call.data == "alert_on" else "معطّلة ❌"
    bot.answer_callback_query(call.id, f"التنبيهات {status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda c: c.data.startswith("win_") or c.data.startswith("loss_"))
def handle_result(call):
    result = call.data.split("_")[0]
    uid = int(call.data.split("_")[1])
    u = get_user(uid)
    if u["journal"]:
        u["journal"][-1]["result"] = result
        u["stats"]["win" if result=="win" else "loss"] += 1
        if u["stats"]["wait"] > 0: u["stats"]["wait"] -= 1
    bot.answer_callback_query(call.id, "✅ رابحة!" if result=="win" else "❌ خاسرة.")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

# ============================================================
# تحليل الصور
# ============================================================
@bot.message_handler(content_types=["photo"])
def analyze_chart(message):
    uid = message.from_user.id
    u = get_user(uid)
    mc = u["multi_charts"]

    file_info = bot.get_file(message.photo[-1].file_id)
    img_bytes = bot.download_file(file_info.file_path)

    if mc and mc[0] == "MULTI_MODE":
        u["multi_charts"] = [img_bytes]
        bot.reply_to(message, "✅ الإطار الكبير استُلم!\n\n📸 أرسل الآن الإطار الصغير (M5/M15)")
        return

    if mc and mc[0] != "MULTI_MODE" and len(mc) == 1:
        mc.append(img_bytes)
        msg = bot.reply_to(message, "⏳ جارٍ تحليل الإطارين... 🔍")
        try:
            analysis = analyze_images(mc, multi=True)
            u["multi_charts"] = []
            signal = "BUY" if "BUY" in analysis.upper() else "SELL" if "SELL" in analysis.upper() else "WAIT"
            u["journal"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "signal": signal, "result": "wait"})
            u["weekly_signals"].append(signal)
            if signal == "WAIT": u["stats"]["wait"] += 1
            lot = calc_lot(u["balance"], u["risk_percent"], 20)
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("✅ رابحة", callback_data=f"win_{uid}"),
                types.InlineKeyboardButton("❌ خاسرة", callback_data=f"loss_{uid}")
            )
            bot.edit_message_text(
                analysis + f"\n\n💰 *اللوت المقترح:* {lot} lot\n\n_سجّل نتيجة صفقتك:_",
                message.chat.id, msg.message_id, parse_mode="Markdown", reply_markup=markup
            )
        except Exception as e:
            bot.edit_message_text(f"❌ خطأ: {e}", message.chat.id, msg.message_id)
        return

    # تحليل شارت واحد
    msg = bot.reply_to(message, "⏳ جارٍ التحليل الشامل... 🔍")
    try:
        analysis = analyze_images([img_bytes])
        signal = "BUY" if "BUY" in analysis.upper() else "SELL" if "SELL" in analysis.upper() else "WAIT"
        u["journal"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "signal": signal, "result": "wait"})
        u["weekly_signals"].append(signal)
        if signal == "WAIT": u["stats"]["wait"] += 1
        lot = calc_lot(u["balance"], u["risk_percent"], 20)
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ رابحة", callback_data=f"win_{uid}"),
            types.InlineKeyboardButton("❌ خاسرة", callback_data=f"loss_{uid}")
        )
        bot.edit_message_text(
            analysis + f"\n\n💰 *اللوت المقترح:* {lot} lot _(بناءً على {u['risk_percent']}% من {u['balance']}$)_\n\n_سجّل نتيجة صفقتك:_",
            message.chat.id, msg.message_id, parse_mode="Markdown", reply_markup=markup
        )
    except Exception as e:
        bot.edit_message_text(f"❌ خطأ: {e}\nحاول مرة أخرى.", message.chat.id, msg.message_id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    bot.reply_to(message, "📸 أرسل صورة الشارت!\n\n/start للقائمة", reply_markup=get_kb())

def main():
    start_keep_alive()
    start_session_alerts()
    print("✅ ChartSniperBot v6.0 Ultra شغال!")
    bot.infinity_polling()

if __name__ == "__main__":
    main()
