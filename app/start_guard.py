from __future__ import annotations

import asyncio
import re

from telethon import TelegramClient


_original_send_message = TelegramClient.send_message


def _normalize(value: str | None) -> str:
    cleaned = re.sub(r"[^a-zа-яё0-9/]+", " ", (value or "").lower())
    return " ".join(cleaned.split())


def _buttons(message) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    if not message or not message.buttons:
        return result
    for row_index, row in enumerate(message.buttons):
        for column_index, button in enumerate(row):
            result.append(
                (_normalize(getattr(button, "text", "")), row_index, column_index)
            )
    return result


async def _finish_active_battle(client: TelegramClient, entity) -> None:
    attack_priorities = (
        "скрытая атака",
        "удар 2 рук",
        "удар двух рук",
        "обычная атака",
        "атаковать",
    )

    while True:
        messages = await client.get_messages(entity, limit=1)
        latest = messages[0] if messages else None
        if latest is None:
            return

        text = _normalize(latest.raw_text)
        buttons = _buttons(latest)
        selected: tuple[int, int] | None = None

        for marker in attack_priorities:
            for button_text, row, column in buttons:
                if marker in button_text:
                    selected = (row, column)
                    break
            if selected is not None:
                break

        if selected is not None:
            await latest.click(i=selected[0], j=selected[1])
            await asyncio.sleep(1.2)
            continue

        if "вы находитесь в бою" in text:
            await asyncio.sleep(1.0)
            continue

        return


async def guarded_send_message(self, entity, message="", *args, **kwargs):
    if isinstance(message, str) and message.strip().lower() == "/start":
        await _finish_active_battle(self, entity)
    return await _original_send_message(self, entity, message, *args, **kwargs)


TelegramClient.send_message = guarded_send_message

from app import bootstrap  # noqa: E402,F401
