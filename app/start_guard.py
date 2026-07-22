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

    empty_checks = 0
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
            empty_checks = 0
            await latest.click(i=selected[0], j=selected[1])
            await asyncio.sleep(1.2)
            continue

        if "вы находитесь в бою" in text:
            empty_checks = 0
            await asyncio.sleep(1.0)
            continue

        # Одно промежуточное сообщение без кнопок ещё не означает конец боя.
        empty_checks += 1
        if empty_checks < 3:
            await asyncio.sleep(1.0)
            continue

        return


async def guarded_send_message(self, entity, message="", *args, **kwargs):
    if isinstance(message, str) and message.strip().lower() == "/start":
        await _finish_active_battle(self, entity)
    return await _original_send_message(self, entity, message, *args, **kwargs)


async def saved_messages_get_chat(self):
    """Надёжно распознаёт команды только в чате «Избранное»."""
    raw = (getattr(self, "raw_text", "") or "").strip()
    if not (getattr(self, "out", False) and raw.startswith("/")):
        return await _original_get_chat(self)

    client = getattr(self, "_client", None)
    if client is None:
        return await _original_get_chat(self)

    me = await client.get_me()

    # В разных версиях Telethon Saved Messages может определяться через
    # chat_id, peer_id.user_id либо объект чата. Проверяем все варианты.
    chat_id = getattr(self, "chat_id", None)
    peer_id = getattr(self, "peer_id", None)
    peer_user_id = getattr(peer_id, "user_id", None)

    if chat_id == me.id or peer_user_id == me.id:
        return me

    chat = await _original_get_chat(self)
    if getattr(chat, "id", None) == me.id:
        return me

    return chat


TelegramClient.send_message = guarded_send_message
events.NewMessage.Event.get_chat = saved_messages_get_chat

from app import bootstrap  # noqa: E402,F401
