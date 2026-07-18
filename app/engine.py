from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from collections.abc import Iterable

from telethon.tl.custom.message import Message

from app.config import Settings
from app.rules import (
    LOW_RESOURCE_MARKERS,
    NEVER_CLICK,
    REPAIR_FLOW,
    STAMINA_BUTTON_MARKERS,
    STANDARD_RULES,
    WORN_EQUIPMENT_MARKERS,
)
from app.state import RuntimeState

logger = logging.getLogger(__name__)

ButtonInfo = tuple[str, int, int]
SelectedAction = tuple[str, int, int, str, str | None]


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def floor_button_matches(button_text: str, floor: int) -> bool:
    compact = button_text.replace("№", " ").replace("-", " ")
    tokens = compact.split()
    floor_text = str(floor)
    return (
        button_text == floor_text
        or f"этаж {floor_text}" in button_text
        or f"{floor_text} этаж" in button_text
        or floor_text in tokens
    )


def is_exploration_location(button_text: str) -> bool:
    """Локация внутри этажа, но не пункт главного меню «Локации»."""
    if "назад" in button_text:
        return False
    if "локация" not in button_text:
        return False
    # «Локации» — отдельный пункт главного меню, разрешён только при починке.
    if button_text.startswith("локации"):
        return False
    return True


