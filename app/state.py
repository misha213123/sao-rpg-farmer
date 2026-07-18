from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class RuntimeState:
    enabled: bool = False
    awaiting_floor: bool = False
    target_floor: int | None = None
    return_to_floor_mode: bool = False
    return_to_floor_step: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    clicks: int = 0
    fights: int = 0
    stamina_potions: int = 0
    treasures: int = 0
    repairs: int = 0
    repair_mode: bool = False
    repair_step: int = 0

    # Ежечасные маршруты: гильдия в :35, арена в :37 по Москве.
    scheduled_mode: bool = False
    scheduled_phase: str = ""
    scheduled_step: int = 0
    scheduled_last_guild_hour: str | None = None
    scheduled_last_arena_hour: str | None = None
    scheduled_runs: int = 0
    scheduled_confirm_clicks: int = 0
    scheduled_arena_clicks: int = 0

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
        floor = str(self.target_floor) if self.target_floor is not None else "не выбран"
        repair_status = f"да, шаг {self.repair_step + 1}" if self.repair_mode else "нет"
        return_status = (
            f"да, шаг {self.return_to_floor_step + 1}"
            if self.return_to_floor_mode
            else "нет"
        )
        scheduled_status = (
            f"{self.scheduled_phase or 'активен'}, шаг {self.scheduled_step}"
            if self.scheduled_mode
            else "нет"
        )
        return (
            f"Статус: {status}\n"
            f"Этаж: {floor}\n"
            f"Аптайм: {self.uptime_text()}\n"
            f"Нажатий: {self.clicks}\n"
            f"Атак: {self.fights}\n"
            f"Зелий стамины: {self.stamina_potions}\n"
            f"Сокровищ: {self.treasures}\n"
            f"Починок: {self.repairs}\n"
            f"Режим починки: {repair_status}\n"
            f"Возврат на этаж: {return_status}\n"
            f"Маршрут :35/:37 МСК: {scheduled_status}\n"
            f"Подтверждений атаки: {self.scheduled_confirm_clicks}\n"
            f"Рандомных боёв: {self.scheduled_arena_clicks}/5\n"
            f"Завершённых циклов: {self.scheduled_runs}\n"
            f"Последнее действие: {self.last_action}"
        )
