from __future__ import annotations

import asyncio
import re

from telethon import TelegramClient, events


_original_send_message = TelegramClient.send_message
_original_get_chat = events.NewMessage.Event.get_chat


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


async def saved_messages_get_chat(self):
    """Распознаёт команды только в «Избранном», а не в игровом боте."""
    chat = await _original_get_chat(self)
    raw = (getattr(self, "raw_text", "") or "").strip()

    if not (getattr(self, "out", False) and raw.startswith("/")):
        return chat

    client = getattr(self, "_client", None)
    if client is None:
        return chat

    me = await client.get_me()
    chat_id = getattr(chat, "id", None)

    # Подменяем чат на self только когда команда действительно отправлена
    # в «Избранное». Команды /start, отправленные игровому боту, больше не
    # попадают в обработчик управления и не могут повторно включить фарм.
    if chat_id == me.id:
        return me

    return chat


TelegramClient.send_message = guarded_send_message
events.NewMessage.Event.get_chat = saved_messages_get_chat

from app import bootstrap  # noqa: E402,F401