class FarmerEngine:
    def __init__(self, settings: Settings, state: RuntimeState) -> None:
        self.settings = settings
        self.state = state
        self.last_message: Message | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _buttons(message: Message) -> list[ButtonInfo]:
        result: list[ButtonInfo] = []
        if not message.buttons:
            return result
        for row_index, row in enumerate(message.buttons):
            for column_index, button in enumerate(row):
                result.append(
                    (
                        normalize(getattr(button, "text", "")),
                        row_index,
                        column_index,
                    )
                )
        return result

    @staticmethod
    def _signature(message: Message, buttons: list[ButtonInfo]) -> str:
        raw = f"{message.id}|{normalize(message.raw_text)}|" + "|".join(
            text for text, _, _ in buttons
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def process(self, message: Message, force: bool = False) -> bool:
        self.last_message = message
        self.state.last_message_id = message.id

        if not self.state.enabled and not force:
            return False

        async with self._lock:
            all_buttons = self._buttons(message)
            if not all_buttons:
                return False

            signature = self._signature(message, all_buttons)
            if not force and signature == self.state.last_signature:
                return False

            # Профиль, Назад, HP и Сбежать полностью исключены.
            buttons = [
                item
                for item in all_buttons
                if not contains_any(item[0], NEVER_CLICK)
                and "профил" not in item[0]
            ]

            message_text = normalize(message.raw_text)
            selected: SelectedAction | None = None
            selected_kind: str | None = None

            # Запускаем починку только по сообщению об износе.
            if contains_any(message_text, WORN_EQUIPMENT_MARKERS):
                if not self.state.repair_mode:
                    logger.info("Worn equipment detected; starting repair flow")
                self.state.repair_mode = True
                self.state.repair_step = 0
                self.state.return_to_floor_mode = False

            # Стамина — только при явном сообщении о нехватке ресурсов.
            if contains_any(message_text, LOW_RESOURCE_MARKERS):
                for button_text, row, column in buttons:
                    if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                        selected = (
                            button_text,
                            row,
                            column,
                            "Выпить зелье стамины",
                            "stamina_potions",
                        )
                        selected_kind = "stamina"
                        break

            # Маршрут починки:
            # Главное меню -> Локации -> Кузница -> Починка -> Починить всё -> Починить всё.
            if selected is None and self.state.repair_mode:
                if self.state.repair_step < len(REPAIR_FLOW):
                    markers, action_name = REPAIR_FLOW[self.state.repair_step]
                    for button_text, row, column in buttons:
                        if contains_any(button_text, markers):
                            selected = (
                                button_text,
                                row,
                                column,
                                action_name,
                                None,
                            )
                            selected_kind = "repair_step"
                            break

            # Основной маршрут фарма:
            # Исследовать -> выбранный этаж -> последняя Локация -> Продолжить/Начать.
            if selected is None and not self.state.repair_mode and self.state.target_floor is not None:
                # Финальная кнопка исследования.
                for button_text, row, column in buttons:
                    if button_text.startswith("продолжить исследование"):
                        selected = (
                            button_text,
                            row,
                            column,
                            "Продолжить исследование",
                            None,
                        )
                        selected_kind = "navigation_finish"
                        break

                if selected is None:
                    for button_text, row, column in buttons:
                        if button_text.startswith("начать исследование"):
                            selected = (
                                button_text,
                                row,
                                column,
                                "Начать исследование",
                                None,
                            )
                            selected_kind = "navigation_finish"
                            break

                # Главное меню: сначала и только «Исследовать».
                if selected is None:
                    for button_text, row, column in buttons:
                        if button_text == "исследовать" or button_text.startswith("исследовать "):
                            selected = (
                                button_text,
                                row,
                                column,
                                "Исследовать",
                                None,
                            )
                            selected_kind = "navigation"
                            break

                # Экран выбора этажа.
                if selected is None:
                    for button_text, row, column in buttons:
                        if floor_button_matches(button_text, self.state.target_floor):
                            selected = (
                                button_text,
                                row,
                                column,
                                f"Этаж {self.state.target_floor}",
                                None,
                            )
                            selected_kind = "navigation"
                            break

                # Экран выбора локации внутри этажа.
                # Пункт главного меню «Локации» сюда никогда не попадает.
                if selected is None:
                    location_buttons = [
                        item for item in buttons if is_exploration_location(item[0])
                    ]
                    if location_buttons:
                        button_text, row, column = location_buttons[-1]
                        selected = (
                            button_text,
                            row,
                            column,
                            "Последняя локация",
                            None,
                        )
                        selected_kind = "navigation"

                # Если сейчас другой экран, возвращаемся в главное меню.
                if selected is None:
                    for button_text, row, column in buttons:
                        if button_text == "главное меню" or button_text.startswith("главное меню"):
                            selected = (
                                button_text,
                                row,
                                column,
                                "Главное меню",
                                None,
                            )
                            selected_kind = "navigation"
                            break

            # Обычные боевые действия. «Локации» здесь отсутствует в правилах.
            if selected is None and not self.state.repair_mode:
                for rule in STANDARD_RULES:
                    for button_text, row, column in buttons:
                        if contains_any(button_text, rule.markers):
                            selected = (
                                button_text,
                                row,
                                column,
                                rule.action_name,
                                rule.counter,
                            )
                            selected_kind = "standard"
                            break
                    if selected is not None:
                        break

            if selected is None:
                logger.info(
                    "No matching action. repair_mode=%s, repair_step=%s, floor=%s, buttons=%s",
                    self.state.repair_mode,
                    self.state.repair_step,
                    self.state.target_floor,
                    [text for text, _, _ in all_buttons],
                )
                self.state.last_signature = signature
                return False

            button_text, row, column, action_name, counter = selected

            # Последняя страховка от запрещённых кнопок.
            if "профил" in button_text or contains_any(button_text, NEVER_CLICK):
                logger.error("Blocked forbidden button: %s", button_text)
                self.state.last_signature = signature
                return False

            # «Локации» разрешена исключительно во время маршрута починки.
            if button_text.startswith("локации") and selected_kind != "repair_step":
                logger.error("Blocked main-menu Locations outside repair: %s", button_text)
                self.state.last_signature = signature
                return False

            delay = random.uniform(
                self.settings.click_delay_min,
                self.settings.click_delay_max,
            )
            await asyncio.sleep(delay)

            try:
                await message.click(i=row, j=column)
            except Exception:
                logger.exception(
                    "Failed to click button: %s at row=%s column=%s",
                    button_text,
                    row,
                    column,
                )
                return False

            self.state.last_signature = signature
            self.state.clicks += 1
            self.state.last_action = action_name
            if counter:
                setattr(self.state, counter, getattr(self.state, counter) + 1)

            if selected_kind == "repair_step":
                self.state.repair_step += 1
                if self.state.repair_step >= len(REPAIR_FLOW):
                    self.state.repairs += 1
                    self.state.repair_mode = False
                    self.state.repair_step = 0
                    self.state.return_to_floor_mode = self.state.target_floor is not None
                    logger.info(
                        "Equipment repair completed; returning to floor %s",
                        self.state.target_floor,
                    )

            elif selected_kind == "navigation_finish":
                self.state.return_to_floor_mode = False
                self.state.return_to_floor_step = 0
                logger.info(
                    "Exploration started or continued on floor %s",
                    self.state.target_floor,
                )

            logger.info(
                "Clicked: %s (button=%s, row=%s, column=%s, message=%s)",
                action_name,
                button_text,
                row,
                column,
                message.id,
            )
            return True
