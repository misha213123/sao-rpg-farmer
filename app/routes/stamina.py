from __future__ import annotations

from collections.abc import Iterable

from app.rules import (
    HP_POTION_BUTTON_MARKERS,
    LOW_RESOURCE_MARKERS,
    STAMINA_BUTTON_MARKERS,
)
from app.state import RuntimeState

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]

RECOVERY_MARKERS = (
    "использовать восстановление стамины",
    "восстановление стамины",
)

EXPLORATION_FLOW: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    (("баффы",), "Баффы для восстановления стамины", None),
    (("след",), "След", None),
    (
        RECOVERY_MARKERS,
        "Использовать восстановление стамины",
        None,
    ),
    (("назад в исследование", "назад"), "Назад в исследование", None),
)

# Маршрут восстановления стамины во время боя с боссом:
# Зелья -> проверить прямую кнопку восстановления.
# Если её нет: След -> Использовать Восстановление стамины.
# Затем Назад в исследование -> продолжить бой обычными боевыми правилами.
BATTLE_FLOW: tuple[tuple[tuple[str, ...], str, str | None], ...] = (
    (("зелья",), "Открыть зелья в бою", None),
    (("след",), "След в меню зелий", None),
    (
        RECOVERY_MARKERS,
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
    """Choose HP potion, stamina potion, exploration recovery, or boss recovery."""

    # Быстрые кнопки зелий имеют максимальный приоритет. Проверяем саму кнопку,
    # а не только текст сообщения: формулировка предупреждения в игре может меняться.
    for button_text, row, column in buttons:
        if contains_any(button_text, HP_POTION_BUTTON_MARKERS):
            return (
                button_text,
                row,
                column,
                "Выпить зелье HP",
                None,
            ), "hp_potion"

    for button_text, row, column in buttons:
        if contains_any(button_text, STAMINA_BUTTON_MARKERS):
            return (
                button_text,
                row,
                column,
                "Выпить зелье стамины",
                "stamina_potions",
            ), "stamina"

    low_resource = contains_any(message_text, LOW_RESOURCE_MARKERS)

    if low_resource and not state.stamina_mode:
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

    # После открытия «Баффы» или «Зелья» сначала проверяем, доступна ли
    # «Использовать Восстановление стамины» прямо на текущем экране.
    # Если доступна, пропускаем «След». Engine после клика увеличит шаг ещё на 1,
    # поэтому заранее ставим индекс действия восстановления (2), чтобы следующим
    # шагом стал возврат «Назад в исследование» (3).
    if state.stamina_step == 1:
        recovery_action_name = (
            "Использовать восстановление стамины в бою"
            if state.stamina_route == "battle"
            else "Использовать восстановление стамины"
        )
        for button_text, row, column in buttons:
            if contains_any(button_text, RECOVERY_MARKERS):
                state.stamina_step = 2
                return (
                    button_text,
                    row,
                    column,
                    recovery_action_name,
                    None,
                ), "stamina_step"

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
