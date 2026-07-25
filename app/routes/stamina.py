from __future__ import annotations

from collections.abc import Iterable

from app.rules import LOW_RESOURCE_MARKERS, STAMINA_BUTTON_MARKERS
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

EXPLORATION_FLOW: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    (("баффы",), "Баффы для восстановления стамины", None),
    (("след",), "След", None),
    (
        ("использовать восстановление стамины", "восстановление стамины"),
        "Использовать восстановление стамины",
        None,
    ),
    (("назад в исследование", "назад"), "Назад в исследование", None),
)

# Чёткий маршрут восстановления стамины во время боя с боссом:
# Зелья -> След -> Использовать Восстановление стамины
# -> Назад в исследование -> продолжить бой обычными боевыми правилами.
BATTLE_FLOW: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    (("зелья",), "Открыть зелья в бою", None),
    (("след",), "След в меню зелий", None),
    (
        ("использовать восстановление стамины", "восстановление стамины"),
        "Использовать восстановление стамины в бою",
        None,
    ),
    (("назад в исследование", "назад"), "Назад к бою с боссом", None),
)


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def stamina_flow_length(state: RuntimeState) -> int:
    if state.stamina_route == "battle":
        return len(BATTLE_FLOW)
    return len(EXPLORATION_FLOW)


def reset_stamina_route(state: RuntimeState) -> None:
    state.stamina_mode = False
    state.stamina_step = 0
    state.stamina_route = ""


def select_stamina_action(
    message_text: str,
    buttons: list[ButtonInfo],
    state: RuntimeState,
) -> tuple[SelectedAction | None, str | None]:
    """Choose quick potion, exploration recovery, or boss-battle recovery route."""
    low_resource = contains_any(message_text, LOW_RESOURCE_MARKERS)

    if low_resource and not state.stamina_mode:
        for button_text, row, column in buttons:
            if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                return (
                    button_text,
                    row,
                    column,
                    "Выпить зелье стамины",
                    "stamina_potions",
                ), "stamina"

        has_battle_potions = any(
            button_text == "зелья" or button_text.endswith(" зелья")
            for button_text, _, _ in buttons
        )
        state.stamina_mode = True
        state.stamina_step = 0
        state.stamina_route = "battle" if has_battle_potions else "exploration"

    if not state.stamina_mode:
        return None, None

    flow = BATTLE_FLOW if state.stamina_route == "battle" else EXPLORATION_FLOW
    if state.stamina_step >= len(flow):
        reset_stamina_route(state)
        return None, None

    markers, action_name, counter = flow[state.stamina_step]
    for button_text, row, column in buttons:
        if contains_any(button_text, markers):
            return (
                button_text,
                row,
                column,
                action_name,
                counter,
            ), "stamina_step"

    return None, "stamina_wait"
