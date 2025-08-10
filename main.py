import telebot
from datetime import datetime, timedelta
import threading

# توکن و چت آی‌دی خودت رو اینجا بزار
TOKEN = "8488391940:AAEQVhHL2h9irpB7lwwPfWPmvaYv84sj-0g"
CHAT_ID = -1002744219806

bot = telebot.TeleBot(TOKEN)

# ذخیره امتیازها
scores = {}
daily_progress = {}

# وقتی کسی گزارش میده
@bot.message_handler(commands=['گزارش'])
def report(message):
    try:
        hours = int(message.text.split()[1])
    except:
        bot.reply_to(message, "لطفا به این شکل بزن: /گزارش 5")
        return
    
    user = message.from_user.first_name
    scores[user] = scores.get(user, 0) + hours
    daily_progress[user] = daily_progress.get(user, 0) + hours
    bot.reply_to(message, f"✅ گزارش ثبت شد! {hours} ساعت برای {user} اضافه شد.")

# ارسال گزارش روزانه
def daily_report():
    while True:
        now = datetime.now()
        if now.hour == 22 and now.minute == 0:
            if daily_progress:
                msg = "📊 گزارش امروز:\n"
                for user, hours in daily_progress.items():
                    msg += f"{user}: {hours} ساعت\n"
                bot.send_message(CHAT_ID, msg)
                daily_progress.clear()
        threading.Event().wait(60)

# اجرای ترد جدا برای گزارش روزانه
threading.Thread(target=daily_report, daemon=True).start()

# اجرای ربات
bot.polling(none_stop=True)
  
