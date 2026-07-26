from __future__ import annotations

from collections.abc import Iterable

from app.routes.combat import select_combat_action
from app.routes.farm import select_farm_action
from app.routes.repair import select_repair_action, start_repair_if_needed
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

PLAYER_ENCOUNTER_MARKERS = (
    "встреча с игроком",
    "вы столкнулись с",
)
ROB_MARKERS = ("ограбить",)

MANUAL_MESSAGE_MARKERS = (
    "встреча с соклановцем",
    "защита границ",
    "активное событие",
    "событие:",
    "выберите действие",
    "недостаточно стамины",
    "не хватает стамины",
    "стамина закончилась",
    "восстановите стамину",
    "сокровище",
    "сундук",
    "гильдейский зачёт",
    "гильдейский зачет",
    "арена",
)

MANUAL_BUTTON_MARKERS = (
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
    if contains_any(message_text, MANUAL_MESSAGE_MARKERS):
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


def select_semi_auto_action(
    message_text: str,
    buttons: list[ButtonInfo],
    state: RuntimeState,
) -> tuple[SelectedAction | None, str | None]:
    """Choose only actions allowed in the semi-automatic mode."""
    start_repair_if_needed(message_text, state)
    repair_action, repair_kind = select_repair_action(buttons, state)
    if repair_action is not None or repair_kind == "repair_wait":
        return repair_action, repair_kind

    player_action, player_kind = select_player_rob_action(message_text, buttons)
    if player_action is not None or player_kind == "semi_auto_wait":
        return player_action, player_kind

    combat_action, combat_kind = select_combat_action(buttons)
    if combat_action is not None:
        return combat_action, combat_kind

    if state.target_floor is not None:
        farm_action, farm_kind = select_farm_action(
            buttons,
            state.target_floor,
            state.target_location,
        )
        if farm_action is not None:
            return farm_action, farm_kind

    if is_manual_screen(message_text, buttons):
        return None, "semi_auto_manual"

    return None, "semi_auto_wait"
