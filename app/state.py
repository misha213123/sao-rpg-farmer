from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


MOSCOW_TZ = timezone(timedelta(hours=3))


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
    stamina_mode: bool = False
    stamina_step: int = 0
    stamina_route: str = ""

    # Ежечасные маршруты: гильдия в :35, арена в :37 по Москве.
    scheduled_mode: bool = False
    scheduled_phase: str = ""
    scheduled_step: int = 0
    scheduled_last_guild_hour: str | None = None
    scheduled_last_arena_hour: str | None = None
    scheduled_runs: int = 0
    scheduled_confirm_clicks: int = 0
    scheduled_arena_clicks: int = 0

    # Статистика рыбалки за текущий московский день.
    fishing_stats_date: str = field(
        default_factory=lambda: datetime.now(MOSCOW_TZ).date().isoformat()
    )
    fishing_chest_earnings: int = 0
    fishing_common: int = 0
    fishing_uncommon: int = 0
    fishing_rare: int = 0
    fishing_epic: int = 0
    fishing_legendary: int = 0

    # После передачи наживки Ниджи ждём новую поклёвку и не проверяем удочку сразу.
    fishing_waiting_after_niji: bool = False

    last_action: str = "—"
    last_message_id: int | None = None
    last_signature: str | None = None

    def reset_fishing_stats_if_needed(self) -> None:
        today = datetime.now(MOSCOW_TZ).date().isoformat()
        if self.fishing_stats_date == today:
            return
        self.fishing_stats_date = today
        self.fishing_chest_earnings = 0
        self.fishing_common = 0
        self.fishing_uncommon = 0
        self.fishing_rare = 0
        self.fishing_epic = 0
        self.fishing_legendary = 0

    def uptime_text(self) -> str:
        seconds = int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def status_text(self) -> str:
        self.reset_fishing_stats_if_needed()
        status = "включён ✅" if self.enabled else "выключен ⛔"
        floor = str(self.target_floor) if self.target_floor is not None else "не выбран"
        repair_status = f"да, шаг {self.repair_step + 1}" if self.repair_mode else "нет"
        stamina_status = (
            f"да, маршрут {self.stamina_route or 'не выбран'}, шаг {self.stamina_step + 1}"
            if self.stamina_mode
            else "нет"
        )
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
            f"Восстановление стамины: {stamina_status}\n"
            f"Возврат на этаж: {return_status}\n"
            f"Маршрут :35/:37 МСК: {scheduled_status}\n"
            f"Подтверждений атаки: {self.scheduled_confirm_clicks}\n"
            f"Рандомных боёв: {self.scheduled_arena_clicks}/5\n"
            f"Завершённых циклов: {self.scheduled_runs}\n"
            "\n🎣 Рыбалка сегодня:\n"
            f"С сундуков заработано: {self.fishing_chest_earnings}\n"
            f"Обычных рыб: {self.fishing_common}\n"
            f"Необычных рыб: {self.fishing_uncommon}\n"
            f"Редких рыб: {self.fishing_rare}\n"
            f"Эпических рыб: {self.fishing_epic}\n"
            f"Легендарных рыб: {self.fishing_legendary}\n"
            f"Последнее действие: {self.last_action}"
        )