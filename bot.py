import logging
import os
from aiogram import Bot, Dispatcher, types
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google_calendar import add_to_calendar
from aiogram.types import BotCommand
import asyncio
from reminder import run_daily_check
from config import SERVICE_TYPES, POPULAR_CARS

def notify_manager(data, full_name, chat_id):
    load_dotenv()
    token = os.getenv("MANAGER_BOT_TOKEN")

    if not token or not chat_id:
        logging.error("❌ Немає токену або chat_id")
        return

    message = f"""🔔 <b>Нова заявка</b>
👤 <b>Ім'я:</b> {full_name}
🚗 <b>Авто:</b> {data.get('car')}
🔧 <b>Послуга:</b> {data.get('service_type', '') + " - " + data.get('subtype', '')}
📅 <b>Час:</b> {data.get('datetime')}
📱 <b>Телефон:</b> {data.get('phone')}"""

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, data=payload)
        logging.info(f"📨 Надіслано [{chat_id}]: {r.status_code} | {r.text}")
    except Exception as e:
        logging.error(f"❌ Помилка надсилання в Telegram: {e}")


API_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

user_data = {}




@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("🛠 Записатися на сервіс")
    await message.answer("Привіт! Я бот автосервісу. Оберіть дію:",
                         reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "🛠 Записатися на сервіс")
async def begin_registration(message: types.Message):
    user_data[message.from_user.id] = {}
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for brand in POPULAR_CARS:
        keyboard.insert(
            types.InlineKeyboardButton(brand, callback_data=f"brand_{brand}"))
    keyboard.add(
        types.InlineKeyboardButton("✏️ Інша марка",
                                   callback_data="brand_other"))
    await message.answer("Оберіть марку авто:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("brand_"))
async def choose_model(c: types.CallbackQuery):
    brand = c.data.split("_", 1)[1]
    if brand == "other":
        user_data[c.from_user.id]['awaiting_brand'] = True
        await bot.send_message(c.from_user.id, "Введіть марку вручну:")
    else:
        user_data[c.from_user.id]['brand'] = brand
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for model in POPULAR_CARS[brand]:
            keyboard.insert(
                types.InlineKeyboardButton(model,
                                           callback_data=f"model_{model}"))
        keyboard.add(
            types.InlineKeyboardButton("✏️ Інша модель",
                                       callback_data="model_other"))
        await bot.send_message(c.from_user.id,
                               f"Оберіть модель {brand}:",
                               reply_markup=keyboard)
    await bot.answer_callback_query(c.id)


@dp.callback_query_handler(lambda c: c.data.startswith("model_"))
async def choose_year(c: types.CallbackQuery):
    model = c.data.split("_", 1)[1]
    if model == "other":
        user_data[c.from_user.id]['awaiting_model'] = True
        await bot.send_message(c.from_user.id, "Введіть модель вручну:")
    else:
        user_data[c.from_user.
                  id]['car'] = f"{user_data[c.from_user.id]['brand']} {model}"
    await send_year_keyboard(c.from_user.id)
    await bot.answer_callback_query(c.id)

async def send_year_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=4)
    for year in range(datetime.now().year, 1995, -1):
        keyboard.insert(
            types.InlineKeyboardButton(str(year),
                                       callback_data=f"year_{year}"))
    await bot.send_message(user_id,
                           "Оберіть рік випуску авто:",
                           reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data.startswith("year_"))
async def after_year_selected(c: types.CallbackQuery):
    year = c.data.split("_")[1]
    uid = c.from_user.id
    user_data[uid]['year'] = year

    # Додаємо рік до car
    brand_model = user_data[uid]['car']
    user_data[uid]['car'] = f"{brand_model} ({year})"

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for stype in SERVICE_TYPES:
        keyboard.add(
            types.InlineKeyboardButton(stype, callback_data=f"stype_{stype}"))
    await bot.send_message(
        uid,
        f"🚗 Ви обрали авто: {user_data[uid]['car']}\nОберіть тип звернення:",
        reply_markup=keyboard)
    await bot.answer_callback_query(c.id)


