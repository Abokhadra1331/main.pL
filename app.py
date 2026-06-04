import os
import sqlite3
import threading
import asyncio
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.request import HTTPXRequest

# --- إعدادات السيرفر للحفاظ على بقاء البوت 24/7 ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "SHIB Bot is active and running 24/7!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=7860)

# --- الإعدادات الأساسية ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 868999453
PAYMENT_CHANNEL = "@Crypto_Fox13"
CHANNELS = ["@penguin_110", "@Crypto_Dragon13", "@Exchange_of_referrals13", "@Crypto_Kings5"]
REWARD_PER_REFERRAL = 2000
MIN_WITHDRAW = 10000
CURRENCY = "SHIB"

# --- إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL, joined_at TEXT, verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, wallet TEXT, status TEXT DEFAULT 'pending', requested_at TEXT)''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot.db"); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)); row = c.fetchone(); conn.close(); return row

def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect("bot.db"); c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not c.fetchone():
        c.execute("INSERT INTO users (user_id, username, referred_by, joined_at) VALUES (?,?,?,?)", (user_id, username, referred_by, datetime.now().isoformat()))
        conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("bot.db"); c = conn.cursor()
    c.execute("SELECT balance, referrals FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone(); conn.close(); return row if row else (0, 0)

# --- الدوال الخاصة بالبوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() else None
    add_user(user.id, user.username or user.first_name, referred_by)
    
    keyboard = ReplyKeyboardMarkup([["💰 رصيدي", "🔗 رابط الإحالة"], ["💵 سحب"], ["📢 قناة إثبات الدفع"]], resize_keyboard=True)
    await update.message.reply_text(f"👋 أهلاً بك {user.first_name} في بوت {CURRENCY}!\n💰 اربح المال من الإحالات.", reply_markup=keyboard)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "💰 رصيدي":
        bal, refs = get_balance(user_id)
        await update.message.reply_text(f"💰 رصيدك الحالي: {bal:,} {CURRENCY}\n👥 عدد إحالاتك: {refs}")
    
    elif text == "🔗 رابط الإحالة":
        bot = await context.bot.get_me()
        await update.message.reply_text(f"🔗 رابط إحالتك هو:\nhttps://t.me/{bot.username}?start={user_id}")
    
    elif text == "💵 سحب":
        bal, _ = get_balance(user_id)
        if bal < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ رصيدك غير كافٍ. الحد الأدنى للسحب هو {MIN_WITHDRAW:,} {CURRENCY}")
        else:
            await update.message.reply_text("📩 أرسل عنوان محفظتك (Binance ID) ليتم مراجعة الطلب:")

# --- التشغيل الأساسي ---
def main():
    init_db()
    if not BOT_TOKEN:
        print("❌ Error: BOT_TOKEN is missing!")
        return
    
    # تشغيل السيرفر في الخلفية
    threading.Thread(target=run_flask, daemon=True).start()
    
    # إعدادات متقدمة تمنع Timeout وتضمن ثبات الاتصال
    request_config = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0, write_timeout=60.0)
    
    # بناء البوت
    app = Application.builder().token(BOT_TOKEN).request(request_config).build()
    
    # إضافة الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🟢 البوت يعمل الآن وبانتظار الرسائل...")
    # التشغيل مع إزالة أي تحديثات قديمة معلقة لتجنب الـ Conflict
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
