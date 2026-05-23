from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: set[int]
    vault_path: Path
    timezone: ZoneInfo
    openai_api_key: str
    openai_model: str


def _parse_user_ids(raw: str) -> set[int]:
    return {int(part.strip()) for part in raw.split(",") if part.strip()}


def load_settings() -> Settings:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    allowed = _parse_user_ids(os.getenv("ALLOWED_USER_IDS", ""))
    vault = Path(os.getenv("VAULT_PATH", ".")).expanduser().resolve()
    timezone = ZoneInfo(os.getenv("BOT_TIMEZONE", "Europe/Samara"))
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    return Settings(token, allowed, vault, timezone, openai_api_key, openai_model)
