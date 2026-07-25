from __future__ import annotations

import re

from telethon import TelegramClient, events


_original_send_message = TelegramClient.send_message
_original_get_chat = events.NewMessage.Event.get_chat


def _normalize(value: str | None) -> str:
    cleaned = re.sub(r"[^a-zа-яё0-9/]+", " ", (value or "").lower())
    return " ".join(cleaned.split())


async def guarded_send_message(self, entity, message="", *args, **kwargs):
    """Отправляет сообщения без скрытых игровых действий.

    Раньше перед каждым исходящим /start этот модуль самостоятельно находил
    активный бой и нажимал атаки. Такие клики выполнялись вне RuntimeState и
    поэтому могли продолжаться даже после команды /off. Теперь /start только
    отправляется адресату, а любые игровые действия выполняются исключительно
    основным движком, который проверяет state.enabled.
    """
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
