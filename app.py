import os
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError
from telegram.request import HTTPXRequest

# 1. إعداد السجلات (Logs) لمراقبة العمليات والأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# 2. تشغيل سيرفر الويب (Flask) لإرضاء منصة Hugging Face ومنع إغلاق السبيس
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is active and running 24/7!"

def run_flask():
    app.run(host="0.0.0.0", port=7860)

# 📢 3. مصفوفة القنوات الأربعة الخاصة بك بالملي
CHANNELS = ["@penguin_110", "@Crypto_Dragon13", "@Exchange_of_referrals13", "@Crypto_Kings5"]

# 4. دالة الفحص للتحقق من القنوات التي لم يشترك فيها المستخدم بعد
async def get_unsubscribed_channels(user_id, context: ContextTypes.DEFAULT_TYPE):
    unsubscribed = []
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'creator', 'administrator']:
                unsubscribed.append(channel)
        except TelegramError as e:
            logging.error(f"خطأ أثناء فحص القناة {channel}: {e}")
            # إذا تعذر الفحص (مثلاً البوت ليس مشرفاً بعد)، نعتبرها غير مشترك احتياطياً
            unsubscribed.append(channel)
    return unsubscribed

# 5. دالة الرد على أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    unsubscribed_channels = await get_unsubscribed_channels(user_id, context)
    
    if not unsubscribed_channels:
        await update.message.reply_text(
            "أهلاً بك مجدداً في بوت SHIB Inu! ✨\n"
            "لقد تم التحقق من اشتراكك في جميع القنوات بنجاح. البوت جاهز لخدمتك الآن! 🚀"
        )
    else:
        # بناء أزرار الاشتراك للقنوات الناقصة فقط
        keyboard = []
        for index, channel in enumerate(unsubscribed_channels, start=1):
            channel_url = f"https://t.me/{channel.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 اشترك في القناة {index} ({channel})", url=channel_url)])
        
        keyboard.append([InlineKeyboardButton("✅ اضغط هنا بعد الاشتراك لتفعيل البوت", callback_data="check_sub")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "عذراً يا غالي! 🚦 للاستفادة من خدمات البوت، يجب عليك أولاً الاشتراك في القنوات الرسمية لدعم المشروع.\n\n"
            "يرجى الانضمام للقنوات الناقصة بالأسفل ثم اضغط على زر التفعيل: 👇",
            reply_markup=reply_markup
        )

# 6. دالة التعامل مع ضغطة زر التفعيل "check_sub"
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    unsubscribed_channels = await get_unsubscribed_channels(user_id, context)
    
    if not unsubscribed_channels:
        await query.edit_message_text(
            "🎉 ممتاز! تم التحقق واشتركت في جميع القنوات بنجاح.\n"
            "أهلاً بك في بوت SHIB Inu! البوت يعمل الآن 24 ساعة من أجلك. 🚀"
        )
    else:
        keyboard = []
        for index, channel in enumerate(unsubscribed_channels, start=1):
            channel_url = f"https://t.me/{channel.replace('@', '')}"
            keyboard.append([InlineKeyboardButton(f"📢 اشترك في القناة {index} ({channel})", url=channel_url)])
        
        keyboard.append([InlineKeyboardButton("✅ اضغط هنا بعد الاشتراك لتفعيل البوت", callback_data="check_sub")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                "⚠️ يبدو أنك لم تشترك في جميع القنوات بعد يا صديقي!\n"
                "تأكد من الانضمام لكل القنوات المذكورة بالأسفل ثم اضغط زر التفعيل مجدداً: 👇",
                reply_markup=reply_markup
            )
        except TelegramError:
            pass

# 7. الدالة الرئيسية لتشغيل البوت والسيرفر معاً
def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        logging.error("خطأ: لم يتم العثور على BOT_TOKEN في إعدادات Secrets!")
        return

    # 🛑 حل مشكلة الـ TimedOut: تمديد مهلة الاتصال لـ 60 ثانية كاملة لضمان استقرار السيرفر
    custom_request = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0)

    # بناء التطبيق بالإعدادات الممددة الآمنة
    application = Application.builder().token(token).request(custom_request).build()
    
    # إضافة المعالجات (Handlers)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^check_sub$"))
    
    # تشغيل سيرفر ويب Flask في خلفية منفصلة تماماً
    threading.Thread(target=run_flask, daemon=True).start()
    
    logging.info("بدء استماع البوت للرسائل بأمان كامل ضد الـ Timeout...")
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    main()
