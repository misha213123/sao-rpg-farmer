from __future__ import annotations

from collections.abc import Iterable

from app.rules import LOW_RESOURCE_MARKERS, STAMINA_BUTTON_MARKERS
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

FALLBACK_FLOW: tuple[tuple[tuple[str, ...], str], ...] = (
    (("баффы",), "Баффы для восстановления стамины"),
    (("след",), "След"),
    (("использовать восстановление стамины", "восстановление стамины"), "Использовать восстановление стамины"),
    (("назад в исследование", "назад"), "Назад в исследование"),
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def select_stamina_action(
    message_text: str,
    buttons: list[ButtonInfo],
    state: RuntimeState,
) -> tuple[SelectedAction | None, str | None]:
    """Choose a quick potion or continue the fallback stamina route."""
    low_resource = contains_any(message_text, LOW_RESOURCE_MARKERS)

    if low_resource and not state.stamina_mode:
        for button_text, row, column in buttons:
            if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                return (
                    button_text,
                    row,
                    column,
                    "Выпить зелье стамины",
                    "stamina_potions",
                ), "stamina"

        state.stamina_mode = True
        state.stamina_step = 0

    if not state.stamina_mode:
        return None, None

    if state.stamina_step >= len(FALLBACK_FLOW):
        state.stamina_mode = False
        state.stamina_step = 0
        return None, None

    markers, action_name = FALLBACK_FLOW[state.stamina_step]
    for button_text, row, column in buttons:
        if contains_any(button_text, markers):
            return (
                button_text,
                row,
                column,
                action_name,
                None,
            ), "stamina_step"

    return None, "stamina_wait"
