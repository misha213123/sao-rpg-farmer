from __future__ import annotations

from dataclasses import dataclass

from app.routes.repair import REPAIR_FLOW, WORN_EQUIPMENT_MARKERS


LOW_RESOURCE_MARKERS = (
    "низкий уровень ресурсов",
    "мало стамины",
    "недостаточно стамины",
)

STAMINA_BUTTON_MARKERS = (
    "выпить зелье стамины",
    "восполнить стамину",
)

# Эти кнопки никогда не нажимаются обычной логикой.
NEVER_CLICK = (
    "профиль",
    "выпить зелье hp",
    "сбежать",
    "назад",
    "удар с разгона",
    "щит паладина",
    "призыв",
    "зелья",
)


@dataclass(frozen=True, slots=True)
class Rule:
    markers: tuple[str, ...]
    action_name: str
    counter: str | None = None


# Боевая логика и её приоритеты находятся в app/routes/combat.py.
STANDARD_RULES = (
    Rule(("забрать сокровища", "открыть сокровище", "сокровища"), "Сокровища", "treasures"),
    Rule(("продолжить поход",), "Продолжить поход"),
    Rule(("продолжить исследование",), "Продолжить исследование"),
    Rule(("начать исследование",), "Начать исследование"),
    Rule(("замок лорда кобольдов", "замок лорда кобольда"), "Замок лорда кобольдов"),
)
