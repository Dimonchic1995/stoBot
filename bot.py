import logging
import os
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import requests
from google_calendar import add_to_calendar
from aiogram.types import BotCommand
import asyncio
from reminder import run_daily_check
from config import SERVICE_TYPES, POPULAR_CARS
from desktop_push import push_to_desktop

async def setup_bot_commands():
    commands = [
        BotCommand(command="/start", description="🚀 Почати роботу")
    ]
    await bot.set_my_commands(commands)

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
MANAGER_TOKEN = os.getenv("MANAGER_BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
user_data = {}

def notify_manager(data, full_name, chat_id):
    if not MANAGER_TOKEN or not chat_id:
        logging.error("❌ Відсутні токени або chat_id")
        return
    msg = (
        f"🔔 <b>Нова заявка</b>\n"
        f"👤 <b>Ім’я:</b> {full_name}\n"
        f"🚗 <b>Авто:</b> {data.get('car')}\n"
        f"🔧 <b>Послуга:</b> {data.get('service_type')} - {data.get('subtype')}\n"
        f"📅 <b>Час:</b> {data.get('datetime')}\n"
        f"📱 <b>Телефон:</b> {data.get('phone')}"
    )
    requests.post(
        f"https://api.telegram.org/bot{MANAGER_TOKEN}/sendMessage",
        data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    )

def make_reply_keyboard(options, row_width=2, request_contact=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for i in range(0, len(options), row_width):
        kb.row(*options[i:i+row_width])
    if request_contact:
        kb.add(KeyboardButton("📱 Поділитися номером", request_contact=True))
    return kb

@dp.message_handler(commands=['start'])
async def cmd_start(msg: types.Message):
    uid = msg.from_user.id
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("🚀 Почати"))
    await msg.answer("Привіт! Натисни «🚀 Почати» для старту запису на сервіс.", reply_markup=kb)
    user_data[uid] = {'step': None}
    push_to_desktop(uid, msg.from_user.full_name, msg.text or "/start", message_id=msg.message_id)

@dp.message_handler(lambda m: m.text == "🚀 Почати")
async def handle_start_button(m: types.Message):
    uid = m.from_user.id
    user_data[uid] = {}
    opts = list(SERVICE_TYPES.keys())
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for i in range(0, len(opts), 2):
        kb.row(*opts[i:i+2])
    await m.answer("Оберіть тип роботи:", reply_markup=kb)
    user_data[uid]['step'] = 'stype'


@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'stype')
async def step_stype(m: types.Message):
    uid = m.from_user.id
    stype = m.text.strip()
    if stype not in SERVICE_TYPES:
        await m.answer("❗ Оберіть правильний варіант із клавіатури.")
        return
    user_data[uid]['service_type'] = stype
    user_data[uid]['step'] = 'brand'
    opts = list(POPULAR_CARS.keys()) + ["✏️ Інша марка"]
    kb = make_reply_keyboard(opts, row_width=2)
    await m.answer(f"Тип: {stype}\nОберіть марку авто:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'brand')
async def step_brand(m: types.Message):
    uid = m.from_user.id
    text = m.text.strip()
    if text == "✏️ Інша марка":
        user_data[uid]['awaiting_brand'] = True
        await m.answer("Введіть марку вручну:", reply_markup=types.ReplyKeyboardRemove())
        return
    if text not in POPULAR_CARS:
        await m.answer("❗ Оберіть марку з клавіатури або '✏️ Інша марка'.")
        return
    user_data[uid].update({'brand': text, 'step': 'model'})
    opts = POPULAR_CARS[text] + ["✏️ Інша модель"]
    kb = make_reply_keyboard(opts, row_width=2)
    await m.answer(f"Марка: {text}\nОберіть модель:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('awaiting_brand'))
async def manual_brand(m: types.Message):
    uid = m.from_user.id
    user_data[uid].update({'brand': m.text.strip(), 'awaiting_brand': False, 'step': 'model'})
    opts = ["✏️ Інша модель"]
    kb = make_reply_keyboard(opts)
    await m.answer(f"Марка: {m.text}\nОберіть модель:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'model')
async def step_model(m: types.Message):
    uid = m.from_user.id
    text = m.text.strip()
    if text == "✏️ Інша модель":
        user_data[uid]['awaiting_model'] = True
        await m.answer("Введіть модель вручну:", reply_markup=types.ReplyKeyboardRemove())
        return
    user_data[uid].update({'car': f"{user_data[uid]['brand']} {text}", 'step': 'year'})
    years = [str(y) for y in range(datetime.now().year, 1995, -1)]
    kb = make_reply_keyboard(years, row_width=3)
    await m.answer(f"Модель: {text}\nОберіть рік:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('awaiting_model'))
async def manual_model(m: types.Message):
    uid = m.from_user.id
    car = f"{user_data[uid]['brand']} {m.text.strip()}"
    user_data[uid].update({'car': car, 'awaiting_model': False, 'step': 'year'})
    years = [str(y) for y in range(datetime.now().year, 1995, -1)]
    kb = make_reply_keyboard(years, row_width=3)
    await m.answer(f"Модель: {m.text}\nОберіть рік:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'year')
async def step_year(m: types.Message):
    uid = m.from_user.id
    year = m.text.strip()
    if not year.isdigit():
        await m.answer("❗ Оберіть рік з кнопок.")
        return
    user_data[uid]['car'] += f" ({year})"
    user_data[uid].update({'year': year, 'step': 'subtype'})
    st = user_data[uid]['service_type']
    subs = SERVICE_TYPES[st]['subtypes']
    kb = make_reply_keyboard(subs, row_width=2)
    await m.answer(f"Авто: {user_data[uid]['car']}\nОберіть підтип:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'subtype')
async def step_subtype(m: types.Message):
    uid = m.from_user.id
    subtype = m.text.strip()
    st = user_data[uid]['service_type']
    if subtype not in SERVICE_TYPES[st]['subtypes']:
        await m.answer("❗ Оберіть підтип з кнопок.")
        return
    user_data[uid].update({'subtype': subtype})
    if SERVICE_TYPES[st]['requires_datetime']:
        user_data[uid]['step'] = 'date'
        now = datetime.utcnow() + timedelta(hours=3)
        dates = []
        for i in range(14):
            d = now.date() + timedelta(days=i)
            if i == 0 and now.hour >= 17: continue
            dates.append(d.strftime("%Y-%m-%d"))
        kb = make_reply_keyboard(dates, row_width=3)
        await m.answer("Оберіть дату (YYYY-MM-DD):", reply_markup=kb)
    else:
        user_data[uid].update({'datetime': 'без дати', 'step': 'phone'})
        kb = make_reply_keyboard([], request_contact=True)
        await m.answer("Поділіться номером:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'date')
async def step_date(m: types.Message):
    uid = m.from_user.id
    date = m.text.strip()
    try:
        datetime.fromisoformat(date)
    except:
        await m.answer("❗ Введіть дату у форматі YYYY-MM-DD кнопками.")
        return
    user_data[uid].update({'selected_date': date, 'step': 'time'})
    wd = datetime.fromisoformat(date).weekday()
    start, end = ("09:00","13:00") if wd==5 else ("09:00","17:30")
    times = []
    t = datetime.fromisoformat(f"{date}T{start}")
    et = datetime.fromisoformat(f"{date}T{end}")
    now = datetime.utcnow() + timedelta(hours=3)
    while t <= et:
        if not (t.date()==now.date() and t<=now):
            times.append(t.strftime("%H:%M"))
        t += timedelta(minutes=30)
    kb = make_reply_keyboard(times, row_width=3)
    await m.answer("Оберіть час:", reply_markup=kb)

@dp.message_handler(lambda m: user_data.get(m.from_user.id, {}).get('step') == 'time')
async def step_time(m: types.Message):
    uid = m.from_user.id
    time = m.text.strip()
    user_data[uid].update({'datetime': f"{user_data[uid]['selected_date']} {time}", 'step': 'phone'})
    kb = make_reply_keyboard([], request_contact=True)
    await m.answer("Поділіться номером:", reply_markup=kb)

@dp.message_handler(content_types=types.ContentType.CONTACT)
async def step_contact(m: types.Message):
    uid = m.from_user.id
    data = user_data.get(uid, {})
    if data.get('step') != 'phone':
        return

    data['phone'] = m.contact.phone_number
    stype = data['service_type']
    calendar_id = SERVICE_TYPES[stype]['calendar_id']
    chat_id = SERVICE_TYPES[stype]['chat_id']

    # ➕ Лише якщо дата є — додаємо в календар
    if data.get('datetime') and data['datetime'] != 'без дати':
        try:
            add_to_calendar(
                summary=f"{stype} — {data['car']}",
                description=f"Телефон: {data['phone']}, Ім’я: {m.from_user.full_name}",
                start_str=data['datetime'],
                service_type=f"{stype} - {data['subtype']}",
                calendar_id=calendar_id,
                user_id=uid,
                chat_id=str(uid),
                full_name=m.from_user.full_name,
                phone=data['phone'],
                car=data['car']
            )
        except Exception as e:
            logging.error(f"❌ Calendar error: {e}")

    # 🟢 У будь-якому випадку — надсилаємо менеджеру
    try:
        notify_manager(data, m.from_user.full_name, chat_id)
    except Exception as e:
        logging.error(f"❌ Notify error: {e}")

    await m.answer("✅ Заявка прийнята!", reply_markup=types.ReplyKeyboardRemove())
    push_to_desktop(uid, m.from_user.full_name, "Нова заявка створена", message_id=m.message_id)
    user_data.pop(uid, None)

def schedule_jobs():
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    scheduler.add_job(lambda: run_daily_check(0), "cron", hour=9, minute=0)
    scheduler.add_job(lambda: run_daily_check(1), "cron", hour=19, minute=0)
    scheduler.start()
