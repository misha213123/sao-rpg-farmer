from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "replace_me":
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    api_id: int
    api_hash: str
    string_session: str
    game_bot: str
    auto_start: bool
    click_delay_min: float
    click_delay_max: float
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        api_id_raw = _required("API_ID")
        try:
            api_id = int(api_id_raw)
        except ValueError as exc:
            raise RuntimeError("API_ID must be an integer") from exc

        delay_min = float(os.getenv("CLICK_DELAY_MIN", "0.7"))
        delay_max = float(os.getenv("CLICK_DELAY_MAX", "1.4"))
        if delay_min < 0 or delay_max < delay_min:
            raise RuntimeError("Invalid CLICK_DELAY_MIN/CLICK_DELAY_MAX values")

        game_bot = _required("GAME_BOT")
        if game_bot.startswith("https://t.me/"):
            game_bot = "@" + game_bot.rsplit("/", 1)[-1]

        return cls(
            api_id=api_id,
            api_hash=_required("API_HASH"),
            string_session=_required("STRING_SESSION"),
            game_bot=game_bot,
            auto_start=_as_bool(os.getenv("AUTO_START"), False),
            click_delay_min=delay_min,
            click_delay_max=delay_max,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