@dp.callback_query_handler(lambda c: c.data.startswith("stype_"))
async def choose_subtype(c: types.CallbackQuery):
    stype = c.data.split("_", 1)[1]
    user_data[c.from_user.id]['service_type'] = stype

    subtypes = SERVICE_TYPES[stype]["subtypes"]
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for sub in subtypes:
        keyboard.add(types.InlineKeyboardButton(sub, callback_data=f"subtype_{sub}"))

    await bot.send_message(c.from_user.id, "Оберіть підтип:", reply_markup=keyboard)
    await bot.answer_callback_query(c.id)

@dp.callback_query_handler(lambda c: c.data.startswith("subtype_"))
async def handle_subtype(c: types.CallbackQuery):
    subtype = c.data.split("_", 1)[1]
    uid = c.from_user.id
    user_data[uid]['subtype'] = subtype

    stype = user_data[uid]['service_type']
    if SERVICE_TYPES[stype]["requires_datetime"]:
        await show_date_keyboard(c)
    else:
        user_data[uid]['datetime'] = "без дати"
        user_data[uid]['step'] = 'phone'
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(types.KeyboardButton("📱 Поділитись номером", request_contact=True))
        await bot.send_message(uid, "Натисніть кнопку нижче, щоб поділитися номером телефону:", reply_markup=keyboard)

    await bot.answer_callback_query(c.id)

@dp.message_handler()
async def handle_manual_input(message: types.Message):
    uid = message.from_user.id
    if user_data.get(uid, {}).get('awaiting_brand'):
        user_data[uid]['brand'] = message.text
        user_data[uid]['awaiting_brand'] = False
        await message.answer("Тепер введіть модель авто:")
        user_data[uid]['awaiting_model'] = True
    elif user_data.get(uid, {}).get('awaiting_model'):
        user_data[uid]['car'] = f"{user_data[uid]['brand']} {message.text}"
        user_data[uid]['awaiting_model'] = False
        await send_year_keyboard(uid)


async def show_date_keyboard(target):
    now = datetime.utcnow() + timedelta(hours=3)
    keyboard = types.InlineKeyboardMarkup(row_width=3)
    for i in range(14):
        date = now.date() + timedelta(days=i)
        if i == 0 and now.hour >= 17:
            continue
        keyboard.insert(
            types.InlineKeyboardButton(text=date.strftime("%d.%m"),
                                       callback_data=f"date_{date}"))

    if isinstance(target, types.CallbackQuery):
        await bot.send_message(target.from_user.id,
                               "Оберіть дату запису:",
                               reply_markup=keyboard)
    else:
        await target.answer("Оберіть дату запису:", reply_markup=keyboard)

    @dp.callback_query_handler(lambda c: c.data.startswith("date_"))
    async def handle_date_choice(callback_query: types.CallbackQuery):
        date_str = callback_query.data.split("_")[1]
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        weekday = selected_date.weekday()  # Пн = 0, Нд = 6

        if weekday == 6:
            await bot.answer_callback_query(callback_query.id)
            await bot.send_message(
                callback_query.from_user.id,
                "⛔ У неділю запис недоступний. Оберіть інший день.")
            return

        user_data[callback_query.from_user.id]['selected_date'] = date_str
        keyboard = types.InlineKeyboardMarkup(row_width=4)

        # 🕘 Часові межі для запису
        if weekday == 5:  # Субота
            start_time = datetime.strptime("09:00", "%H:%M")
            end_time = datetime.strptime("13:00", "%H:%M")
        else:  # Пн-Пт
            start_time = datetime.strptime("09:00", "%H:%M")
            end_time = datetime.strptime("17:30", "%H:%M")

        now = datetime.utcnow() + timedelta(hours=3)

        time_cursor = start_time
        while time_cursor <= end_time:
            time_slot = time_cursor.strftime("%H:%M")
            slot_dt = datetime.strptime(f"{date_str} {time_slot}",
                                        "%Y-%m-%d %H:%M")
            if selected_date == now.date() and slot_dt <= now:
                time_cursor += timedelta(minutes=30)
                continue
            keyboard.insert(
                types.InlineKeyboardButton(text=time_slot,
                                           callback_data=f"time_{time_slot}"))
            time_cursor += timedelta(minutes=30)

        await bot.send_message(callback_query.from_user.id,
                               "Оберіть зручний час:",
                               reply_markup=keyboard)
        await bot.answer_callback_query(callback_query.id)


