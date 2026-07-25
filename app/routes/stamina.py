from __future__ import annotations

from collections.abc import Iterable

from app.rules import LOW_RESOURCE_MARKERS, STAMINA_BUTTON_MARKERS

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def select_stamina_action(
    message_text: str,
    buttons: list[ButtonInfo],
) -> tuple[SelectedAction | None, str | None]:
    """Select the existing quick stamina-potion action without changing behavior."""
    if not contains_any(message_text, LOW_RESOURCE_MARKERS):
        return None, None

    for button_text, row, column in buttons:
        if contains_any(button_text, STAMINA_BUTTON_MARKERS):
            return (
                button_text,
                row,
                column,
                "Выпить зелье стамины",
                "stamina_potions",
            ), "stamina"

    return None, None
