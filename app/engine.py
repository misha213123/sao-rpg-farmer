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


class FarmerEngine:
    def __init__(self, settings: Settings, state: RuntimeState) -> None:
        self.settings = settings
        self.state = state
        self.last_message: Message | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _buttons(message: Message) -> list[tuple[str, object]]:
        result: list[tuple[str, object]] = []
        if not message.buttons:
            return result
        for row in message.buttons:
            for button in row:
                result.append((normalize(getattr(button, "text", "")), button))
        return result

    @staticmethod
    def _signature(message: Message, buttons: list[tuple[str, object]]) -> str:
        raw = f"{message.id}|{normalize(message.raw_text)}|" + "|".join(text for text, _ in buttons)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def process(self, message: Message, force: bool = False) -> bool:
        self.last_message = message
        self.state.last_message_id = message.id

        if not self.state.enabled and not force:
            return False

        async with self._lock:
            all_buttons = self._buttons(message)
            if not all_buttons:
                logger.debug("Message %s has no buttons", message.id)
                return False

            signature = self._signature(message, all_buttons)
            if not force and signature == self.state.last_signature:
                return False

            # Запрещённые кнопки полностью исключаются ещё до выбора действия.
            # Поэтому «Профиль» физически не может быть нажат движком.
            buttons = [
                (text, button)
                for text, button in all_buttons
                if not contains_any(text, NEVER_CLICK)
            ]

            message_text = normalize(message.raw_text)
            selected: tuple[str, object, str, str | None] | None = None
            selected_kind: str | None = None

            if contains_any(message_text, WORN_EQUIPMENT_MARKERS):
                if not self.state.repair_mode:
                    logger.info("Worn equipment detected; starting repair flow")
                self.state.repair_mode = True
                self.state.repair_step = 0
                self.state.return_to_floor_mode = False

            # 1. Стамина — только при сообщении о нехватке ресурсов.
            if contains_any(message_text, LOW_RESOURCE_MARKERS):
                for button_text, button in buttons:
                    if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                        selected = (button_text, button, "Выпить зелье стамины", "stamina_potions")
                        selected_kind = "stamina"
                        break

            # 2. Строгий маршрут починки.
            if selected is None and self.state.repair_mode:
                if self.state.repair_step < len(REPAIR_FLOW):
                    markers, action_name = REPAIR_FLOW[self.state.repair_step]
                    for button_text, button in buttons:
                        if contains_any(button_text, markers):
                            selected = (button_text, button, action_name, None)
                            selected_kind = "repair_step"
                            break

            # 3. Навигация к сохранённому этажу всегда имеет приоритет над обычными правилами.
            # Логика строго такая:
            # Исследовать -> выбранный этаж -> последняя Локация -> Продолжить/Начать исследование.
            if selected is None and not self.state.repair_mode and self.state.target_floor is not None:
                # Уже на экране запуска исследования.
                for button_text, button in buttons:
                    if "продолжить исследование" in button_text:
                        selected = (button_text, button, "Продолжить исследование", None)
                        selected_kind = "navigation_finish"
                        break

                if selected is None:
                    for button_text, button in buttons:
                        if "начать исследование" in button_text:
                            selected = (button_text, button, "Начать исследование", None)
                            selected_kind = "navigation_finish"
                            break

                # Экран выбора локации — выбираем последнюю подходящую кнопку.
                if selected is None:
                    location_buttons = [
                        (button_text, button)
                        for button_text, button in buttons
                        if "локац" in button_text
                    ]
                    if location_buttons:
                        button_text, button = location_buttons[-1]
                        selected = (button_text, button, "Последняя локация", None)
                        selected_kind = "navigation"

                # Экран выбора этажа.
                if selected is None:
                    for button_text, button in buttons:
                        if floor_button_matches(button_text, self.state.target_floor):
                            selected = (
                                button_text,
                                button,
                                f"Этаж {self.state.target_floor}",
                                None,
                            )
                            selected_kind = "navigation"
                            break

                # Главное меню — только «Исследовать». «Профиль» уже удалён из buttons.
                if selected is None:
                    for button_text, button in buttons:
                        if "исследовать" in button_text or "исследование" in button_text:
                            selected = (button_text, button, "Исследовать", None)
                            selected_kind = "navigation"
                            break

                # Если находимся вне главного меню, сначала нажимаем «Главное меню».
                if selected is None:
                    for button_text, button in buttons:
                        if "главное меню" in button_text:
                            selected = (button_text, button, "Главное меню", None)
                            selected_kind = "navigation"
                            break

            # 4. Обычный фарм, когда навигационная кнопка на текущем экране не найдена.
            if selected is None and not self.state.repair_mode:
                for rule in STANDARD_RULES:
                    for button_text, button in buttons:
                        if contains_any(button_text, rule.markers):
                            selected = (button_text, button, rule.action_name, rule.counter)
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
                    [text for text, _ in all_buttons],
                )
                self.state.last_signature = signature
                return False

            button_text, button, action_name, counter = selected

            # Последняя страховка: запрещённую кнопку не нажимаем даже при ошибке логики.
            if contains_any(button_text, NEVER_CLICK):
                logger.error("Blocked forbidden button: %s", button_text)
                self.state.last_signature = signature
                return False

            delay = random.uniform(self.settings.click_delay_min, self.settings.click_delay_max)
            await asyncio.sleep(delay)

            try:
                await button.click()
            except Exception:
                logger.exception("Failed to click button: %s", button_text)
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
                logger.info("Exploration started or continued on floor %s", self.state.target_floor)

            logger.info("Clicked: %s (button=%s, message=%s)", action_name, button_text, message.id)
            return True
