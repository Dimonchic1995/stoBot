from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def build_service(creds_path: str):
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build("calendar", "v3", credentials=creds)


def list_events(
    creds_path: str,
    calendar_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    service = build_service(creds_path)
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start.isoformat() + "Z",
            timeMax=end.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return response.get("items", [])


def has_conflict(
    creds_path: str,
    calendar_id: str,
    start: datetime,
    end: datetime,
) -> bool:
    events = list_events(creds_path, calendar_id, start, end)
    return bool(events)


def create_event(
    creds_path: str,
    calendar_id: str,
    summary: str,
    description: str,
    start: datetime,
    duration_minutes: int,
) -> dict:
    service = build_service(creds_path)
    end = start + timedelta(minutes=duration_minutes)
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Kiev"},
        "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Kiev"},
    }
    return (
        service.events()
        .insert(calendarId=calendar_id, body=event)
        .execute()
    )
