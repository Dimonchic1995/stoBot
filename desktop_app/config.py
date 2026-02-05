import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_CONFIG = {
    "bot_token": "",
    "shared_secret": "",
    "local_api_port": 8765,
    "google_creds_path": "",
    "service_calendar_map": {},
}


@dataclass
class AppConfig:
    bot_token: str = ""
    shared_secret: str = ""
    local_api_port: int = 8765
    google_creds_path: str = ""
    service_calendar_map: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> Tuple[bool, List[str]]:
        missing = []
        if not self.bot_token:
            missing.append("bot_token")
        if not self.shared_secret:
            missing.append("shared_secret")
        if not self.local_api_port:
            missing.append("local_api_port")
        if not self.google_creds_path:
            missing.append("google_creds_path")
        return (len(missing) == 0, missing)


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return AppConfig()
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return AppConfig()
    return AppConfig(
        bot_token=data.get("bot_token", ""),
        shared_secret=data.get("shared_secret", ""),
        local_api_port=int(data.get("local_api_port", 8765)),
        google_creds_path=data.get("google_creds_path", ""),
        service_calendar_map=data.get("service_calendar_map", {}) or {},
    )


def save_config(config_path: Path, config: AppConfig) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "bot_token": config.bot_token,
        "shared_secret": config.shared_secret,
        "local_api_port": config.local_api_port,
        "google_creds_path": config.google_creds_path,
        "service_calendar_map": config.service_calendar_map,
    }
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
