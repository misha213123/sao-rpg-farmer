from __future__ import annotations

from app.routes.base import find_button, has_text


ARENA_MENU_MARKERS = ("арена", "pvp")
ARENA_BATTLE_MARKERS = ("рандомный бой",)
ARENA_REPEAT_VARIANTS = (("ещё бой",), ("еще бой",))


def is_exhausted(message) -> bool:
    return (
        has_text(message, "использовано 5/5")
        or has_text(message, "рандомных боев использовано 5/5")
        or has_text(message, "рандомных боёв использовано 5/5")
    )


def find_arena_menu(message):
    return find_button(message, ARENA_MENU_MARKERS)


def find_battle_button(message):
    target = find_button(message, ARENA_BATTLE_MARKERS)
    if target is not None:
        return target
    for markers in ARENA_REPEAT_VARIANTS:
        target = find_button(message, markers)
        if target is not None:
            return target
    return None
