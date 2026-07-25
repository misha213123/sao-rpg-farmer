from __future__ import annotations

from app.routes.base import find_button, has_text


QUICK_POTION_MARKERS = ("выпить зелье стамины",)
BUFFS_MARKERS = ("баффы",)
TRACE_MARKERS = ("след",)
RESTORE_MARKERS = ("использовать восстановление стамины",)
BACK_TO_RESEARCH_MARKERS = ("назад в исследование",)


def low_stamina(message) -> bool:
    """Detect the game's low-stamina screen without relying on emoji."""
    return has_text(message, "стамина") and (
        has_text(message, "10%")
        or has_text(message, "недостаточно стамины")
        or has_text(message, "стамина закончилась")
    )


def find_quick_potion(message):
    return find_button(message, QUICK_POTION_MARKERS)


def find_fallback_step(message, step: str):
    markers_by_step = {
        "buffs": BUFFS_MARKERS,
        "trace": TRACE_MARKERS,
        "restore": RESTORE_MARKERS,
        "back": BACK_TO_RESEARCH_MARKERS,
    }
    markers = markers_by_step.get(step)
    return find_button(message, markers) if markers else None
