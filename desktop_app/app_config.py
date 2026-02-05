import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    bot_token: str = ""
    shared_secret: str = ""
    local_api_port: int = 8765
    google_creds_path: str = ""
    calendar_mappings: list[dict] = field(default_factory=list)


DEFAULT_CONFIG = AppConfig()


def load_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        return DEFAULT_CONFIG
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError:
        return DEFAULT_CONFIG

    return AppConfig(
        bot_token=payload.get("bot_token", ""),
        shared_secret=payload.get("shared_secret", ""),
        local_api_port=int(payload.get("local_api_port", 8765)),
        google_creds_path=payload.get("google_creds_path", ""),
        calendar_mappings=payload.get("calendar_mappings", []) or [],
    )


def save_config(config_path: Path, config: AppConfig) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "bot_token": config.bot_token,
        "shared_secret": config.shared_secret,
        "local_api_port": config.local_api_port,
        "google_creds_path": config.google_creds_path,
        "calendar_mappings": config.calendar_mappings,
    }
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def validate_config(config: AppConfig) -> list[str]:
    missing = []
    if not config.bot_token:
        missing.append("bot_token")
    if not config.shared_secret:
        missing.append("shared_secret")
    if not config.local_api_port:
        missing.append("local_api_port")
    if not config.google_creds_path:
        missing.append("google_creds_path")
    if not config.calendar_mappings:
        missing.append("calendar_mappings")
    else:
        for mapping in config.calendar_mappings:
            if not mapping.get("service_type") or not mapping.get("calendar_id"):
                missing.append("calendar_mappings")
                break
    return missing
