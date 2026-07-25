from __future__ import annotations

import re
from collections.abc import Iterable

from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

NIJI_MESSAGE_MARKERS = (
    "ты не одолжишь наживку",
    "одолжишь наживку",
)
GIVE_BAIT_MARKERS = ("дать наживку",)

TRASH_MARKERS = ("мусор",)
CATCH_MARKERS = (
    "обычная",
    "необычная",
    "редкая",
    "эпическая",
    "легендарная",
    "сундук",
    "предмет",
)

CHECK_ROD_MARKERS = ("проверить удочку",)
PULL_ROD_MARKERS = ("вытащить удочку",)
CAST_ROD_MARKERS = ("забросить удочку",)
FISHING_MARKERS = ("рыбалка",)
LOCATIONS_MARKERS = ("локации",)

RARITY_COUNTERS = (
    ("легендар", "fishing_legendary"),
    ("эпическ", "fishing_epic"),
    ("необычн", "fishing_uncommon"),
    ("редк", "fishing_rare"),
    ("обычн", "fishing_common"),
)

CHEST_MONEY_MARKERS = (
    "золот",
    "монет",
    "серебр",
    "кредит",
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def find_button(
    buttons: list[ButtonInfo],
    markers: Iterable[str],
) -> ButtonInfo | None:
    for button_text, row, column in buttons:
        if contains_any(button_text, markers):
            return button_text, row, column
    return None


def make_action(
    button: ButtonInfo,
    action_name: str,
    kind: str,
) -> tuple[SelectedAction, str]:
    button_text, row, column = button
    return (
        button_text,
        row,
        column,
        action_name,
        None,
    ), kind


def _extract_chest_earnings(message_text: str) -> int:
    if "сундук" not in message_text or not contains_any(message_text, CHEST_MONEY_MARKERS):
        return 0

    amounts: list[int] = []
    for match in re.finditer(r"(?:\+\s*)?(\d[\d\s.,]*)", message_text):
        raw = re.sub(r"[^0-9]", "", match.group(1))
        if raw:
            amounts.append(int(raw))
    return max(amounts, default=0)


def record_fishing_result(message_text: str, state: RuntimeState) -> None:
    """Обновляет только дневную статистику рыбалки из сообщений с результатом."""
    state.reset_fishing_stats_if_needed()

    # Считаем рыбу только после фактического улова, а не на экране глубинного зрения.
    caught = "поймана" in message_text or "рыба добавлена в улов" in message_text
    if caught:
        for marker, counter_name in RARITY_COUNTERS:
            if marker in message_text:
                setattr(state, counter_name, getattr(state, counter_name) + 1)
                break

    chest_earnings = _extract_chest_earnings(message_text)
    if chest_earnings > 0:
        state.fishing_chest_earnings += chest_earnings


def select_fishing_action(
    message_text: str,
    buttons: list[ButtonInfo],
) -> tuple[SelectedAction | None, str | None]:
    """Выбирает только действия отдельного режима рыбалки.

    Маршрут запуска:
    /start -> Локации -> Рыбалка -> Забросить удочку.

    Цикл:
    - рыба, сундук, предмет или неизвестное событие -> Проверить удочку;
    - мусор -> Вытащить удочку;
    - после результата -> Забросить удочку;
    - просьба Ниджи -> Дать наживку и продолжить ожидание.
    """
    if contains_any(message_text, NIJI_MESSAGE_MARKERS):
        give_bait = find_button(buttons, GIVE_BAIT_MARKERS)
        if give_bait is not None:
            return make_action(give_bait, "Дать наживку Ниджи", "fishing_give_bait")
        return None, "fishing_wait_niji"

    if "глубинное зрение" in message_text and contains_any(message_text, TRASH_MARKERS):
        pull_rod = find_button(buttons, PULL_ROD_MARKERS)
        if pull_rod is not None:
            return make_action(pull_rod, "Вытащить удочку: мусор", "fishing_pull_trash")
        return None, "fishing_wait_trash"

    if "глубинное зрение" in message_text and contains_any(message_text, CATCH_MARKERS):
        check_rod = find_button(buttons, CHECK_ROD_MARKERS)
        if check_rod is not None:
            return make_action(check_rod, "Проверить удочку", "fishing_check")
        return None, "fishing_wait_catch"

    cast_rod = find_button(buttons, CAST_ROD_MARKERS)
    if cast_rod is not None:
        return make_action(cast_rod, "Забросить удочку", "fishing_cast")

    fishing = find_button(buttons, FISHING_MARKERS)
    if fishing is not None:
        return make_action(fishing, "Рыбалка", "fishing_navigation")

    locations = find_button(buttons, LOCATIONS_MARKERS)
    if locations is not None:
        return make_action(locations, "Локации", "fishing_navigation")

    # Для неизвестного события рыбалки используем безопасный общий вариант.
    if "удочка заброшена" not in message_text:
        check_rod = find_button(buttons, CHECK_ROD_MARKERS)
        if check_rod is not None:
            return make_action(check_rod, "Проверить удочку: неизвестное событие", "fishing_check")

    return None, "fishing_wait"
