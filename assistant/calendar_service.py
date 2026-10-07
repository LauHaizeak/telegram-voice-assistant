from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


@dataclass
class Event:
    id: str
    title: str
    start: datetime | date
    all_day: bool


class CalendarService:
    def __init__(self, creds: Credentials, calendar_id: str, tz: ZoneInfo) -> None:
        self._api = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._calendar_id = calendar_id
        self._tz = tz

    def list_events(self, first_day: date, days: int = 1) -> list[Event]:
        start = datetime.combine(first_day, time.min, self._tz)
        end = start + timedelta(days=days)
        result = (
            self._api.events()
            .list(
                calendarId=self._calendar_id,
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
        events = []
        for item in result.get("items", []):
            raw = item["start"]
            if "dateTime" in raw:
                when: datetime | date = datetime.fromisoformat(raw["dateTime"]).astimezone(self._tz)
                all_day = False
            else:
                when = date.fromisoformat(raw["date"])
                all_day = True
            events.append(Event(item["id"], item.get("summary", "(sans titre)"), when, all_day))
        return events

    def create_event(
        self, title: str, day: date, start: time | None, duration: timedelta
    ) -> Event:
        if start is None:
            body = {
                "summary": title,
                "start": {"date": day.isoformat()},
                "end": {"date": (day + timedelta(days=1)).isoformat()},
            }
        else:
            begin = datetime.combine(day, start, self._tz)
            body = {
                "summary": title,
                "start": {"dateTime": begin.isoformat(), "timeZone": str(self._tz)},
                "end": {"dateTime": (begin + duration).isoformat(), "timeZone": str(self._tz)},
            }
        created = self._api.events().insert(calendarId=self._calendar_id, body=body).execute()
        when = day if start is None else datetime.combine(day, start, self._tz)
        return Event(created["id"], title, when, start is None)

    def delete_event(self, event_id: str) -> None:
        self._api.events().delete(calendarId=self._calendar_id, eventId=event_id).execute()
