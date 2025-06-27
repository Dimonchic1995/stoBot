
1. Установи зависимости:
   pip install -r requirements.txt

2. В Google Cloud:
   - Створи сервисний аккаунт
   - Завантаж JSON-файл з ключем (назви його creds.json)

3. Додати пошту сервісного акаунту  в гугл календар. 

4. Заповнити відповідність груп телеграм та гугл календарів в "config" 

calendar_id - пошта власника каленраря
chat_id (знайти за посиланням "https://api.telegram.org/bot"MANAGER_BOT_TOKEN"/getUpdates")

5. Додати ід телеграм груп в .env
BOT_TOKEN - бот клієнта
MANAGER_BOT_TOKEN - бот в групі менеджерів


6. Запусти бота:
   python main.py


Оновлення конфігурації
git status                       # подивись, що змінилося
git add .                        # додай всі зміни
git commit -m "Опис змін"        # зроби коміт
git push origin main             # відправ зміни на GitHub (або іншу гілку, якщо потрібно)

Оновлення проекту на сервері
cd ~/stoBot
git pull origin main         # отримаєш свіжі зміни

sudo docker-compose build --no-cache
sudo docker-compose down
sudo docker-compose up -d
sudo docker ps