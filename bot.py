import telebot
from datetime import datetime, timedelta
import sqlite3
import threading
import time

# توکن و Chat ID خودت رو اینجا بذار
TOKEN = "8488391940:AAEQVhHL2h9irpB7lwwPfWPmvaYv84sj-0g"
CHAT_ID = -1002744219806

bot = telebot.TeleBot(TOKEN)

# اتصال به دیتابیس
conn = sqlite3.connect("scores.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS scores (
    user_id INTEGER,
    name TEXT,
    score INTEGER,
    date TEXT
)
""")
conn.commit()

# دستورات امتیازدهی
@bot.message_handler(commands=["ساعت"])
def add_hours(message):
    try:
        hours = int(message.text.split()[1])
        points = hours * 10
        save_score(message.from_user.id, message.from_user.first_name, points)
        bot.reply_to(message, f"{points} امتیاز بابت {hours} ساعت مطالعه ثبت شد ✅")
    except:
        bot.reply_to(message, "فرمت صحیح: /ساعت 5")

@bot.message_handler(commands=["تست"])
def add_tests(message):
    try:
        tests = int(message.text.split()[1])
        points = (tests // 20) * 5
        save_score(message.from_user.id, message.from_user.first_name, points)
        bot.reply_to(message, f"{points} امتیاز بابت {tests} تست ثبت شد ✅")
    except:
        bot.reply_to(message, "فرمت صحیح: /تست 40")

@bot.message_handler(commands=["گزارش"])
def daily_report(message):
    user_id = message.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT * FROM scores WHERE user_id=? AND date=?", (user_id, today))
    if cursor.fetchone():
        bot.reply_to(message, "شما امروز گزارش داده‌اید ✅")
    else:
        save_score(user_id, message.from_user.first_name, 10)
        bot.reply_to(message, "۱۰ امتیاز بابت گزارش روزانه ثبت شد ✅")

def save_score(user_id, name, points):
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO scores (user_id, name, score, date) VALUES (?, ?, ?, ?)",
                   (user_id, name, points, today))
    conn.commit()

def check_daily_winner():
    while True:
        now = datetime.now()
        if now.hour == 22 and now.minute == 0:
            today = now.strftime("%Y-%m-%d")
            cursor.execute("SELECT name, SUM(score) as total FROM scores WHERE date=? GROUP BY user_id ORDER BY total DESC", (today,))
            rows = cursor.fetchall()
            if rows:
                winner = rows[0][0]
                bot.send_message(CHAT_ID, f"🏆 برنده امروز: {winner} با {rows[0][1]} امتیاز")
        time.sleep(60)

threading.Thread(target=check_daily_winner, daemon=True).start()

print("Bot is running...")
bot.infinity_polling()
