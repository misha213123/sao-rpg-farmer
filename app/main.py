from __future__ import annotations

import asyncio
import logging
import re

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.config import Settings
from app.engine import FarmerEngine
from app.state import RuntimeState

HELP_TEXT = """Команды управления:
/on — включить автоматику и выбрать этаж
/floor 25 — сменить этаж на 25
/off — выключить автоматику
/status — показать состояние
/click — обработать последнее сообщение вручную
/help — показать команды

Команды отправляйте сюда, в «Избранное».
"""


def parse_floor(value: str) -> int | None:
    match = re.search(r"\d+", value)
    if not match:
        return None
    floor = int(match.group())
    return floor if floor > 0 else None


async def run() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logger = logging.getLogger("sao-rpg-farmer")

    state = RuntimeState(enabled=False)
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

    async def activate_floor(floor: int, event: events.NewMessage.Event) -> None:
        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
        state.repair_mode = False
        state.repair_step = 0
        state.return_to_floor_mode = True
        state.return_to_floor_step = 0
        state.last_signature = None
        await event.reply(
            f"Автоматизация включена ✅\nВыбран этаж: {floor}\n"
            "Перехожу: Главное меню → Исследовать → выбранный этаж."
        )
        clicked = await process_latest()
        if not clicked:
            await event.reply("Жду следующего сообщения игры, чтобы продолжить переход.")

    @client.on(events.NewMessage(from_users=game_bot))
    async def on_game_message(event: events.NewMessage.Event) -> None:
        await engine.process(event.message)

    @client.on(events.MessageEdited(from_users=game_bot))
    async def on_game_message_edited(event: events.MessageEdited.Event) -> None:
        await engine.process(event.message)

    @client.on(events.NewMessage(chats="me", outgoing=True))
    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()
        command = raw.lower()

        if state.awaiting_floor and not command.startswith("/"):
            floor = parse_floor(raw)
            if floor is None:
                await event.reply("Напиши номер этажа цифрами, например: 25")
                return
            await activate_floor(floor, event)
            return

        if not command.startswith("/"):
            return

        if command == "/on":
            state.enabled = False
            state.awaiting_floor = True
            state.return_to_floor_mode = False
            await event.reply(
                "На каком этаже фармить?\n"
                "Напиши только номер, например: 25"
            )

        elif command.startswith("/floor"):
            floor = parse_floor(command.removeprefix("/floor"))
            if floor is None:
                state.awaiting_floor = True
                await event.reply("Напиши номер этажа следующим сообщением, например: 25")
                return
            await activate_floor(floor, event)

        elif command == "/off":
            state.enabled = False
            state.awaiting_floor = False
            state.repair_mode = False
            state.return_to_floor_mode = False
            await event.reply("Автоматизация выключена ⛔")

        elif command == "/status":
            await event.reply(state.status_text())

        elif command == "/click":
            clicked = await process_latest(force=True)
            await event.reply("Кнопка нажата ✅" if clicked else "Подходящая кнопка не найдена.")

        elif command == "/help":
            await event.reply(HELP_TEXT)

    logger.info("Farmer is running. Control it from Saved Messages.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
