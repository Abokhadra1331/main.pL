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

# --- إعدادات السيرفر ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "SHIB Bot is active and running 24/7!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=7860)

# --- الإعدادات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 868999453
PAYMENT_CHANNEL = "@Crypto_Fox13"
CHANNELS = ["@penguin_110", "@Crypto_Dragon13", "@Exchange_of_referrals13", "@Crypto_Kings5"]
REWARD_PER_REFERRAL = 2000
MIN_WITHDRAW = 10000
CURRENCY = "SHIB"

# --- قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0, referrals INTEGER DEFAULT 0, referred_by INTEGER DEFAULT NULL, joined_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

def check_sub(user_id, context):
    for channel in CHANNELS:
        try:
            member = context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']: return False
        except: return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() else None
    
    conn = sqlite3.connect("bot.db"); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by) VALUES (?,?,?)", (user.id, user.username or user.first_name, referred_by))
    if referred_by:
        c.execute("UPDATE users SET balance=balance+?, referrals=referrals+1 WHERE user_id=?", (REWARD_PER_REFERRAL, referred_by))
    conn.commit(); conn.close()
    
    if not check_sub(user.id, context):
        buttons = [[InlineKeyboardButton(f"اشترك في {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
        buttons.append([InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check")])
        await update.message.reply_text("⚠️ يجب الاشتراك في القنوات أولاً:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await send_main_menu(update)

async def send_main_menu(update):
    kb = ReplyKeyboardMarkup([["💰 رصيدي", "🔗 رابط الإحالة"], ["💵 سحب"], ["📢 قناة إثبات الدفع"]], resize_keyboard=True)
    await update.message.reply_text("مرحباً بك في بوت الإحالات!", reply_markup=kb)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "check":
        if check_sub(query.from_user.id, context):
            await query.edit_message_text("✅ تم التحقق!")
            await send_main_menu(update)
        else:
            await query.answer("❌ لم تشترك بعد!", show_alert=True)
    elif query.data.startswith("approve_"):
        if query.from_user.id == ADMIN_ID:
            w_id = query.data.split("_")[1]
            conn = sqlite3.connect("bot.db"); c = conn.cursor()
            c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (w_id,))
            conn.commit(); conn.close()
            await query.edit_message_text("✅ تم الموافقة على السحب!")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    if text == "💰 رصيدي":
        conn = sqlite3.connect("bot.db"); c = conn.cursor()
        c.execute("SELECT balance, referrals FROM users WHERE user_id=?", (user_id,))
        res = c.fetchone(); conn.close()
        if res: await update.message.reply_text(f"💰 رصيدك: {res[0]} {CURRENCY}\n👥 إحالاتك: {res[1]}")
    elif text == "🔗 رابط الإحالة":
        bot = await context.bot.get_me()
        await update.message.reply_text(f"🔗 رابطك: https://t.me/{bot.username}?start={user_id}")
    elif text == "💵 سحب":
        conn = sqlite3.connect("bot.db"); c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        bal = c.fetchone()[0]
        if bal >= MIN_WITHDRAW:
            c.execute("INSERT INTO withdrawals (user_id, amount) VALUES (?,?)", (user_id, bal))
            c.execute("UPDATE users SET balance=0 WHERE user_id=?", (user_id,))
            conn.commit()
            await update.message.reply_text("✅ تم إرسال طلبك للمراجعة!")
            await context.bot.send_message(ADMIN_ID, f"طلب سحب جديد من {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ موافقة", callback_data=f"approve_{c.lastrowid}")]]))
        else:
            await update.message.reply_text("❌ رصيدك غير كافٍ.")
        conn.close()

def main():
    init_db()
    threading.Thread(target=run_flask, daemon=True).start()
    request_config = HTTPXRequest(connect_timeout=60.0, read_timeout=60.0, write_timeout=60.0)
    app = Application.builder().token(BOT_TOKEN).request(request_config).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🟢 البوت يعمل الآن بكامل طاقته!")
    # السطر المهم جداً: يمسح أي Webhook ويسمح بكل أنواع التحديثات
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
