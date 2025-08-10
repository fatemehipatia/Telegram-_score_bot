# bot.py
# -*- coding: utf-8 -*-
import os
import json
import time
import threading
import re
from datetime import datetime, timedelta
import telebot

# ---------- خواندن تنظیمات از متغیر محیطی ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID") or 0)  # حتما -100... وارد شود
TZ = os.getenv("TZ")  # مثال: "Europe/Berlin" یا "Asia/Tehran"

if TZ:
    os.environ['TZ'] = TZ
    try:
        time.tzset()
    except Exception:
        pass

bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# ---------- بارگذاری و ذخیره‌سازی داده ----------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

# ساختار داده:
# data = {
#   "users": { uid: {"name":..., "reports": { "YYYY-MM-DD": {"hours":int,"tests":int,"presence":0/1,"points":int}}, "weekly":int, "monthly":int } },
#   "daily_bonus_dates": ["YYYY-MM-DD", ...]
# }
data = load_data()
if "users" not in data:
    data["users"] = {}
if "daily_bonus_dates" not in data:
    data["daily_bonus_dates"] = []
save_data(data)

# ---------- قوانین امتیازدهی ----------
# هر ساعت مطالعه = 10 امتیاز
# هر 20 تست = 5 امتیاز
# حضور و گزارش روزانه = 10 امتیاز ثابت
# نفر اول روز = 10 امتیاز اضافه
# پیشرفت نسبت به روز قبل = 5 امتیاز

def calc_points(hours:int, tests:int, presence:bool)->int:
    pts = 0
    try:
        pts += int(hours) * 10
    except:
        pass
    try:
        pts += (int(tests) // 20) * 5
    except:
        pass
    if presence:
        pts += 10
    return pts

# ---------- پارسر متن گزارش فارسی ----------
def parse_report_text(text: str):
    """
    متن‌های قابل قبول:
      "3ساعت 40تست"
      "3 ساعت 40 تست"
      "3ساعت"
      "40تست"
      و ترکیب‌های مشابه
    خروجی: (hours:int, tests:int)
    """
    hours = 0
    tests = 0
    # normalize: تبدیل ارقام فارسی به لاتین (اگر لازم باشه) — ساده: فقط ارقام انگلیسی/فارسی
    # اول استخراج ساعت
    m = re.search(r'(\d+)\s*ساعت', text)
    if m:
        hours = int(m.group(1))
    # استخراج تست
    m2 = re.search(r'(\d+)\s*تست', text)
    if m2:
        tests = int(m2.group(1))
    return hours, tests

# ---------- ثبت یا به‌روزرسانی گزارش روزانه (فقط یک‌بار در روز) ----------
def record_activity_once(user_id:int, name:str, hours:int=0, tests:int=0):
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)
    users = data["users"]
    if uid not in users:
        users[uid] = {"name": name, "reports": {}, "weekly": 0, "monthly": 0}
    # اگر امروز قبلاً ثبت شده باشد،‌ نپذیرد
    if today in users[uid]["reports"]:
        return False, users[uid]["reports"][today]["points"]
    presence = True
    pts = calc_points(hours, tests, presence)
    users[uid]["reports"][today] = {"hours": hours, "tests": tests, "presence": 1, "points": pts}
    users[uid]["weekly"] = users[uid].get("weekly", 0) + pts
    users[uid]["monthly"] = users[uid].get("monthly", 0) + pts
    users[uid]["name"] = name
    save_data(data)
    return True, pts

# ---------- دستورات کاربری (در پیوی بات) ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    txt = ("سلام!\n\n"
           "برای ثبت گزارش روزانه از این دستور استفاده کنید:\n"
           "مثال:\n"
           "/گزارش 3ساعت 40تست\n\n"
           "دستورهای دیگر در پیوی:\n"
           "/امتیاز — نمایش امتیاز امروز و ماه\n"
           "/رتبه — جدول ماهانه")
    bot.reply_to(m, txt)

