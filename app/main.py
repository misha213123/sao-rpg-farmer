from __future__ import annotations

import asyncio
import logging

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.config import Settings
from app.engine import FarmerEngine
from app.state import RuntimeState

HELP_TEXT = """Команды управления:
/on — включить автоматику
/off — выключить автоматику
/status — показать состояние
/click — обработать последнее сообщение вручную
/help — показать команды

Команды отправляйте сюда, в «Избранное».
"""


async def run() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger("sao-rpg-farmer")

    state = RuntimeState(enabled=settings.auto_start)
    engine = FarmerEngine(settings, state)
    client = TelegramClient(StringSession(settings.string_session), settings.api_id, settings.api_hash)

    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("STRING_SESSION is invalid or no longer authorized")

    game_bot = await client.get_entity(settings.game_bot)
    me = await client.get_me()
    logger.info("Connected as %s (%s)", getattr(me, "username", None) or me.first_name, me.id)
    logger.info("Game bot: %s", settings.game_bot)

    async def process_latest(force: bool = False) -> bool:
        async for message in client.iter_messages(game_bot, limit=1):
            return await engine.process(message, force=force)
        return False

    @client.on(events.NewMessage(from_users=game_bot))
    async def on_game_message(event: events.NewMessage.Event) -> None:
        await engine.process(event.message)

    @client.on(events.MessageEdited(from_users=game_bot))
    async def on_game_message_edited(event: events.MessageEdited.Event) -> None:
        await engine.process(event.message)

    @client.on(events.NewMessage(chats="me", outgoing=True))
    async def on_saved_message(event: events.NewMessage.Event) -> None:
        command = (event.raw_text or "").strip().lower()
        if not command.startswith("/"):
            return

        if command == "/on":
            state.enabled = True
            state.last_signature = None
            await event.reply("Автоматизация включена ✅")
            clicked = await process_latest()
            if not clicked:
                await event.reply("Последнее сообщение проверено. Подходящая кнопка пока не найдена.")

        elif command == "/off":
            state.enabled = False
            await event.reply("Автоматизация выключена ⛔")

        elif command == "/status":
            await event.reply(state.status_text())

        elif command == "/click":
            clicked = await process_latest(force=True)
            await event.reply("Кнопка нажата ✅" if clicked else "Подходящая кнопка не найдена.")

        elif command == "/help":
            await event.reply(HELP_TEXT)

    if state.enabled:
        await process_latest()

    logger.info("Farmer is running. Control it from Saved Messages.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
