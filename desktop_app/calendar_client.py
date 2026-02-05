import logging
from datetime import datetime, timedelta
from typing import List

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarClient:
    def __init__(self, creds_path: str):
        self.creds_path = creds_path
        self.service = None

    def _get_service(self):
        if not self.service:
            creds = service_account.Credentials.from_service_account_file(
                self.creds_path, scopes=SCOPES
            )
            self.service = build("calendar", "v3", credentials=creds)
        return self.service

    def list_events(self, calendar_id: str, time_min: datetime, time_max: datetime):
        service = self._get_service()
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min.isoformat() + "Z",
                timeMax=time_max.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return events_result.get("items", [])

    def check_conflict(self, calendar_id: str, start: datetime, end: datetime) -> bool:
        events = self.list_events(calendar_id, start, end)
        return len(events) > 0

    def create_event(self, calendar_id: str, summary: str, start: datetime, end: datetime) -> str:
        service = self._get_service()
        event = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": "Europe/Kiev"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Europe/Kiev"},
        }
        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logging.info("Created calendar event %s", created.get("id"))
        return created.get("id")

    @staticmethod
    def build_range(period: str) -> tuple[datetime, datetime]:
        now = datetime.utcnow() + timedelta(hours=3)
        if period == "week":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=7)
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        return start, end
