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

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "SHIB Bot is active and running 24/7!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=7860)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 868999453
PAYMENT_CHANNEL = "@Crypto_Fox13"
CHANNELS = ["@penguin_110", "@Crypto_Dragon13", "@Exchange_of_referrals13", "@Crypto_Kings5"]

REWARD_PER_REFERRAL = 2000
MIN_WITHDRAW = 10000
CURRENCY = "SHIB"

def init_db():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance REAL DEFAULT 0,
        referrals INTEGER DEFAULT 0,
        referred_by INTEGER DEFAULT NULL,
        joined_at TEXT,
        verified INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount REAL,
        wallet TEXT,
        status TEXT DEFAULT 'pending',
        requested_at TEXT
    )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    exists = c.fetchone()
    if not exists:
        c.execute("INSERT INTO users (user_id, username, referred_by, joined_at, verified) VALUES (?,?,?,?,0)",
                  (user_id, username, referred_by, datetime.now().isoformat()))
        conn.commit()
    conn.close()

def verify_user(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT verified, referred_by FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if row and row[0] == 0:
        c.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))
        referred_by = row[1]
        if referred_by and referred_by != user_id:
            c.execute("SELECT user_id FROM users WHERE user_id=?", (referred_by,))
            if c.fetchone():
                c.execute("UPDATE users SET balance=balance+?, referrals=referrals+1 WHERE user_id=?",
                          (REWARD_PER_REFERRAL, referred_by))
        conn.commit()
        conn.close()
        return referred_by
    conn.close()
    return None

def get_balance(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT balance, referrals FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (0, 0)

def add_withdrawal(user_id, amount, wallet):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT INTO withdrawals (user_id, amount, wallet, requested_at) VALUES (?,?,?,?)",
              (user_id, amount, wallet, datetime.now().isoformat()))
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_withdrawal(withdrawal_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT * FROM withdrawals WHERE id=?", (withdrawal_id,))
    row = c.fetchone()
    conn.close()
    return row

def approve_withdrawal(withdrawal_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (withdrawal_id,))
    conn.commit()
    conn.close()

async def check_subscriptions(user_id, context):
    for channel in CHANNELS:
        try:
            ch_name = channel if channel.startswith("@") else f"@{channel}"
            member = await context.bot.get_chat_member(chat_id=ch_name, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            print(f"⚠️ فحص قناة معطلة: {e}")
            continue 
    return True

def reply_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🔗 رابط الإحالة"), KeyboardButton("💰 رصيدي")],
        [KeyboardButton("👥 إحالاتي"), KeyboardButton("💵 سحب")],
        [KeyboardButton("📢 قناة إثبات الدفع")]
    ], resize_keyboard=True)

def subscription_keyboard():
    buttons = [[InlineKeyboardButton(f"📢 اشترك في {ch}", url=f"https://t.me/{ch.lstrip('@')}")] for ch in CHANNELS]
    buttons.append([InlineKeyboardButton("✅ تحققت من اشتراكي", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    args = context.args
    referred_by = int(args[0]) if args and args[0].isdigit() else None
    
    add_user(user.id, user.username or user.first_name, referred_by)

    subscribed = await check_subscriptions(user.id, context)
    if not subscribed:
        await update.message.reply_text(
            "👋 مرحباً بك!\n\n⚠️ يجب الاشتراك في القنوات التالية أولاً:",
            reply_markup=subscription_keyboard()
        )
        return

    user_data = get_user(user.id)
    if user_data and user_data[6] == 0:
        referred_by_id = verify_user(user.id)
        if referred_by_id:
            try:
                await context.bot.send_message(
                    referred_by_id,
                    f"🎉 انضم شخص جديد عبر رابطك!\n💰 حصلت على +{REWARD_PER_REFERRAL:,} {CURRENCY}"
                )
            except:
                pass

    await update.message.reply_text(
        f"👋 أهلاً {user.first_name}!\n\n"
        f"🤖 بوت الإحالات\n"
        f"💰 اربح {REWARD_PER_REFERRAL:,} {CURRENCY} لكل صديق تدعوه!\n"
        f"📌 الحد الأدنى للسحب: {MIN_WITHDRAW:,} {CURRENCY}",
        reply_markup=reply_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = query.from_user

    if query.data == "check_sub":
        subscribed = await check_subscriptions(user.id, context)
        if subscribed:
            referred_by_id = verify_user(user.id)
            if referred_by_id:
                try:
                    await context.bot.send_message(
                        referred_by_id,
                        f"🎉 انضم شخص جديد عبر رابطك!\n💰 حصلت على +{REWARD_PER_REFERRAL:,} {CURRENCY}"
                    )
                except:
                    pass
            await query.edit_message_text(f"✅ تم التحقق! أهلاً {user.first_name}")
            await context.bot.send_message(
                user.id,
                f"👋 أهلاً {user.first_name}!\n\n"
                f"🤖 بوت الإحالات\n"
                f"💰 اربح {REWARD_PER_REFERRAL:,} {CURRENCY} لكل صديق تدعوه!\n"
                f"📌 الحد الأدنى للسحب: {MIN_WITHDRAW:,} {CURRENCY}",
                reply_markup=reply_keyboard()
            )
        else:
            try:
                await query.edit_message_text(
                    "❌ لم تشترك في جميع القنوات!\nاشترك ثم اضغط تحققت.",
                    reply_markup=subscription_keyboard()
                )
            except:
                pass

    elif query.data.startswith("approve_"):
        if user.id != ADMIN_ID:
            return
        parts = query.data.split("_")
        withdrawal_id = int(parts[1])
        target_user_id = int(parts[2])
        withdrawal = get_withdrawal(withdrawal_id)
        if not withdrawal or withdrawal[4] == "approved":
            await query.answer("تم الموافقة مسبقاً!", show_alert=True)
            return
        approve_withdrawal(withdrawal_id)
        
        try:
            target_user = await context.bot.get_chat(target_user_id)
            username = f"@{target_user.username}" if target_user.username else target_user.first_name
        except:
            username = f"المستخدم ({target_user_id})"

        await context.bot.send_message(
            PAYMENT_CHANNEL,
            f"✅ تم الدفع!\n\n"
            f"👤 المستخدم: {username}\n"
            f"💰 المبلغ: {withdrawal[2]:,} {CURRENCY}\n"
            f"🏦 Binance ID: `{withdrawal[3]}`",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                target_user_id,
                f"✅ تم تحويل {withdrawal[2]:,} {CURRENCY} إلى حساب Binance بتاعك!"
            )
        except:
            pass
        await query.edit_message_reply_markup(reply_markup=None)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    text = update.message.text

    if context.user_data.get("awaiting_wallet"):
        binance_id = text.strip()
        if not binance_id.isdigit() or len(binance_id) < 9:
            await update.message.reply_text(
                "❌ Binance ID غير صحيح!\nلازم يكون أرقام فقط ولا يقل عن 9 أرقام.\n\nأرسل Binance ID مرة أخرى:"
            )
            return
        amount = context.user_data["withdraw_amount"]
        add_withdrawal(user.id, amount, binance_id)
        conn = sqlite3.connect("bot.db")
        withdrawal_id = conn.execute(
            "SELECT id FROM withdrawals WHERE user_id=? ORDER BY id DESC LIMIT 1", (user.id,)
        ).fetchone()[0]
        conn.close()
        context.user_data.pop("awaiting_wallet", None)
        context.user_data.pop("withdraw_amount", None)
        await update.message.reply_text(
