from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from config import SERVICE_TYPES

SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'creds.json'

SERVICE_TYPE_COLORS = {
    "Рихтовка/покраска": "5",  # Yellow
    "ГБО": "10",               # Bold Green
    "СТО": "11",               # Bold Red
}

def add_to_calendar(summary, description, start_str, service_type,
                    duration_minutes=30, calendar_id=None,
                    user_id=None, chat_id=None, full_name=None,
                    phone=None, car=None):
    
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)

    start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
    end_time = start_time + timedelta(minutes=duration_minutes)

    color_id = SERVICE_TYPE_COLORS.get(service_type.split(' - ')[0], "1")  # Default: Blue

    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Europe/Kiev'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Europe/Kiev'},
        'colorId': color_id,
        'extendedProperties': {
            'private': {
                'user_id': str(user_id or ''),
                'chat_id': str(chat_id or ''),
                'full_name': full_name or '',
                'phone': phone or '',
                'car': car or '',
                'service_type': service_type or '',
            }
        }
    }

    calendar_id = calendar_id or 'primary'
    return service.events().insert(calendarId=calendar_id, body=event).execute()

def get_upcoming_events_for_reminders(days_ahead=0):
    from pprint import pprint
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.utcnow() + timedelta(hours=3)
    start_of_day = (now + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    reminders = []

    for service_name, info in SERVICE_TYPES.items():
        calendar_id = info.get("calendar_id")
        print(f"📅 Перевірка календаря '{calendar_id}' на дату: {start_of_day.date()}")

        try:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=start_of_day.isoformat() + 'Z',
                timeMax=end_of_day.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            print(f"🔍 Знайдено {len(events)} подій у {calendar_id}")

            for event in events:
                print("🔹 Подія:")
                pprint(event)
                ep = event.get('extendedProperties', {}).get('private', {})
                start_time = event['start'].get('dateTime')

                if ep.get('user_id') and ep.get('chat_id'):
                    reminders.append({
                        'user_id': int(ep['user_id']),
                        'chat_id': int(ep['chat_id']),
                        'full_name': ep.get('full_name', ''),
                        'phone': ep.get('phone', ''),
                        'datetime': start_time,
                        'car': ep.get('car', ''),
                        'service_type': ep.get('service_type', '')
                    })
                else:
                    print("⚠️ Пропущено: Немає user_id або chat_id")

        except Exception as e:
            print(f"❌ Помилка з календарем '{calendar_id}': {e}")

    print(f"✅ Усього нагадувань: {len(reminders)}")
    return reminders