@dp.callback_query_handler(lambda c: c.data.startswith("time_"))
async def handle_time_choice(callback_query: types.CallbackQuery):
    time_str = callback_query.data.split("_")[1]
    date_str = user_data[callback_query.from_user.id]['selected_date']
    full_datetime = f"{date_str} {time_str}"
    user_data[callback_query.from_user.id]['datetime'] = full_datetime
    user_data[callback_query.from_user.id]['step'] = 'phone'
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
    keyboard.add(
        types.KeyboardButton("📱 Поділитись номером", request_contact=True))
    await bot.send_message(
        callback_query.from_user.id,
        f"Обрано {full_datetime}. Натисніть кнопку нижче, щоб поділитися номером телефону:",
        reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)


@dp.message_handler(content_types=types.ContentType.CONTACT)
async def get_contact(message: types.Message):
    if message.contact and message.contact.phone_number:
        data = user_data.get(message.from_user.id, {})
        data['phone'] = message.contact.phone_number

        stype = data.get('service_type')
        calendar_id = SERVICE_TYPES.get(stype, {}).get("calendar_id")
        chat_id = SERVICE_TYPES.get(stype, {}).get("chat_id")



        # 📅 Календар
        try:
            add_to_calendar(
                summary=f"{stype} — {data.get('car')}",
                description=f"Телефон: {data.get('phone')}, Ім’я: {message.from_user.full_name}",
                start_str=data.get('datetime'),
                service_type=f"{stype} - {data.get('subtype', '')}",
                calendar_id=calendar_id,
                user_id=message.from_user.id,
                chat_id=str(message.from_user.id),
                full_name=message.from_user.full_name,
                phone=data.get('phone'),
                car=data.get('car')
            )
        except Exception as e:
            logging.error(f"❌ Помилка календаря: {e}")

        # 💬 Повідомлення в групу
        try:
            notify_manager(data, message.from_user.full_name, chat_id)
        except Exception as e:
            logging.error(f"❌ Не вдалося надіслати повідомлення менеджеру: {e}")
        
        # ✅ Повідомлення клієнту
        await message.answer(
            "✅ Ваша заявка успішно прийнята!\n"
            "Очікуйте дзвінка менеджера найближчим часом."
        )

        user_data.pop(message.from_user.id, None)

@dp.message_handler(
    lambda message: message.text == "📅 Вказати дату діагностики")
async def save_diag_date(message: types.Message):
    await message.answer(
        "Введіть дату останньої діагностики (формат: 2025-06-01):")
    user_data[message.from_user.id] = {'step': 'diag_date'}


@dp.message_handler(lambda message: user_data.get(message.from_user.id, {}).
                    get('step') == 'diag_date')
async def get_diag_date(message: types.Message):
    date = message.text
    append_record([
        str(datetime.now()), message.from_user.full_name,
        f"Дата останньої діагностики: {date}", "", "",
        str(message.from_user.id)
    ])
    await message.answer("✅ Дата діагностики збережена!")





# 🟩 Запуск з шедулером з Google Calendar
async def main():
    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    await bot.set_my_commands(
        [BotCommand(command="start", description="Запустити бота")])

    # 🔔 В день запису о 09:00
    scheduler.add_job(lambda: asyncio.create_task(run_daily_check(offset_days=0)), "cron", hour=9, minute=0)

    # 🔔 За день до запису о 19:00
    scheduler.add_job(lambda: asyncio.create_task(run_daily_check(offset_days=1)), "cron", hour=19, minute=0)

    scheduler.start()
    await dp.start_polling(bot)



#import asyncio
#from reminder import run_daily_check  # або твій актуальний файл

#async def test_calendar_reminders():
#    await run_daily_check(offset_days=0)  # Сьогодні
#    await run_daily_check(offset_days=1)  # Завтра

#asyncio.run(test_calendar_reminders())
