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
            result.append((_normalize(getattr(button, "text", "")), row_index, column_index))
    return result


async def _finish_active_battle(client: TelegramClient, entity) -> None:
    priorities = (
        "скрытая атака",
        "удар 2 рук",
        "удар двух рук",
        "обычная атака",
        "атаковать",
    )
    active_markers = (
        "вы находитесь в бою",
        "атакуйте или сбегите",
        "выберите действие",
        "hp босса",
        "вы вернулись к боссу",
    )
    battle_seen = False
    idle = 0

    for _ in range(240):
        messages = await client.get_messages(entity, limit=1)
        latest = messages[0] if messages else None
        if latest is None:
            await asyncio.sleep(0.8)
            continue

        text = _normalize(latest.raw_text)
        buttons = _buttons(latest)
        selected = None

        for marker in priorities:
            for button_text, row, column in buttons:
                if marker in button_text:
                    selected = (row, column)
                    break
            if selected is not None:
                break

        if selected is not None:
            battle_seen = True
            idle = 0
            try:
                await latest.click(i=selected[0], j=selected[1])
            except Exception:
                await asyncio.sleep(0.8)
                continue
            await asyncio.sleep(1.3)
            continue

        if any(marker in text for marker in active_markers):
            battle_seen = True
            idle = 0
            await asyncio.sleep(0.9)
            continue

        if not battle_seen:
            return

        idle += 1
        if idle >= 3:
            return
        await asyncio.sleep(0.8)


async def guarded_send_message(self, entity, message="", *args, **kwargs):
    if isinstance(message, str) and message.strip().lower() == "/start":
        await _finish_active_battle(self, entity)
    return await _original_send_message(self, entity, message, *args, **kwargs)


async def saved_messages_get_chat(self):
    chat = await _original_get_chat(self)
    raw = (getattr(self, "raw_text", "") or "").strip()

    if not (getattr(self, "out", False) and raw.startswith("/")):
        return chat

    client = getattr(self, "_client", None)
    if client is None:
        return chat

    me = await client.get_me()
    if getattr(chat, "id", None) == me.id:
        return me
    return chat


TelegramClient.send_message = guarded_send_message
events.NewMessage.Event.get_chat = saved_messages_get_chat

from app import bootstrap  # noqa: E402,F401