@bot.message_handler(commands=["گزارش"])
def cmd_report(m):
    # این دستور برای کاربران است (پیوی یا گروه) — ما اجازه می‌دهیم در پیوی استفاده شود.
    text = m.text.replace("/گزارش", "").strip()
    hours, tests = parse_report_text(text)
    ok, pts = record_activity_once(m.from_user.id, m.from_user.first_name, hours=hours, tests=tests)
    if ok:
        bot.reply_to(m, f"✅ گزارش ثبت شد.\n{safenum(hours)} ساعت مطالعه، {safenum(tests)} تست.\nامتیاز اضافه‌شده: {pts}")
    else:
        bot.reply_to(m, f"📌 امروز قبلا گزارش داده‌اید.\nامتیاز امروز شما: {pts}")

def safenum(x):
    try:
        return int(x)
    except:
        return 0

@bot.message_handler(commands=["امتیاز"])
def cmd_score(m):
    uid = str(m.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in data["users"]:
        bot.reply_to(m, "هنوز امتیازی برای شما ثبت نشده.")
        return
    today_pts = data["users"][uid]["reports"].get(today, {}).get("points", 0)
    month_pts = data["users"][uid].get("monthly", 0)
    bot.reply_to(m, f"📊 امتیاز امروز: {today_pts}\n📅 مجموع ماه: {month_pts}")

@bot.message_handler(commands=["رتبه"])
def cmd_leaderboard(m):
    arr = []
    for uid, info in data["users"].items():
        arr.append((info.get("monthly", 0), info.get("name", "کاربر ناشناس")))
    arr.sort(reverse=True)
    if not arr:
        bot.reply_to(m, "هنوز امتیازی ثبت نشده.")
        return
    txt = "🏆 جدول ماهانه:\n"
    for i, (pts, name) in enumerate(arr[:20], start=1):
        txt += f"{i}. {name} — {pts} امتیاز\n"
    bot.reply_to(m, txt)

# ---------- دستور ادمین برای اجرای گزارش فوری (در گروه) ----------
@bot.message_handler(commands=["گزارش_فوری"])
def cmd_admin_report(m):
    # فقط در گروه و توسط ادمین اجرا شود
    try:
        if m.chat.id != GROUP_CHAT_ID:
            bot.reply_to(m, "این دستور فقط در گروه اجرا می‌شود.")
            return
        member = bot.get_chat_member(GROUP_CHAT_ID, m.from_user.id)
        if member.status not in ("creator", "administrator"):
            bot.reply_to(m, "⛔ فقط ادمین یا سازنده گروه می‌تواند این دستور را اجرا کند.")
            return
    except Exception:
        bot.reply_to(m, "خطا در بررسی وضعیت ادمین.")
        return
    do_daily_tasks_and_announce()
    bot.reply_to(m, "✅ گزارش روزانه اجرا شد.")

# ---------- وظایف روزانه — محاسبه پیشرفت و جایزه نفر اول ----------
def do_daily_tasks_and_announce():
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    users = data["users"]
    today_list = []
    for uid, info in users.items():
        rep = info.get("reports", {})
        if today in rep:
            pts = rep[today].get("points", 0)
            today_list.append((pts, info.get("name", "ناشناس"), uid))

    if not today_list:
        bot.send_message(GROUP_CHAT_ID, "📋 امروز کسی گزارش ثبت نکرد.")
        return

    # مرتب‌سازی و انتخاب نفر اول
    today_list.sort(reverse=True, key=lambda x: x[0])
    top_pts, top_name, top_uid = today_list[0]

    if today not in data.get("daily_bonus_dates", []):
        # جایزه نفر اول روز (+10)
        users[top_uid]["weekly"] = users[top_uid].get("weekly", 0) + 10
        users[top_uid]["monthly"] = users[top_uid].get("monthly", 0) + 10

        progressed = []
        for pts, name, uid in today_list:
            y_pts = users.get(uid, {}).get("reports", {}).get(yesterday, {}).get("points", 0)
            if pts > y_pts:
                users[uid]["weekly"] = users[uid].get("weekly", 0) + 5
                users[uid]["monthly"] = users[uid].get("monthly", 0) + 5
                progressed.append(name)

        data.setdefault("daily_bonus_dates", []).append(today)
        save_data(data)

        # ارسال پیام
        msg = "📅 گزارش روزانه:\n\n"
        for rank, (pts, name, uid) in enumerate(today_list, start=1):
            msg += f"{rank}. {name} — {pts} امتیاز\n"
        msg += f"\n🏅 نفر اول امروز: {top_name} — {top_pts} امتیاز (+10 امتیاز جایزه)\n"
        if progressed:
            msg += "🎯 افرادی که نسبت به دیروز پیشرفت کردند (هر کدام +5 امتیاز):\n"
            msg += ", ".join(progressed) + "\n"
        bot.send_message(GROUP_CHAT_ID, msg)
    else:
        msg = "📅 گزارش روزانه (تکراری):\n\n"
        for rank, (pts, name, uid) in enumerate(today_list, start=1):
            msg += f"{rank}. {name} — {pts} امتیاز\n"
        bot.send_message(GROUP_CHAT_ID, msg)

# ---------- وظایف هفتگی و ماهانه ----------
def do_weekly_tasks_and_announce():
    users = data["users"]
    arr = []
    for uid, info in users.items():
        arr.append((info.get("weekly", 0), info.get("name", "ناشناس"), uid))
    arr.sort(reverse=True)
    if not arr:
        bot.send_message(GROUP_CHAT_ID, "این هفته هیچ امتیازی ثبت نشده.")
        return
    top = arr[0]
    users[top[2]]["monthly"] = users[top[2]].get("monthly", 0) + 20
    bot.send_message(GROUP_CHAT_ID, f"🏆 نفر اول هفته: {top[1]} — {top[0]} امتیاز (+20 امتیاز جایزه)")
    for info in users.values():
        info["weekly"] = 0
    save_data(data)

def do_monthly_tasks_and_announce():
    users = data["users"]
    arr = []
    for uid, info in users.items():
        arr.append((info.get("monthly", 0), info.get("name", "ناشناس"), uid))
    arr.sort(reverse=True)
    if not arr:
        bot.send_message(GROUP_CHAT_ID, "این ماه هیچ امتیازی ثبت نشده.")
        return
    top = arr[0]
    bot.send_message(GROUP_CHAT_ID, f"🌟 نفر اول ماه: {top[1]} — {top[0]} امتیاز")
    for info in users.values():
        info["monthly"] = 0
    save_data(data)

# ---------- زمان‌بندی اجراها (thread background) ----------
def schedule_runner():
    while True:
        now = datetime.now()
        # روزانه ساعت 22
        if now.hour == 22 and now.minute == 0:
            try:
                do_daily_tasks_and_announce()
            except Exception as e:
                print("Error in daily job:", e)
            time.sleep(61)  # جلوگیری از اجرای مکرر در همان دقیقه
        # جمعه (weekday 4) ساعت 22 -> توجه: Monday=0 ... Sunday=6 ; جمعه=4
        if now.weekday() == 4 and now.hour == 22 and now.minute == 0:
            try:
                do_weekly_tasks_and_announce()
            except Exception as e:
                print("Error in weekly job:", e)
            time.sleep(61)
        # روز اول ماه ساعت 22
        if now.day == 1 and now.hour == 22 and now.minute == 0:
            try:
                do_monthly_tasks_and_announce()
            except Exception as e:
                print("Error in monthly job:", e)
            time.sleep(61)
        time.sleep(15)

threading.Thread(target=schedule_runner, daemon=True).start()

print("بات آماده است.")
bot.infinity_polling()
  
