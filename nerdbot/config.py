from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    token: str
    prefix: str = "!"
    # When set, slash commands sync instantly to this guild only (handy for testing).
    dev_guild_id: int | None = None
    refresh_minutes: int = 15
    json_api: str = "https://json.tarkov.dev"
    boss_api: str = "https://bossdata.cultistcircle.workers.dev"
    log_level: str = "INFO"


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    guild = os.getenv("DEV_GUILD_ID", "").strip()
    return Settings(
        token=token,
        prefix=os.getenv("COMMAND_PREFIX", "!").strip() or "!",
        dev_guild_id=int(guild) if guild else None,
        refresh_minutes=max(5, int(os.getenv("REFRESH_MINUTES", "15"))),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
