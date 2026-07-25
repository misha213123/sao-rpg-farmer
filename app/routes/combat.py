from __future__ import annotations

from collections.abc import Iterable

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

# Порядок строгий: обычная атака используется только когда более сильных кнопок нет.
COMBAT_PRIORITIES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("скрытая атака", "скрыта"), "Скрытая атака"),
    (("удар 2 рук", "удар двух рук", "удар с двух рук"), "Удар 2 рук"),
    (("удар в воздухе",), "Удар в воздухе"),
    (("обычная атака",), "Обычная атака"),
)

# Кнопка входа/возобновления боя не конкурирует с четырьмя боевыми умениями.
ATTACK_ENTRY_MARKERS = ("атаковать",)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def select_combat_button(buttons: list[ButtonInfo]) -> ButtonInfo | None:
    """Возвращает боевую кнопку в строгом порядке приоритета."""
    for markers, _action_name in COMBAT_PRIORITIES:
        for button_text, row, column in buttons:
            if contains_any(button_text, markers):
                return button_text, row, column
    return None


def select_combat_action(buttons: list[ButtonInfo]) -> tuple[SelectedAction | None, str | None]:
    """Выбирает умение, а при их отсутствии — кнопку входа в бой."""
    for markers, action_name in COMBAT_PRIORITIES:
        for button_text, row, column in buttons:
            if contains_any(button_text, markers):
                return (
                    button_text,
                    row,
                    column,
                    action_name,
                    "fights",
                ), "combat"

    for button_text, row, column in buttons:
        if contains_any(button_text, ATTACK_ENTRY_MARKERS):
            return (
                button_text,
                row,
                column,
                "Атаковать",
                "fights",
            ), "combat"

    return None, None
