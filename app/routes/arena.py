from __future__ import annotations

from collections.abc import Iterable

from app.routes.base import find_button, has_text


ButtonInfo = tuple[str, int, int]

ARENA_MENU_MARKERS = ("арена", "pvp")
ARENA_FIRST_BATTLE_MARKERS = ("рандомный бой",)
ARENA_REPEAT_MARKERS = ("ещё бой", "еще бой")
ARENA_MAX_BATTLES = 5

ARENA_EXHAUSTED_TEXT_MARKERS = (
    "использовано 5/5",
    "рандомных боев использовано 5/5",
    "рандомных боёв использовано 5/5",
    "достигли лимита рандомных боев",
    "достигли лимита рандомных боёв",
    "лимит 5 боев в час",
    "лимит 5 боёв в час",
    "лимит pvp боев исчерпан",
    "лимит pvp боёв исчерпан",
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def is_exhausted_text(message_text: str) -> bool:
    """Return True when the arena hourly limit is exhausted."""
    return (
        ("5/5" in message_text and "бо" in message_text)
        or contains_any(message_text, ARENA_EXHAUSTED_TEXT_MARKERS)
    )


def should_finish_arena(message_text: str, battle_clicks: int) -> bool:
    """Arena ends after the game reports 5/5 or five battle clicks."""
    return is_exhausted_text(message_text) or battle_clicks >= ARENA_MAX_BATTLES


def battle_button_markers(battle_clicks: int) -> tuple[str, ...]:
    """Use Random battle for the first fight and Another fight afterwards."""
    if battle_clicks == 0:
        return ARENA_FIRST_BATTLE_MARKERS
    return ARENA_REPEAT_MARKERS


def select_battle_button(
    buttons: list[ButtonInfo],
    battle_clicks: int,
) -> ButtonInfo | None:
    """Return the exact arena battle button for the current fight number."""
    markers = battle_button_markers(battle_clicks)
    for button_text, row, column in buttons:
        if contains_any(button_text, markers):
            return button_text, row, column
    return None


def find_arena_menu(message):
    return find_button(message, ARENA_MENU_MARKERS)


def find_battle_button(message):
    target = find_button(message, ARENA_FIRST_BATTLE_MARKERS)
    if target is not None:
        return target
    return find_button(message, ARENA_REPEAT_MARKERS)


def is_exhausted(message) -> bool:
    """Compatibility helper for code that still passes a Telegram message."""
    return (
        has_text(message, "5/5")
        or any(has_text(message, marker) for marker in ARENA_EXHAUSTED_TEXT_MARKERS)
    )
