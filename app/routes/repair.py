from __future__ import annotations

from app.routes.base import find_button


REPAIR_ALL_MARKERS = ("починить всё",)
MAIN_MENU_MARKERS = ("главное меню",)


def find_repair_all(message):
    return find_button(message, REPAIR_ALL_MARKERS)


def find_main_menu(message):
    return find_button(message, MAIN_MENU_MARKERS)
