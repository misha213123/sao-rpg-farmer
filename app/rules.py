from __future__ import annotations

from dataclasses import dataclass


LOW_RESOURCE_MARKERS = (
    "низкий уровень ресурсов",
    "мало стамины",
    "недостаточно стамины",
)

STAMINA_BUTTON_MARKERS = (
    "выпить зелье стамины",
    "восполнить стамину",
)

NEVER_CLICK = (
    "выпить зелье hp",
    "сбежать",
)


@dataclass(frozen=True, slots=True)
class Rule:
    markers: tuple[str, ...]
    action_name: str
    counter: str | None = None


# Порядок важен: первое найденное правило побеждает.
STANDARD_RULES = (
    Rule(("обычная атака",), "Обычная атака", "fights"),
    Rule(("забрать сокровища", "открыть сокровище", "сокровища"), "Сокровища", "treasures"),
    Rule(("продолжить поход",), "Продолжить поход"),
    Rule(("продолжить исследование",), "Продолжить исследование"),
    Rule(("начать исследование",), "Начать исследование"),
    Rule(("замок лорда кобольдов", "замок лорда кобольда"), "Замок лорда кобольдов"),
    Rule(("локации",), "Локации"),
    Rule(("профиль",), "Профиль"),
)
