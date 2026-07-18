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
            buttons = self._buttons(message)
            if not buttons:
                logger.debug("Message %s has no buttons", message.id)
                return False

            signature = self._signature(message, buttons)
            if not force and signature == self.state.last_signature:
                return False

            message_text = normalize(message.raw_text)
            selected: tuple[str, object, str, str | None] | None = None
            selected_kind: str | None = None

            if contains_any(message_text, WORN_EQUIPMENT_MARKERS):
                if not self.state.repair_mode:
                    logger.info("Worn equipment detected; starting repair flow")
                self.state.repair_mode = True
                self.state.repair_step = 0
                self.state.return_to_floor_mode = False
                self.state.return_to_floor_step = 0

            # Стамина имеет самый высокий приоритет и используется только при предупреждении.
            if contains_any(message_text, LOW_RESOURCE_MARKERS):
                for button_text, button in buttons:
                    if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                        selected = (button_text, button, "Выпить зелье стамины", "stamina_potions")
                        selected_kind = "stamina"
                        break

            # Строгий маршрут починки.
            if selected is None and self.state.repair_mode:
                if self.state.repair_step < len(REPAIR_FLOW):
                    markers, action_name = REPAIR_FLOW[self.state.repair_step]
                    for button_text, button in buttons:
                        if contains_any(button_text, markers):
                            selected = (button_text, button, action_name, None)
                            selected_kind = "repair_step"
                            break

            # Если пользователь сам открыл главное меню, запускаем возврат на сохранённый этаж.
            if (
                selected is None
                and not self.state.repair_mode
                and self.state.target_floor is not None
                and any("исследовать" in text or "исследование" in text for text, _ in buttons)
            ):
                self.state.return_to_floor_mode = True
                self.state.last_signature = None

            # Самовосстанавливающаяся навигация. Мы определяем текущий экран по кнопкам,
            # поэтому маршрут не ломается, даже если пользователь вручную перешёл на другой экран.
            if (
                selected is None
                and not self.state.repair_mode
                and self.state.return_to_floor_mode
                and self.state.target_floor is not None
            ):
                # После выбора локации игра может показать как «Начать», так и
                # «Продолжить исследование». Оба варианта завершают навигацию.
                for button_text, button in buttons:
                    if "начать исследование" in button_text or "продолжить исследование" in button_text:
                        action = "Продолжить исследование" if "продолжить" in button_text else "Начать исследование"
                        selected = (button_text, button, action, None)
                        selected_kind = "return_finish"
                        break

                # Экран выбора локации: выбираем последнюю кнопку с «локац», игнорируя «Назад».
                if selected is None:
                    location_buttons = [
                        (button_text, button)
                        for button_text, button in buttons
                        if "локац" in button_text and "назад" not in button_text
                    ]
                    if location_buttons:
                        button_text, button = location_buttons[-1]
                        selected = (button_text, button, "Последняя локация", None)
                        selected_kind = "return_step"

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
                            selected_kind = "return_step"
                            break

                # Главное меню: нажимаем «Исследовать».
                if selected is None:
                    for button_text, button in buttons:
                        if "исследовать" in button_text or "исследование" in button_text:
                            selected = (button_text, button, "Исследовать", None)
                            selected_kind = "return_step"
                            break

                # Если мы на другом экране, сначала возвращаемся в главное меню.
                if selected is None:
                    for button_text, button in buttons:
                        if "главное меню" in button_text:
                            selected = (button_text, button, "Главное меню", None)
                            selected_kind = "return_step"
                            break

            # Обычный фарм.
            if (
                selected is None
                and not self.state.repair_mode
                and not self.state.return_to_floor_mode
            ):
                for rule in STANDARD_RULES:
                    for button_text, button in buttons:
                        if contains_any(button_text, NEVER_CLICK):
                            continue
                        if contains_any(button_text, rule.markers):
                            selected = (button_text, button, rule.action_name, rule.counter)
                            selected_kind = "standard"
                            break
                    if selected is not None:
                        break

            if selected is None:
                logger.info(
                    "No matching action. repair_mode=%s, repair_step=%s, return_mode=%s, floor=%s, buttons=%s",
                    self.state.repair_mode,
                    self.state.repair_step,
                    self.state.return_to_floor_mode,
                    self.state.target_floor,
                    [text for text, _ in buttons],
                )
                self.state.last_signature = signature
                return False

            button_text, button, action_name, counter = selected
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
                    self.state.return_to_floor_step = 0
                    logger.info(
                        "Equipment repair completed; returning to floor %s",
                        self.state.target_floor,
                    )

            elif selected_kind == "return_finish":
                self.state.return_to_floor_mode = False
                self.state.return_to_floor_step = 0
                logger.info("Exploration started or continued on floor %s", self.state.target_floor)

            logger.info("Clicked: %s (message=%s)", action_name, message.id)
            return True
