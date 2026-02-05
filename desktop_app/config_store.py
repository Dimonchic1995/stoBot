import json
import os
from dataclasses import dataclass, field
from typing import List, Dict


REQUIRED_FIELDS = [
    "telegram_bot_token",
    "shared_secret",
    "local_api_port",
    "google_creds_path",
]


@dataclass
class AppConfig:
    telegram_bot_token: str = ""
    shared_secret: str = ""
    local_api_port: int = 8765
    google_creds_path: str = ""
    service_calendar_mapping: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        if not os.path.exists(path):
            return cls()
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return cls(
            telegram_bot_token=data.get("telegram_bot_token", ""),
            shared_secret=data.get("shared_secret", ""),
            local_api_port=data.get("local_api_port", 8765),
            google_creds_path=data.get("google_creds_path", ""),
            service_calendar_mapping=data.get("service_calendar_mapping", []),
        )

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "telegram_bot_token": self.telegram_bot_token,
                    "shared_secret": self.shared_secret,
                    "local_api_port": self.local_api_port,
                    "google_creds_path": self.google_creds_path,
                    "service_calendar_mapping": self.service_calendar_mapping,
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )

    def validate(self):
        missing = []
        for field_name in REQUIRED_FIELDS:
            value = getattr(self, field_name)
            if field_name == "local_api_port":
                if not isinstance(value, int) or value <= 0:
                    missing.append(field_name)
                continue
            if not value:
                missing.append(field_name)
        return missing
