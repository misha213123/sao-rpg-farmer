from __future__ import annotations

from app.routes.base import find_button


FARM_CONTINUE_MARKERS = ("продолжить исследование",)
FARM_START_MARKERS = ("исследовать",)


def find_continue_button(message):
    return find_button(message, FARM_CONTINUE_MARKERS)


def find_start_button(message):
    return find_button(message, FARM_START_MARKERS)
