from __future__ import annotations

from collections.abc import Iterable

from app.routes.combat import select_combat_action
from app.routes.repair import select_repair_action, start_repair_if_needed
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

# Полуавтоматический режим пока изолирован и не подключён к main.py/engine.py.
# Он предназначен для отдельного режима №4 после безопасного подключения.

CONTINUE_MARKERS = ("продолжить исследование",)
PLAYER_ENCOUNTER_MARKERS = (
    "встреча с игроком",
    "вы столкнулись с",
)
ROB_MARKERS = ("ограбить",)

# На этих экранах полуавтоматический режим ничего не нажимает.
MANUAL_MESSAGE_MARKERS = (
    "встреча с соклановцем",
    "защита границ",
    "активное событие",
    "событие:",
    "выберите действие",
    "стамина",
    "выносливость",
    "сокровище",
    "сундук",
    "гильдейский зачёт",
    "гильдейский зачет",
    "арена",
)

MANUAL_BUTTON_MARKERS = (
    "баффы",
    "зелья",
    "выпить зелье стамины",
    "использовать восстановление стамины",
    "пройти мимо",
    "принять бой",
    "отказаться от события",
    "отказаться",
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def is_manual_screen(message_text: str, buttons: list[ButtonInfo]) -> bool:
    """Return True when the player must handle the current screen manually."""
    if contains_any(message_text, MANUAL_MESSAGE_MARKERS):
        # Встреча с игроком является исключением: её обрабатываем автоматически.
        if contains_any(message_text, PLAYER_ENCOUNTER_MARKERS):
            return False
        return True

    return any(
        contains_any(button_text, MANUAL_BUTTON_MARKERS)
        for button_text, _, _ in buttons
    )


def select_player_rob_action(
    message_text: str,
    buttons: list[ButtonInfo],
) -> tuple[SelectedAction | None, str | None]:
    if not contains_any(message_text, PLAYER_ENCOUNTER_MARKERS):
        return None, None

    for button_text, row, column in buttons:
        if contains_any(button_text, ROB_MARKERS):
            return (
                button_text,
                row,
                column,
                "Ограбить игрока",
                None,
            ), "semi_auto_player_encounter"

    return None, "semi_auto_wait"


def select_continue_action(
    buttons: list[ButtonInfo],
) -> tuple[SelectedAction | None, str | None]:
    for button_text, row, column in buttons:
        if contains_any(button_text, CONTINUE_MARKERS):
            return (
                button_text,
                row,
                column,
                "Продолжить исследование",
                None,
            ), "semi_auto_continue"

    return None, None


def select_semi_auto_action(
    message_text: str,
    buttons: list[ButtonInfo],
    state: RuntimeState,
) -> tuple[SelectedAction | None, str | None]:
    """Choose only actions allowed in the semi-automatic mode.

    Automatic actions:
    1. Existing repair route, including one click on «Починить всё».
    2. Encounter with another player -> «Ограбить».
    3. Boss/combat actions using the existing strict combat priority.
    4. «Продолжить исследование».

    All stamina handling, random events, clanmate encounters, treasure screens,
    Arena, Guild ranking and unknown screens are left for the player.
    """
    # Починка должна работать так же, как в полном режиме.
    start_repair_if_needed(message_text, state)
    repair_action, repair_kind = select_repair_action(buttons, state)
    if repair_action is not None or repair_kind == "repair_wait":
        return repair_action, repair_kind

    player_action, player_kind = select_player_rob_action(message_text, buttons)
    if player_action is not None or player_kind == "semi_auto_wait":
        return player_action, player_kind

    # Любые остальные события и специальные экраны оставляем пользователю.
    if is_manual_screen(message_text, buttons):
        return None, "semi_auto_manual"

    combat_action, combat_kind = select_combat_action(buttons)
    if combat_action is not None:
        return combat_action, combat_kind

    continue_action, continue_kind = select_continue_action(buttons)
    if continue_action is not None:
        return continue_action, continue_kind

    return None, "semi_auto_wait"
