from __future__ import annotations

from app.routes.base import find_button, has_text


GUILD_STEPS = (
    ("кланы",),
    ("гильдейский зачёт",),
    ("боевая доблесть",),
    ("выбрать цель",),
    ("agrognomiki",),
)
GUILD_CONFIRM_MARKERS = ("подтвердить атаку",)
GUILD_REPEAT_VARIANTS = (("ещё раз", "agrognomiki"), ("еще раз", "agrognomiki"))


def is_exhausted(message) -> bool:
    return (
        has_text(message, "осталось атак в этом часе 0")
        or has_text(message, "осталось в этом часе 0 атак")
        or has_text(message, "нет доступных атак")
        or has_text(message, "атаки исчерпаны")
    )


def find_step_button(message, step_index: int):
    if step_index < 0 or step_index >= len(GUILD_STEPS):
        return None
    return find_button(message, GUILD_STEPS[step_index])


def find_confirm_button(message):
    return find_button(message, GUILD_CONFIRM_MARKERS)


def find_repeat_button(message):
    for markers in GUILD_REPEAT_VARIANTS:
        target = find_button(message, markers)
        if target is not None:
            return target
    return None
