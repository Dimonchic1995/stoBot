from datetime import datetime, timedelta
from aiogram import Bot
from dotenv import load_dotenv
import os

from google_calendar import get_upcoming_events_for_reminders

load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=API_TOKEN)

async def run_daily_check(offset_days=0):
    print(f"🔍 Запуск перевірки нагадувань... (offset_days={offset_days})")

    try:
        # 📅 Отримуємо всі події з extendedProperties
        reminders = get_upcoming_events_for_reminders(days_ahead=offset_days)
    except Exception as e:
        print(f"❌ Помилка при зчитуванні календаря: {e}")
        return

    for record in reminders:
        chat_id = record['chat_id']
        full_name = record['full_name']
        service_type = record['service_type']
        car = record['car']
        dt_str = record['datetime']

        if not chat_id or not dt_str:
            continue

        try:
            dt_formatted = datetime.fromisoformat(dt_str).strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            print(f"❌ Не вдалося обробити дату: {dt_str} → {e}")
            continue

        message = (
            f"🔔 Нагадування: завтра у вас запис на {dt_formatted}.\n"
            f"🚗 {car}\n🔧 {service_type}"
            if offset_days == 1 else
            f"🔔 Нагадування: сьогодні ваш запис на {dt_formatted}.\n"
            f"🚗 {car}\n🔧 {service_type}"
        )

        try:
            print(f"📨 Відправка повідомлення до {chat_id}: {message}")
            await bot.send_message(chat_id=int(chat_id), text=message)
            print("✅ Успішно відправлено")
        except Exception as e:
            print(f"❌ Помилка надсилання до {chat_id}: {e}")
