from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class RuntimeState:
    enabled: bool = False
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    clicks: int = 0
    fights: int = 0
    stamina_potions: int = 0
    treasures: int = 0
    last_action: str = "—"
    last_message_id: int | None = None
    last_signature: str | None = None

    def uptime_text(self) -> str:
        seconds = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def status_text(self) -> str:
        status = "включён ✅" if self.enabled else "выключен ⛔"
        return (
            f"Статус: {status}\n"
            f"Аптайм: {self.uptime_text()}\n"
            f"Нажатий: {self.clicks}\n"
            f"Атак: {self.fights}\n"
            f"Зелий стамины: {self.stamina_potions}\n"
            f"Сокровищ: {self.treasures}\n"
            f"Последнее действие: {self.last_action}"
        )
