from __future__ import annotations

from collections.abc import Iterable

ButtonInfo = tuple[str, int, int]

GUILD_ROUTE_STEPS: dict[int, tuple[str, ...]] = {
    1: ("кланы",),
    2: ("гильдейский зачёт",),
    3: ("боевая доблесть",),
    4: ("выбрать цель",),
    5: ("agrognomiki",),
}

GUILD_CONFIRM_MARKERS = ("подтвердить атаку",)
GUILD_REPEAT_VARIANTS = (
    ("ещё раз", "agrognomiki"),
    ("еще раз", "agrognomiki"),
)
GUILD_COMBAT_VARIANTS = (
    ("скрытая атака",),
    ("удар 2 рук",),
    ("удар двух рук",),
    ("обычная атака",),
    ("атаковать",),
)
GUILD_MAX_BATTLES = 10

GUILD_EXHAUSTED_TEXT_MARKERS = (
    "осталось атак в этом часе 0",
    "осталось в этом часе 0 атак",
    "осталось 0 атак",
    "нет доступных атак",
    "атаки исчерпаны",
    "лимит pvp боев исчерпан",
    "лимит pvp боёв исчерпан",
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def find_button(
    buttons: list[ButtonInfo],
    markers: tuple[str, ...],
) -> ButtonInfo | None:
    for button_text, row, column in buttons:
        if all(marker in button_text for marker in markers):
            return button_text, row, column
    return None


def select_route_button(buttons: list[ButtonInfo], step: int) -> ButtonInfo | None:
    markers = GUILD_ROUTE_STEPS.get(step)
    if markers is None:
        return None
    return find_button(buttons, markers)


def select_confirm_button(buttons: list[ButtonInfo]) -> ButtonInfo | None:
    return find_button(buttons, GUILD_CONFIRM_MARKERS)


def select_combat_button(buttons: list[ButtonInfo]) -> ButtonInfo | None:
    for markers in GUILD_COMBAT_VARIANTS:
        target = find_button(buttons, markers)
        if target is not None:
            return target
    return None


def select_repeat_button(buttons: list[ButtonInfo]) -> ButtonInfo | None:
    for markers in GUILD_REPEAT_VARIANTS:
        target = find_button(buttons, markers)
        if target is not None:
            return target
    return None


def is_exhausted_text(message_text: str) -> bool:
    return (
        contains_any(message_text, GUILD_EXHAUSTED_TEXT_MARKERS)
        or ("0 атак" in message_text and "остал" in message_text)
        or ("лимит" in message_text and "исчерпан" in message_text)
    )


def should_finish_guild(message_text: str, battle_clicks: int) -> bool:
    return is_exhausted_text(message_text) or battle_clicks >= GUILD_MAX_BATTLES
