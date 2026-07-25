from __future__ import annotations

from collections.abc import Iterable

from app.rules import WORN_EQUIPMENT_MARKERS
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

# Строгий маршрут починки:
# Главное меню -> Локации -> Кузница -> Починка
# -> Починить всё (один раз) -> Главное меню.
REPAIR_FLOW: tuple[tuple[tuple[str, ...], str], ...] = (
    (("главное меню",), "Главное меню"),
    (("локации",), "Локации"),
    (("кузница",), "Кузница"),
    (("починка",), "Починка"),
    (("починить все", "починить всё"), "Починить всё"),
    (("главное меню",), "Главное меню после починки"),
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def start_repair_if_needed(message_text: str, state: RuntimeState) -> None:
    if not contains_any(message_text, WORN_EQUIPMENT_MARKERS):
        return

    state.repair_mode = True
    state.repair_step = 0
    state.return_to_floor_mode = False


def select_repair_action(
    buttons: list[ButtonInfo],
    state: RuntimeState,
) -> tuple[SelectedAction | None, str | None]:
    if not state.repair_mode:
        return None, None

    if state.repair_step >= len(REPAIR_FLOW):
        return None, None

    markers, action_name = REPAIR_FLOW[state.repair_step]
    for button_text, row, column in buttons:
        if contains_any(button_text, markers):
            return (
                button_text,
                row,
                column,
                action_name,
                None,
            ), "repair_step"

    return None, "repair_wait"


def complete_repair_step(state: RuntimeState) -> bool:
    state.repair_step += 1
    if state.repair_step < len(REPAIR_FLOW):
        return False

    state.repairs += 1
    state.repair_mode = False
    state.repair_step = 0
    state.return_to_floor_mode = state.target_floor is not None
    return True
