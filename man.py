# main.py
import os, json, time, threading
from datetime import datetime, timedelta
import telebot

# ---------- تنظیمات از متغیر محیطی ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID") or 0)
TZ = os.getenv("TZ")  # مثال: "Europe/Berlin" یا "Asia/Tehran"

if TZ:
    os.environ['TZ'] = TZ
    try:
        time.tzset()
    except:
        pass

bot = telebot.TeleBot(BOT_TOKEN)
DATA_FILE = "data.json"

# ---------- ذخیره/بارگذاری ----------
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

data = load_data()  # ساختار: { user_id: { "name":..., "reports": { "YYYY-MM-DD": {"hours":int,"tests":int,"presence":0/1,"points":int } }, "weekly":int, "monthly":int } }

# ---------- محاسبه امتیاز ----------
def calc_points(hours, tests, presence):
    pts = 0
    pts += int(hours) * 10
    pts += (int(tests) // 20) * 5
    if presence:
        pts += 10
    return pts

# ---------- helper برای ثبت گزارش (از پیوی) ----------
def record_report(user_id, name, hours, tests, presence):
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"name": name, "reports": {}, "weekly": 0, "monthly": 0}
    if today in data[uid]["reports"]:
        return False, "قبلا امروز ثبت شده"
    pts = calc_points(hours, tests, presence)
    data[uid]["reports"][today] = {"hours": hours, "tests": tests, "presence": 1 if presence else 0, "points": pts}
    data[uid]["weekly"] = data[uid].get("weekly", 0) + pts
    data[uid]["monthly"] = data[uid].get("monthly", 0) + pts
    data[uid]["name"] = name
    save_data(data)
    return True, pts

# ---------- دستورات کاربران (در پیوی بات) ----------
@bot.message_handler(commands=["start"])
def cmd_start(m):
    bot.reply_to(m, "سلام! برای ثبت فعالیت از دستورها استفاده کن:\n/study <hours>\n/test <count>\n/report  (ثبت حضور، +10) \n/score  (نمایش امتیاز)")

@bot.message_handler(commands=["study"])
def cmd_study(m):
    try:
        hours = float(m.text.split()[1])
    except:
        bot.reply_to(m, "مثال: /study 2  — برای ثبت 2 ساعت")
        return
    success, pts = record_report_partial(m.from_user.id, m.from_user.first_name, hours=hours)
    if success:
        bot.reply_to(m, f"✅ ثبت شد: {hours} ساعت. امتیاز اضافه‌شده: {int(hours)*10}")
    else:
        bot.reply_to(m, pts)

@bot.message_handler(commands=["test"])
def cmd_test(m):
    try:
        cnt = int(m.text.split()[1])
    except:
        bot.reply_to(m, "مثال: /test 40  — برای ثبت 40 تست")
        return
    success, pts = record_report_partial(m.from_user.id, m.from_user.first_name, tests=cnt)
    if success:
        bot.reply_to(m, f"✅ ثبت شد: {cnt} تست. امتیاز براساس هر 20 تست: {(cnt//20)*5}")
    else:
        bot.reply_to(m, pts)

@bot.message_handler(commands=["report"])
def cmd_presence(m):
    # ثبت حضور روزانه (یکبار در روز) در پیوی
    uid = str(m.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if uid in data and today in data[uid]["reports"]:
        bot.reply_to(m, "📌 امروز قبلاً گزارش داشتی.")
        return
    # اگر هنوز رکوردی از امروز وجود ندارد، ثبت با مقادیر صفر برای ساعت و تست و presence=1
    success, pts = record_report(m.from_user.id, m.from_user.first_name, hours=0, tests=0, presence=1)
    if success:
        bot.reply_to(m, f"✅ حضور ثبت شد — +10 امتیاز")
    else:
        bot.reply_to(m, pts)

# تابع کمکی‌ای که اجازه می‌دهد partial (قسمتی) ثبت شود تا کاربر بتواند ابتدا ساعت بزند، بعد تست و... 
def record_report_partial(user_id, name, hours=None, tests=None):
    today = datetime.now().strftime("%Y-%m-%d")
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"name": name, "reports": {}, "weekly": 0, "monthly": 0}
    # اگر امروز وجود دارد، مقدارها را جمع می‌کنیم (compile)
    if today in data[uid]["reports"]:
        rec = data[uid]["reports"][today]
        # اگر می‌خواهیم فقط اضافه کنیم:
        new_hours = rec.get("hours", 0) + (hours or 0)
        new_tests = rec.get("tests", 0) + (tests or 0)
        presence = rec.get("presence", 0)
        new_pts = calc_points(new_hours, new_tests, presence)
        # بروزرسانی: کم کردن قبلی از weekly/monthly و اضافه کردن جدید
        prev_pts = rec.get("points", 0)
        data[uid]["weekly"] = data[uid].get("weekly", 0) - prev_pts + new_pts
        data[uid]["monthly"] = data[uid].get("monthly", 0) - prev_pts + new_pts
        rec.update({"hours": new_hours, "tests": new_tests, "points": new_pts})
        save_data(data)
        return True, new_pts
    else:
        # ایجاد رکورد جدید با مقادیر ورودی (یا صفر)
        h = hours or 0
        t = tests or 0
        presence = 0
        pts = calc_points(h, t, presence)
        data[uid]["reports"][today] = {"hours": h, "tests": t, "presence": presence, "points": pts}
        data[uid]["weekly"] = data[uid].get("weekly", 0) + pts
        data[uid]["monthly"] = data[uid].get("monthly", 0) + pts
        data[uid]["name"] = name
        save_data(data)
        return True, pts

