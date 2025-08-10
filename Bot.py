# bot.py
# -*- coding: utf-8 -*-
import os
import json
import time
import threading
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
# users: { user_id(str): { "name":str, "reports": { "YYYY-MM-DD": {"hours":int, "tests":int, "presence":0/1, "points":int} }, "weekly":int, "monthly":int } }
data = load_data()
if "users" not in data:
    data["users"] = {}
if "daily_bonus_dates" not in data:
    data["daily_bonus_dates"] = []  # تاریخ‌هایی که پاداش پیشرفت و نفر اول داده شده (فرمت YYYY-MM-DD)
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

# ---------- ثبت یا به‌روزرسانی گزارش روزانه (می‌تواند partial باشد) ----------
def record_activity(user_id:int, name:str, add_hours:int=0, add_tests:int=0, set_presence:bool=False):
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)
    users = data["users"]
    if uid not in users:
        users[uid] = {"name": name, "reports": {}, "weekly": 0, "monthly": 0}
    # اگر رکورد امروز وجود دارد، مجموع کن؛ در غیر این صورت ایجاد کن.
    if today in users[uid]["reports"]:
        rec = users[uid]["reports"][today]
        prev_points = rec.get("points", 0)
        new_hours = rec.get("hours", 0) + (add_hours or 0)
        new_tests = rec.get("tests", 0) + (add_tests or 0)
        presence = 1 if (rec.get("presence", 0) or set_presence) else 0
        new_points = calc_points(new_hours, new_tests, bool(presence))
        # بروز رسانی امتیازات هفته و ماه با کسر قبلی و اضافه کردن جدید
        users[uid]["weekly"] = users[uid].get("weekly", 0) - prev_points + new_points
        users[uid]["monthly"] = users[uid].get("monthly", 0) - prev_points + new_points
        rec.update({"hours": new_hours, "tests": new_tests, "presence": presence, "points": new_points})
    else:
        h = add_hours or 0
        t = add_tests or 0
        p = 1 if set_presence else 0
        pts = calc_points(h, t, bool(p))
        users[uid]["reports"][today] = {"hours": h, "tests": t, "presence": p, "points": pts}
        users[uid]["weekly"] = users[uid].get("weekly", 0) + pts
        users[uid]["monthly"] = users[uid].get("monthly", 0) + pts
    users[uid]["name"] = name
    save_data(data)
    return users[uid]["reports"][today]["points"]

# ---------- دستورات کاربری (در پیوی بات) ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    txt = ("سلام!\n\n"
           "دستورها در پیوی با بات:\n"
           "/study <hours> — ثبت ساعت مطالعه (هر ساعت = 10 امتیاز)\n"
           "/test <count> — ثبت تعداد تست (هر 20 تست = 5 امتیاز)\n"
           "/report — ثبت حضور روزانه (+10 امتیاز، فقط یک‌بار در روز)\n"
           "/score — نمایش امتیاز امروز و ماه\n"
           "/leaderboard — جدول ماهانه\n\n"
           "برای ثبت /study یا /test حتما عدد پشت دستور بنویس.")
    bot.reply_to(m, txt)

@bot.message_handler(commands=["study"])
def cmd_study(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "مثال: /study 3  (برای ثبت 3 ساعت)")
        return
    try:
        hours = int(float(parts[1]))
    except:
        bot.reply_to(m, "ساعت باید عدد باشد. مثال: /study 2")
        return
    pts = record_activity(m.from_user.id, m.from_user.first_name, add_hours=hours)
    bot.reply_to(m, f"✅ ثبت شد: {hours} ساعت مطالعه — (+{hours*10} امتیاز)\nامتیاز روزانه شما: {pts}")

