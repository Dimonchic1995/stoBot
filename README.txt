
1. Установи зависимости:
   pip install -r requirements.txt

2. В Google Cloud:
   - Створи сервисний аккаунт
   - Завантаж JSON-файл з ключем (назви його creds.json)
   - Дай доступ до Google Sheets (AutoServiceBot) на пошту з JSON-файлу

3. Створи Google таблицю "AutoServiceBot" і додай лист Sheet1

4. Додати ід телеграм груп в .env
BOT_TOKEN - бот клієнта
MANAGER_BOT_TOKEN - бот в групі менеджерів
MANAGER_CHAT_ID - ІД чату (знайти за посиланням "https://api.telegram.org/bot"MANAGER_BOT_TOKEN"/getUpdates")

4. Запусти бота:
   python main.py
