from __future__ import annotations

from collections.abc import Iterable

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

# После обычного заброса кнопка «Проверить удочку» уже видна, но нажимать её
# нельзя, пока игра прямо говорит ждать клёва.
WAITING_AFTER_CAST_MARKERS = (
    "удочка заброшена",
    "жди клёва",
    "жди клева",
)

CHECK_ROD_MARKERS = ("проверить удочку",)
PULL_ROD_MARKERS = ("вытащить удочку",)
CAST_ROD_MARKERS = ("забросить удочку",)
FISHING_MARKERS = ("рыбалка",)
LOCATIONS_MARKERS = ("локации",)


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


def select_fishing_action(
    message_text: str,
    buttons: list[ButtonInfo],
) -> tuple[SelectedAction | None, str | None]:
    """Выбирает только действия отдельного режима рыбалки.

    Маршрут запуска:
    /start -> Локации -> Рыбалка -> Забросить удочку.

    Цикл:
    - известная или неизвестная поклёвка -> Проверить удочку -> Забросить удочку;
    - мусор -> Вытащить удочку -> Забросить удочку;
    - просьба Ниджи -> Дать наживку и продолжить ожидание;
    - сразу после заброса ничего не нажимать до появления нового события.
    """
    # Событие Ниджи имеет самый высокий приоритет.
    if contains_any(message_text, NIJI_MESSAGE_MARKERS):
        give_bait = find_button(buttons, GIVE_BAIT_MARKERS)
        if give_bait is not None:
            return make_action(give_bait, "Дать наживку Ниджи", "fishing_give_bait")
        return None, "fishing_wait_niji"

    # Мусор нельзя проверять: удочку нужно вытащить.
    if "глубинное зрение" in message_text and contains_any(message_text, TRASH_MARKERS):
        pull_rod = find_button(buttons, PULL_ROD_MARKERS)
        if pull_rod is not None:
            return make_action(pull_rod, "Вытащить удочку: мусор", "fishing_pull_trash")
        return None, "fishing_wait_trash"

    # Известную рыбу, сундук и предмет забираем через проверку удочки.
    if "глубинное зрение" in message_text and contains_any(message_text, CATCH_MARKERS):
        check_rod = find_button(buttons, CHECK_ROD_MARKERS)
        if check_rod is not None:
            return make_action(check_rod, "Проверить удочку", "fishing_check")
        return None, "fishing_wait_catch"

    # Сразу после заброса кнопка проверки уже присутствует, но здесь ждём клёва.
    if contains_any(message_text, WAITING_AFTER_CAST_MARKERS):
        return None, "fishing_wait_bite"

    # Запасное правило для любых новых и неизвестных событий рыбалки:
    # если игра предлагает «Проверить удочку», нажимаем её.
    check_rod = find_button(buttons, CHECK_ROD_MARKERS)
    if check_rod is not None:
        return make_action(
            check_rod,
            "Проверить удочку: неизвестное событие",
            "fishing_check_fallback",
        )

    # После улова или вытаскивания мусора снова забрасываем удочку.
    cast_rod = find_button(buttons, CAST_ROD_MARKERS)
    if cast_rod is not None:
        return make_action(cast_rod, "Забросить удочку", "fishing_cast")

    # Навигация из /start в рыбалку.
    fishing = find_button(buttons, FISHING_MARKERS)
    if fishing is not None:
        return make_action(fishing, "Рыбалка", "fishing_navigation")

    locations = find_button(buttons, LOCATIONS_MARKERS)
    if locations is not None:
        return make_action(locations, "Локации", "fishing_navigation")

    return None, "fishing_wait"
