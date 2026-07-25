from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from collections.abc import Iterable

from telethon.tl.custom.message import Message

from app.config import Settings
from app.routes.combat import select_combat_action
from app.routes.events import (
    select_player_encounter_action,
    select_random_event_action,
)
from app.routes.farm import select_farm_action
from app.routes.semi_auto import select_semi_auto_action
from app.routes.stamina import (
    reset_stamina_route,
    select_stamina_action,
    stamina_flow_length,
)
from app.rules import (
    NEVER_CLICK,
    REPAIR_FLOW,
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

            buttons = [
                item
                for item in all_buttons
                if not contains_any(item[0], NEVER_CLICK)
                and "профил" not in item[0]
            ]

            message_text = normalize(message.raw_text)
            selected: SelectedAction | None = None
            selected_kind: str | None = None

            # Полуавтоматический режим полностью изолирован от обычных правил.
            # Он использует только бой, «Продолжить исследование», ограбление игрока
            # и существующий маршрут починки. Стамина и события остаются ручными.
            if getattr(self.state, "automation_mode", "") == "semi_auto":
                selected, selected_kind = select_semi_auto_action(
                    message_text,
                    all_buttons,
                    self.state,
                )
                if selected is None:
                    logger.info(
                        "Semi-auto waiting for manual action. kind=%s buttons=%s",
                        selected_kind,
                        [text for text, _, _ in all_buttons],
                    )
                    self.state.last_signature = signature
                    return False

            if selected is None and contains_any(message_text, WORN_EQUIPMENT_MARKERS):
                if not self.state.repair_mode:
                    logger.info("Worn equipment detected; starting repair flow")
                self.state.repair_mode = True
                self.state.repair_step = 0
                self.state.return_to_floor_mode = False

            if selected is None:
                # Stamina receives every button, including the normally forbidden
                # battle button "Зелья" and the explicit return button.
                selected, selected_kind = select_stamina_action(
                    message_text,
                    all_buttons,
                    self.state,
                )

            if selected is None and selected_kind == "stamina_wait":
                logger.info(
                    "Waiting for stamina route=%s step=%s; buttons=%s",
                    self.state.stamina_route,
                    self.state.stamina_step + 1,
                    [text for text, _, _ in all_buttons],
                )
                self.state.last_signature = signature
                return False

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

            if selected is None and not self.state.repair_mode:
                selected, selected_kind = select_player_encounter_action(
                    message_text,
                    buttons,
                )

            if selected is None and not self.state.repair_mode:
                selected, selected_kind = select_random_event_action(
                    message_text,
                    buttons,
                )

            # Обычный бой теперь обрабатывается отдельным модулем. Приоритет строгий:
            # Скрытая атака -> Удар 2 рук -> Удар в воздухе -> Обычная атака.
            if selected is None and not self.state.repair_mode:
                selected, selected_kind = select_combat_action(buttons)

            if (
                selected is None
                and not self.state.repair_mode
                and self.state.target_floor is not None
            ):
                selected, selected_kind = select_farm_action(
                    buttons,
                    self.state.target_floor,
                )

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
                    "No matching action. repair_mode=%s, repair_step=%s, stamina_mode=%s, stamina_route=%s, stamina_step=%s, floor=%s, buttons=%s",
                    self.state.repair_mode,
                    self.state.repair_step,
                    self.state.stamina_mode,
                    self.state.stamina_route,
                    self.state.stamina_step,
                    self.state.target_floor,
                    [text for text, _, _ in all_buttons],
                )
                self.state.last_signature = signature
                return False

            button_text, row, column, action_name, counter = selected

            forbidden = "профил" in button_text or contains_any(button_text, NEVER_CLICK)
            if forbidden and selected_kind != "stamina_step":
                logger.error("Blocked forbidden button: %s", button_text)
                self.state.last_signature = signature
                return False

            if (
                button_text.startswith("локации") or " локации" in button_text
            ) and selected_kind != "repair_step":
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

            if selected_kind == "stamina_step":
                self.state.stamina_step += 1
                if self.state.stamina_step >= stamina_flow_length(self.state):
                    completed_route = self.state.stamina_route
                    reset_stamina_route(self.state)
                    if completed_route == "exploration":
                        self.state.return_to_floor_mode = (
                            self.state.target_floor is not None
                        )
                    logger.info(
                        "Stamina restoration completed via %s route",
                        completed_route,
                    )

            elif selected_kind == "repair_step":
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