@bot.message_handler(commands=["score"])
def cmd_score(m):
    uid = str(m.from_user.id)
    total = sum([info.get("points",0) for info in data.get(uid,{}).get("reports",{} ).values()]) if uid in data else 0
    total_all = data.get(uid, {}).get("monthly", 0)
    bot.reply_to(m, f"📊 امتیاز امروز: {total}\n📅 امتیاز ماه: {total_all}")

@bot.message_handler(commands=["leaderboard"])
def cmd_leader(m):
    # جدول ماهانه را نشان میدهد
    arr = []
    for uid, info in data.items():
        arr.append((info.get("monthly",0), info.get("name","کاربر ناشناس")))
    arr.sort(reverse=True)
    if not arr:
        bot.reply_to(m, "هیچ امتیازی ثبت نشده.")
        return
    text = "🏆 جدول ماهانه:\n"
    for i, (pts,name) in enumerate(arr[:10], start=1):
        text += f"{i}. {name} — {pts} امتیاز\n"
    bot.reply_to(m, text)

# ---------- اعلام نتایج روزانه/هفتگی/ماهانه (قابلیت اجرای دستی توسط ادمین) ----------
def announce_daily():
    today = datetime.now().strftime("%Y-%m-%d")
    scores = []
    for uid, info in data.items():
        if today in info.get("reports", {}):
            p = info["reports"][today]["points"]
            scores.append((p, info.get("name","ناشناس"), uid))
    if not scores:
        bot.send_message(GROUP_CHAT_ID, "📋 امروز کسی فعالیتی ثبت نکرده.")
        return
    scores.sort(reverse=True)
    # نفر اول روز جایزه 20 می‌گیره (اضافه به weekly/monthly)
    top_pts, top_name, top_uid = scores[0]
    data[top_uid]["weekly"] = data[top_uid].get("weekly",0) + 20
    data[top_uid]["monthly"] = data[top_uid].get("monthly",0) + 20
    save_data(data)
    # پیام
    text = "📅 گزارش امروز:\n"
    for rank, (pts, name, _) in enumerate(scores, start=1):
        text += f"{rank}. {name} — {pts} امتیاز\n"
    text += f"\n🏅 نفر اول امروز: {top_name} — جایزه: +20 امتیاز"
    bot.send_message(GROUP_CHAT_ID, text)

@bot.message_handler(commands=["گزارش"])
def cmd_admin_report(m):
    # فقط ادمین گروه میتواند این دستور را در گروه اجرا کند
    try:
        member = bot.get_chat_member(GROUP_CHAT_ID, m.from_user.id)
        if member.status not in ("administrator","creator"):
            bot.reply_to(m, "⛔ فقط ادمین می‌تواند گزارش روزانه را اجرا کند.")
            return
    except Exception:
        bot.reply_to(m, "⛔ این دستور فقط در گروه اجرا می‌شود.")
        return
    announce_daily()
    bot.reply_to(m, "✅ گزارش روزانه اجرا شد.")

# ---------- زمانبندی خودکار (ساعت 22) ----------
def schedule_task(func, hour=22, minute=0, weekday=None, monthly=False):
    def runner():
        while True:
            now = datetime.now()
            if monthly:
                # اجرا در روز اول ماه
                if now.day == 1 and now.hour == hour and now.minute == minute:
                    func()
                    time.sleep(61)
            elif weekday is not None:
                # weekday: 0=Monday ... 6=Sunday ; اجرا در آن روز ساعت مشخص
                if now.weekday() == weekday and now.hour == hour and now.minute == minute:
                    func()
                    time.sleep(61)
            else:
                if now.hour == hour and now.minute == minute:
                    func()
                    time.sleep(61)
            time.sleep(20)
    t = threading.Thread(target=runner, daemon=True)
    t.start()

# زمانبندی‌ها
schedule_task(announce_daily, hour=22, minute=0)          # هر روز 22:00
schedule_task(lambda: bot.send_message(GROUP_CHAT_ID, announce_weekly_helper()), hour=22, minute=0, weekday=4)  # جمعه 22:00 -> ما تابع کمکی پایین را صدا میزنیم
schedule_task(lambda: announce_monthly_helper(), hour=22, minute=0, monthly=True)

# helper برای هفتگی/ماهانه
def announce_weekly_helper():
    # محاسبه برنده هفته، ارسال پیام، و ریست weekly
    arr = []
    for uid,info in data.items():
        arr.append((info.get("weekly",0), info.get("name","ناشناس"), uid))
    arr.sort(reverse=True)
    if not arr:
        return "این هفته هیچ امتیازی ثبت نشده."
    top = arr[0]
    # جایزه 20 امتیاز به نفر اول هفته
    data[top[2]]["monthly"] = data[top[2]].get("monthly",0) + 20
    data[top[2]]["weekly"] = 0
    save_data(data)
    return f"🥇 نفر اول هفته: {top[1]} — {top[0]} امتیاز (جایزه: +20)"

def announce_monthly_helper():
    arr = []
    for uid,info in data.items():
        arr.append((info.get("monthly",0), info.get("name","ناشناس"), uid))
    arr.sort(reverse=True)
    if not arr:
        bot.send_message(GROUP_CHAT_ID, "این ماه هیچ امتیازی ثبت نشده.")
        return
    top = arr[0]
    bot.send_message(GROUP_CHAT_ID, f"🏅 نفر اول ماه: {top[1]} — {top[0]} امتیاز")
    # ریست ماهانه
    for info in data.values():
        info["monthly"] = 0
    save_data(data)

print("Bot is running...")
bot.infinity_polling()
      
