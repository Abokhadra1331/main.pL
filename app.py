import os
import logging
import threading
import json
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError

# إعداد السجلات لمراقبة الأخطاء
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running 24/7 with Referrals!"

def run_flask():
    app.run(host="0.0.0.0", port=7860)

# 📢 القنوات الأربعة الخاصة بك
CHANNELS = ["@penguin_110", "@Crypto_Dragon13", "@Exchange_of_referrals13", "@Crypto_Kings5"]

# 📊 قاعدة بيانات بسيطة لحفظ نقاط المستخدمين والإحالات (ملف json)
DB_FILE = "users_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# دالة فحص الاشتراكات الناقصة
async def get_unsubscribed_channels(user_id, context: ContextTypes.DEFAULT_TYPE):
    unsubscribed = []
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'creator', 'administrator']:
                unsubscribed.append(channel)
        except Exception as e:
            logging.error(f"خطأ في القناة {channel}: {e}")
            unsubscribed.append(channel)
    return unsubscribed

# دالة التشغيل عند إرسال /start (وتدعم نظام الإحالات)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    args = context.args  # التقاط معرف الشخص الذي قام بالإحالة
    
    db = load_db()
    
    # إذا كان المستخدم جديداً تماماً في قاعدة البيانات
    if user_id not in db:
        referrer_id = args[0] if (args and args[0] != user_id) else None
        db[user_id] = {
            "username": user.username or "No Username",
            "points": 0,
            "referred_by": referrer_id,
            "referrals_count": 0,
            "is_activated": False  # لن يتم تفعيله أو احتساب نقطة لدعوته إلا بعد الاشتراك بالقنوات
        }
        save_db(db)

    unsubscribed_channels = await get_unsubscribed_channels(user.id, context)
    
    if not unsubscribed_channels:
        # إذا كان مشتركاً بالفعل، نقوم بتفعيل حسابه واحتساب النقاط إن وجد مُحيل
        await activate_user(user_id, update, context)
    else:
        # بناء أزرار الاشتراك للقنوات الناقصة
        keyboard = []
        for index, channel in enumerate(unsubscribed_channels, start=1):
            channel_url = f"https://t.me/{channel.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 اشترك في القناة {index} ({channel})", url=channel_url)])
        
        # تمرير بيانات المحيل في الـ callback_data إذا وجد للتحقق لاحقاً
        keyboard.append([InlineKeyboardButton("✅ اضغط هنا بعد الاشتراك لتفعيل البوت", callback_data="check_sub")])
        
        await update.message.reply_text(
            f"أهلاً بك يا غالي في بوت SHIB Inu! 🚦\n\n"
            f"للاستفادة من نظام الإحالات وتجميع النقاط، يجب عليك أولاً الاشتراك في القنوات الرسمية لدعم المشروع.\n"
            f"يرجى الانضمام للقنوات بالأسفل ثم اضغط زر التفعيل: 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# دالة تفعيل الحساب ومنح النقاط للمُحيل
async def activate_user(user_id, update_or_query, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
    db = load_db()
    bot_username = context.bot.username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    
    # التحقق إن كان الحساب لم يُفعل بعد لمنع تكرار النقاط
    if not db.get(user_id, {}).get("is_activated", False):
        db[user_id]["is_activated"] = True
        referrer_id = db[user_id].get("referred_by")
        
        # إذا جاء المستخدم عبر رابط إحالة شخص آخر، نمنح الشخص الآخر نقطة
        if referrer_id and referrer_id in db:
            db[referrer_id]["points"] += 1
            db[referrer_id]["referrals_count"] += 1
            try:
                # إشعار الشخص الذي قام بدعوته بنجاح
                await context.bot.send_message(
                    chat_id=int(referrer_id),
                    text=f"🎉 دخل مستخدم جديد عبر رابطك واشترك في القنوات! حصلت على 1 نقطة.\n"
                         f"رصيدك الحالي: {db[referrer_id]['points']} نقطة."
                )
            except Exception as e:
                logging.error(f"فشل إرسال إشعار للمُحيل: {e}")
        
        save_db(db)

    welcome_text = (
        f"🎉 ممتاز! تم تفعيل حسابك بنجاح في بوت SHIB Inu!\n\n"
        f"📊 رصيدك الحالي: {db[user_id]['points']} نقطة.\n"
        f"👥 عدد الإحالات الناجحة: {db[user_id]['referrals_count']}\n\n"
        f"🔗 رابط الإحالة الخاص بك (انشره لتجميع النقاط):\n`{ref_link}`"
    )

    if is_callback:
        await update_or_query.edit_message_text(welcome_text, parse_mode="Markdown")
    else:
        await update_or_query.message.reply_text(welcome_text, parse_mode="Markdown")

# دالة التحقق عند الضغط على زر التفعيل
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    unsubscribed_channels = await get_unsubscribed_channels(query.from_user.id, context)
    
    if not unsubscribed_channels:
        await activate_user(user_id, query, context, is_callback=True)
    else:
        keyboard = []
        for index, channel in enumerate(unsubscribed_channels, start=1):
            channel_url = f"https://t.me/{channel.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 اشترك في القناة {index} ({channel})", url=channel_url)])
        keyboard.append([InlineKeyboardButton("✅ اضغط هنا بعد الاشتراك لتفعيل البوت", callback_data="check_sub")])
        
        try:
            await query.edit_message_text(
                "⚠️ يبدو أنك لم تشترك في جميع القنوات بعد يا صديقي!\n"
                "تأكد من الانضمام لكل القنوات بالأسفل ثم اضغط زر التفعيل مجدداً: 👇",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            pass

def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logging.error("خطأ: لم يتم العثور على BOT_TOKEN!")
        return

    threading.Thread(target=run_flask, daemon=True).start()

    # بناء وتشفير البوت مع تخطي الفحص لتفادي الـ Timeout
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^check_sub$"))
    
    logging.info("بدء تشغيل البوت الشامل للإحالات والاشتراكات...")
    application.run_polling(initialize=False)

if __name__ == '__main__':
    main()
