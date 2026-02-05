import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


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
    calendar_mapping: Dict[str, str] = field(default_factory=dict)

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.telegram_bot_token:
            missing.append("telegram_bot_token")
        if not self.shared_secret:
            missing.append("shared_secret")
        if not self.local_api_port:
            missing.append("local_api_port")
        if not self.google_creds_path:
            missing.append("google_creds_path")
        return missing


class ConfigManager:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = AppConfig()

    def load(self) -> AppConfig:
        if self.config_path.exists():
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.config = AppConfig(
                telegram_bot_token=raw.get("telegram_bot_token", ""),
                shared_secret=raw.get("shared_secret", ""),
                local_api_port=int(raw.get("local_api_port", 8765) or 8765),
                google_creds_path=raw.get("google_creds_path", ""),
                calendar_mapping=raw.get("calendar_mapping", {}),
            )
        return self.config

    def save(self, config: AppConfig) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "telegram_bot_token": config.telegram_bot_token,
            "shared_secret": config.shared_secret,
            "local_api_port": config.local_api_port,
            "google_creds_path": config.google_creds_path,
            "calendar_mapping": config.calendar_mapping,
        }
        self.config_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.config = config
