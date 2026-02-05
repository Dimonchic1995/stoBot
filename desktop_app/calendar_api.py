import logging
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_service(creds_path: str):
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)


def list_events(creds_path: str, calendar_id: str, start_dt: datetime, end_dt: datetime):
    service = get_service(creds_path)
    events = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_dt.isoformat() + "Z",
            timeMax=end_dt.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events.get("items", [])


def has_conflict(creds_path: str, calendar_id: str, start_dt: datetime, end_dt: datetime):
    events = list_events(creds_path, calendar_id, start_dt, end_dt)
    return len(events) > 0


def create_event(creds_path: str, calendar_id: str, summary: str, start_dt: datetime, end_dt: datetime):
    service = get_service(creds_path)
    body = {
        "summary": summary,
        "start": {"dateTime": start_dt.isoformat() + "Z"},
        "end": {"dateTime": end_dt.isoformat() + "Z"},
    }
    event = service.events().insert(calendarId=calendar_id, body=body).execute()
    logging.info("Created calendar event %s", event.get("id"))
    return event.get("id")


def test_access(creds_path: str):
    service = get_service(creds_path)
    calendars = service.calendarList().list(maxResults=1).execute()
    return calendars.get("items", [])
