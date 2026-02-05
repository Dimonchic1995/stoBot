import datetime as dt
from typing import List, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarClient:
    def __init__(self, creds_path: str) -> None:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
        self.service = build("calendar", "v3", credentials=credentials)

    def list_events(
        self, calendar_id: str, time_min: dt.datetime, time_max: dt.datetime
    ) -> List[dict]:
        events_result = (
            self.service.events()
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

    def create_event(
        self,
        calendar_id: str,
        summary: str,
        description: str,
        start_dt: dt.datetime,
        end_dt: dt.datetime,
    ) -> Tuple[str, dict]:
        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Kiev"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Kiev"},
        }
        event = (
            self.service.events()
            .insert(calendarId=calendar_id, body=event_body)
            .execute()
        )
        return event["id"], event
