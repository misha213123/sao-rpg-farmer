from __future__ import annotations

from typing import TypeAlias

ButtonInfo: TypeAlias = tuple[str, int, int]
RouteAction: TypeAlias = tuple[str, int, int, str, str | None]


def floor_button_matches(button_text: str, floor: int) -> bool:
    """Match the configured floor without confusing it with other numbers."""
    compact = button_text.replace("№", " ").replace("-", " ")
    tokens = compact.split()
    floor_text = str(floor)
    return (
        button_text == floor_text
        or f"этаж {floor_text}" in button_text
        or f"{floor_text} этаж" in button_text
        or floor_text in tokens
    )


def is_exploration_location(button_text: str) -> bool:
    """Return True only for a location inside the selected floor."""
    if "назад" in button_text:
        return False
    if "локация" not in button_text:
        return False
    if button_text.startswith("локации") or " локации" in button_text:
        return False
    return True


def is_main_explore_button(button_text: str) -> bool:
    """Match the main-menu Explore button, including decorative emoji."""
    return (
        "исследовать" in button_text
        and "продолжить" not in button_text
        and "начать" not in button_text
        and "исследование" not in button_text
    )


def select_farm_action(
    buttons: list[ButtonInfo],
    target_floor: int,
    target_location: int | None = None,
) -> tuple[RouteAction | None, str | None]:
    """Select the next action of the ordinary farming route.

    Location buttons are already flattened by Telegram row by row: left to right,
    then the next row. Therefore a single centred bottom button naturally becomes
    the last location in the list.
    """
    for button_text, row, column in buttons:
        if "продолжить исследование" in button_text:
            return (
                button_text,
                row,
                column,
                "Продолжить исследование",
                None,
            ), "navigation_finish"

    for button_text, row, column in buttons:
        if "начать исследование" in button_text:
            return (
                button_text,
                row,
                column,
                "Начать исследование",
                None,
            ), "navigation_finish"

    for button_text, row, column in buttons:
        if is_main_explore_button(button_text):
            return (
                button_text,
                row,
                column,
                "Исследовать",
                None,
            ), "navigation"

    for button_text, row, column in buttons:
        if floor_button_matches(button_text, target_floor):
            return (
                button_text,
                row,
                column,
                f"Этаж {target_floor}",
                None,
            ), "navigation"

    location_buttons = [
        item for item in buttons if is_exploration_location(item[0])
    ]
    if location_buttons:
        location_index = (target_location or len(location_buttons)) - 1
        if 0 <= location_index < len(location_buttons):
            button_text, row, column = location_buttons[location_index]
            return (
                button_text,
                row,
                column,
                f"Локация {location_index + 1}",
                None,
            ), "navigation"
        return None, "location_unavailable"

    for button_text, row, column in buttons:
        if "главное меню" in button_text:
            return (
                button_text,
                row,
                column,
                "Главное меню",
                None,
            ), "navigation"

    return None, None
