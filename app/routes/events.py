from __future__ import annotations

from collections.abc import Iterable
from typing import TypeAlias

ButtonInfo: TypeAlias = tuple[str, int, int]
RouteAction: TypeAlias = tuple[str, int, int, str, str | None]

EVENT_MARKERS = (
    "активное событие",
    "событие:",
    "откажитесь от него",
    "выберите действие",
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def is_event_message(message_text: str, buttons: list[ButtonInfo]) -> bool:
    """Detect a random event that blocks ordinary exploration."""
    if contains_any(message_text, EVENT_MARKERS):
        return True
    return any("отказаться от события" in text for text, _, _ in buttons)


def select_player_encounter_action(
    message_text: str,
    buttons: list[ButtonInfo],
) -> tuple[RouteAction | None, str | None]:
    """For Encounter with player, preserve the existing Rob action."""
    if (
        "встреча с игроком" not in message_text
        and "вы столкнулись с" not in message_text
    ):
        return None, None

    for button_text, row, column in buttons:
        if "ограбить" in button_text:
            return (
                button_text,
                row,
                column,
                "Ограбить игрока",
                None,
            ), "player_encounter"

    return None, None


def select_random_event_action(
    message_text: str,
    buttons: list[ButtonInfo],
    automation_mode: str = "farm",
) -> tuple[RouteAction | None, str | None]:
    """Select an action for blocking exploration events.

    Special events are handled before generic event detection so they work even
    when the game message does not contain the usual random-event markers.
    """
    # Событие 17 этажа «Логово теней» автоматически закрываем только в режимах
    # обычного фарма. Полуавтомат, рыбалка и режим только Арена/Гильдия не трогаем.
    if automation_mode in ("farm", "full") and "логово теней" in message_text:
        for button_text, row, column in buttons:
            if button_text == "уйти" or button_text.endswith(" уйти"):
                return (
                    button_text,
                    row,
                    column,
                    "Логово теней: уйти",
                    None,
                ), "shadow_lair_exit"
        return None, "shadow_lair_wait"

    # Событие второго этажа «Мастер боевых искусств» обрабатывается только
    # обычным фармом: полуавтоматический режим использует отдельный маршрут и
    # этот модуль не вызывает.
    if "мастер боевых искусств" in message_text:
        for button_text, row, column in buttons:
            if "усилить силу" in button_text:
                return (
                    button_text,
                    row,
                    column,
                    "Мастер боевых искусств: усилить силу",
                    None,
                ), "martial_arts_master"
        return None, "martial_arts_master_wait"

    if "встреча с соклановцем" in message_text:
        for button_text, row, column in buttons:
            if "пройти мимо" in button_text:
                return (
                    button_text,
                    row,
                    column,
                    "Пройти мимо соклановца",
                    None,
                ), "clanmate_encounter"

    if "защита границ" in message_text:
        for button_text, row, column in buttons:
            if "принять бой" in button_text:
                return (
                    button_text,
                    row,
                    column,
                    "Принять бой на защите границ",
                    None,
                ), "border_defense"

    if not is_event_message(message_text, buttons):
        return None, None

    for button_text, row, column in buttons:
        if "отказаться от события" in button_text or "отказаться" in button_text:
            return (
                button_text,
                row,
                column,
                "Закрыть событие",
                None,
            ), "event"

    event_buttons = [
        item
        for item in buttons
        if "главное меню" not in item[0]
        and "локации" not in item[0]
        and "профил" not in item[0]
    ]
    if event_buttons:
        button_text, row, column = event_buttons[-1]
        return (
            button_text,
            row,
            column,
            "Действие события",
            None,
        ), "event"

    return None, None