@bot.message_handler(commands=["test"])
def cmd_test(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "مثال: /test 40  (برای ثبت 40 تست)")
        return
    try:
        cnt = int(parts[1])
    except:
        bot.reply_to(m, "تعداد تست باید عدد صحیح باشد. مثال: /test 40")
        return
    pts = record_activity(m.from_user.id, m.from_user.first_name, add_tests=cnt)
    added = (cnt // 20) * 5
    if added == 0:
        bot.reply_to(m, "⚠️ برای گرفتن امتیاز باید حداقل 20 تست وارد کنید.")
    else:
        bot.reply_to(m, f"✅ ثبت شد: {cnt} تست — (+{added} امتیاز)\nامتیاز روزانه شما: {data['users'][str(m.from_user.id)]['reports'][datetime.now().strftime('%Y-%m-%d')]['points']}")

@bot.message_handler(commands=["report"])
def cmd_presence(m):
    uid = m.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    u = data["users"].get(str(uid), {})
    if today in u.get("reports", {}):
        bot.reply_to(m, "📌 امروز قبلاً ثبت شده است (برای ثبت حضور باید از قبل گزارش نداشته باشی).")
        return
    pts = record_activity(uid, m.from_user.first_name, add_hours=0, add_tests=0, set_presence=True)
    bot.reply_to(m, f"✅ حضور ثبت شد — +10 امتیاز\nامتیاز امروز شما: {pts}")

@bot.message_handler(commands=["score"])
def cmd_score(m):
    uid = str(m.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid not in data["users"]:
        bot.reply_to(m, "هنوز امتیازی برای شما ثبت نشده.")
        return
    today_pts = data["users"][uid]["reports"].get(today, {}).get("points", 0)
    month_pts = data["users"][uid].get("monthly", 0)
    bot.reply_to(m, f"📊 امتیاز امروز: {today_pts}\n📅 مجموع ماه: {month_pts}")

@bot.message_handler(commands=["leaderboard"])
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
            bot.reply_to(m, "⛔ فقط ادمین‌ یا سازنده گروه می‌تواند این دستور را اجرا کند.")
            return
    except Exception as e:
        bot.reply_to(m, "خطا در بررسی وضعیت ادمین.")
        return
    do_daily_tasks_and_announce()

# ---------- وظایف روزانه — محاسبه پیشرفت و جایزه نفر اول ----------
def do_daily_tasks_and_announce():
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday = yesterday_dt.strftime("%Y-%m-%d")

    users = data["users"]
    # جمع کردن امتیازات امروز
    today_list = []
    for uid, info in users.items():
        rep = info.get("reports", {})
        if today in rep:
            pts = rep[today].get("points", 0)
            today_list.append((pts, info.get("name", "ناشناس"), uid))

    if not today_list:
        bot.send_message(GROUP_CHAT_ID, "📋 امروز کسی گزارش ثبت نکرد.")
        return

    # نفر اول روز (10 امتیاز جایزه)
    today_list.sort(reverse=True, key=lambda x: x[0])
    top_pts, top_name, top_uid = today_list[0]
    # جلوگیری از دوبار جایزه در یک روز با چک روی daily_bonus_dates
    if today not in data.get("daily_bonus_dates", []):
        # جایزه نفر اول روز
        users[top_uid]["weekly"] = users[top_uid].get("weekly", 0) + 10
        users[top_uid]["monthly"] = users[top_uid].get("monthly", 0) + 10
        # جایزه برای هر کسی که نسبت به دیروز پیشرفت داشته (5 امتیاز)
        progressed = []
        for pts, name, uid in today_list:
            # امتیاز دیروز (اگر داشته)
            y_pts = users.get(uid, {}).get("reports", {}).get(yesterday, {}).get("points", 0)
            if pts > y_pts:
                users[uid]["weekly"] = users[uid].get("weekly", 0) + 5
                users[uid]["monthly"] = users[uid].get("monthly", 0) + 5
                progressed.append(name)
        # ثبت تاریخ که جایزه امروز داده شده
        data.setdefault("daily_bonus_dates", []).append(today)
        save_data(data)

        # ارسال پیام در گروه
        msg = "📅 گزارش روزانه:\n\n"
        for rank, (pts, name, uid) in enumerate(today_list, start=1):
            msg += f"{rank}. {name} — {pts} امتیاز\n"
        msg += f"\n🏅 نفر اول امروز: {top_name} — {top_pts} امتیاز (+10 امتیاز جایزه)\n"
        if progressed:
            msg += "🎯 افرادی که نسبت به دیروز پیشرفت کردند (هر کدام +5 امتیاز):\n"
            msg += ", ".join(progressed) + "\n"
        bot.send_message(GROUP_CHAT_ID, msg)
    else:
        # اگر برای امروز قبلاً جایزه داده شده فقط گزارش را ارسال می‌کنیم (بدون دوباره جایزه دادن)
        msg = "📅 گزارش روزانه (تکراری):\n\n"
        for rank, (pts, name, uid) in enumerate(today_list, start=1):
            msg += f"{rank}. {name} — {pts} امتیاز\n"
        bot.send_message(GROUP_CHAT_ID, msg)

# ---------- وظایف هفتگی و ماهانه ----------
def do_weekly_tasks_and_announce():
    # محاسبه برنده هفته (جمع جدول weekly) و دادن جایزه 20 امتیاز
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
    # ریست امتیازهای هفتگی
    for info in users.values():
        info["weekly"] = 0
    save_data(data)

def do_monthly_tasks_and_announce():
    # اعلام نفر اول ماه و ریست ماهانه
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
        # جمعه (weekday 4) ساعت 22 -> توجه: Python weekday: Monday=0 ... Sunday=6 ; جمعه=4
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
           
