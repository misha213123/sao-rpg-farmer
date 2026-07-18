from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from collections.abc import Iterable

from telethon.tl.custom.message import Message

from app.config import Settings
from app.rules import LOW_RESOURCE_MARKERS, NEVER_CLICK, STAMINA_BUTTON_MARKERS, STANDARD_RULES
from app.state import RuntimeState

logger = logging.getLogger(__name__)


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


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

            # Зелье стамины нажимается только при явном предупреждении о ресурсах.
            if contains_any(message_text, LOW_RESOURCE_MARKERS):
                for button_text, button in buttons:
                    if contains_any(button_text, STAMINA_BUTTON_MARKERS):
                        selected = (button_text, button, "Выпить зелье стамины", "stamina_potions")
                        break

            if selected is None:
                for rule in STANDARD_RULES:
                    for button_text, button in buttons:
                        if contains_any(button_text, NEVER_CLICK):
                            continue
                        if contains_any(button_text, rule.markers):
                            selected = (button_text, button, rule.action_name, rule.counter)
                            break
                    if selected is not None:
                        break

            if selected is None:
                logger.info("No matching action. Buttons: %s", [text for text, _ in buttons])
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

            logger.info("Clicked: %s (message=%s)", action_name, message.id)
            return True
