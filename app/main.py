from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.config import Settings
from app.engine import FarmerEngine
from app.state import RuntimeState

HELP_TEXT = """Команды управления:
/start — начать переход на сохранённый этаж
/on — включить автоматику и выбрать этаж
/floor 25 — сменить этаж на 25
/off — выключить автоматику
/status — показать состояние
/click — обработать последнее сообщение вручную
/help — показать команды

Автоматические маршруты по московскому времени:
:07 — /start → Кланы → Гильдейский зачёт → Боевая доблесть → Выбрать цель → Agrognomiki → Подтвердить атаку. Затем Agrognomiki → Подтвердить атаку до 10 боёв.
После гильдии обычный фарм НЕ запускается.
:10 — Арена (PvP) → Рандомный бой 5 раз или до сообщения «использовано 5/5 боёв» → /start → обычный фарм.

Команды отправляйте сюда, в «Избранное».
"""

MOSCOW_TZ = timezone(timedelta(hours=3))


def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def message_buttons(message) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    if not message.buttons:
        return result
    for row_index, row in enumerate(message.buttons):
        for column_index, button in enumerate(row):
            result.append(
                (normalize(getattr(button, "text", "")), row_index, column_index)
            )
    return result


def parse_floor(value: str) -> int | None:
    match = re.search(r"\d+", value)
    if not match:
        return None
    floor = int(match.group())
    return floor if floor > 0 else None


def parse_plain_floor(value: str) -> int | None:
    value = value.strip()
    if not value.isdigit():
        return None
    floor = int(value)
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
    client = TelegramClient(
        StringSession(settings.string_session), settings.api_id, settings.api_hash
    )
    scheduled_lock = asyncio.Lock()

    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("STRING_SESSION is invalid or no longer authorized")

    game_bot = await client.get_entity(settings.game_bot)
    me = await client.get_me()
    logger.info(
        "Connected as %s (%s)",
        getattr(me, "username", None) or me.first_name,
        me.id,
    )
    logger.info("Game bot: %s", settings.game_bot)

    pending_floor = False
    restored_enabled = False
    async for saved in client.iter_messages("me", limit=150, reverse=True):
        raw = (saved.raw_text or "").strip()
        command = raw.lower()

        if command == "/off":
            restored_enabled = False
            pending_floor = False
            continue
        if command == "/on":
            pending_floor = True
            restored_enabled = False
            continue
        if command.startswith("/floor"):
            floor = parse_floor(command.removeprefix("/floor"))
            if floor is not None:
                state.target_floor = floor
                restored_enabled = True
                pending_floor = False
            continue
        if pending_floor:
            floor = parse_plain_floor(raw)
            if floor is not None:
                state.target_floor = floor
                restored_enabled = True
                pending_floor = False
            continue
        if command == "/start" and state.target_floor is not None:
            restored_enabled = True

    if state.target_floor is not None:
        logger.info("Restored floor from Saved Messages: %s", state.target_floor)
    state.enabled = restored_enabled and state.target_floor is not None
    state.return_to_floor_mode = state.enabled

    async def click_matching(message, markers: tuple[str, ...]) -> bool:
        for text, row, column in message_buttons(message):
            if all(marker in text for marker in markers):
                await asyncio.sleep(1.0)
                await message.click(i=row, j=column)
                logger.info(
                    "Scheduled route clicked: %s (phase=%s, step=%s, row=%s, column=%s)",
                    text,
                    state.scheduled_phase,
                    state.scheduled_step,
                    row,
                    column,
                )
                return True
        return False

    async def start_guild_route(hour_key: str) -> None:
        state.scheduled_last_guild_hour = hour_key
        state.scheduled_mode = True
        state.scheduled_phase = "guild"
        state.scheduled_step = 1
        state.scheduled_confirm_clicks = 0
        state.scheduled_arena_clicks = 0
        state.repair_mode = False
        state.return_to_floor_mode = False
        state.last_signature = None
        logger.info("Starting guild route at :07 MSK")
        await client.send_message(game_bot, "/start")

    async def start_arena_route(hour_key: str) -> None:
        state.scheduled_last_arena_hour = hour_key
        state.scheduled_mode = True
        state.scheduled_phase = "arena"
        state.scheduled_step = 1
        state.scheduled_arena_clicks = 0
        state.repair_mode = False
        state.return_to_floor_mode = False
        state.last_signature = None
        logger.info("Starting arena route at :10 MSK")
        await client.send_message(game_bot, "/start")

    async def finish_arena_route() -> None:
        logger.info("Arena completed; returning to ordinary farming")
        state.scheduled_mode = False
        state.scheduled_phase = ""
        state.scheduled_step = 0
        state.scheduled_runs += 1
        state.return_to_floor_mode = state.target_floor is not None
        state.last_signature = None
        await client.send_message(game_bot, "/start")

    async def handle_scheduled_route(message) -> bool:
        if not state.scheduled_mode:
            return False
        if scheduled_lock.locked():
            return True

        async with scheduled_lock:
            buttons = message_buttons(message)
            texts = [text for text, _, _ in buttons]
            message_text = normalize(message.raw_text)

            # Между завершением 10 гильдейских боёв и :10 ничего не нажимаем.
            if state.scheduled_phase == "wait_arena":
                return True

            if state.scheduled_phase == "guild":
                route_steps: dict[int, tuple[str, ...]] = {
                    1: ("кланы",),
                    2: ("гильдейский зачёт",),
                    3: ("боевая доблесть",),
                    4: ("выбрать цель",),
                    5: ("agrognomiki",),
                }

                if state.scheduled_step in route_steps:
                    if await click_matching(message, route_steps[state.scheduled_step]):
                        state.scheduled_step += 1
                        state.last_signature = None
                        return True

                    if state.scheduled_step == 1:
                        for text, row, column in buttons:
                            if "главное меню" in text:
                                await asyncio.sleep(1.0)
                                await message.click(i=row, j=column)
                                return True
                    logger.info(
                        "Guild route waiting for step %s; buttons=%s",
                        state.scheduled_step,
                        texts,
                    )
                    return True

                if state.scheduled_step == 6:
                    # Один подтверждённый клик = один гильдейский бой.
                    if await click_matching(message, ("подтвердить атаку",)):
                        state.scheduled_confirm_clicks += 1
                        state.last_signature = None
                        logger.info(
                            "Guild battle confirmed: %s/10",
                            state.scheduled_confirm_clicks,
                        )

                        if state.scheduled_confirm_clicks >= 10:
                            logger.info("Ten guild battles completed; waiting for :10 MSK")
                            state.scheduled_phase = "wait_arena"
                            state.scheduled_step = 0
                            now_moscow = datetime.now(MOSCOW_TZ)
                            if now_moscow.minute >= 10:
                                await start_arena_route(
                                    now_moscow.strftime("%Y-%m-%d-%H")
                                )
                        else:
                            # После каждой атаки снова выбираем Agrognomiki.
                            state.scheduled_step = 5
                        return True

                    # Если игра уже сообщает, что боёв нет, прекращаем раньше.
                    zero_attacks = (
                        "осталось в этом часе 0 атак" in message_text
                        or "осталось 0 атак" in message_text
                        or ("0 атак" in message_text and "остал" in message_text)
                    )
                    if zero_attacks:
                        logger.info("Guild attacks exhausted early; waiting for :10 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        return True

                    logger.info(
                        "Waiting for Confirm attack or Agrognomiki; buttons=%s text=%s",
                        texts,
                        message_text,
                    )
                    return True

            if state.scheduled_phase == "arena":
                if state.scheduled_step == 1:
                    if await click_matching(message, ("арена", "pvp")):
                        state.scheduled_step = 2
                        state.last_signature = None
                        return True
                    for text, row, column in buttons:
                        if "главное меню" in text:
                            await asyncio.sleep(1.0)
                            await message.click(i=row, j=column)
                            return True
                    logger.info("Arena route waiting for Arena (PvP); buttons=%s", texts)
                    return True

                if state.scheduled_step == 2:
                    arena_exhausted = (
                        ("5/5" in message_text and "бо" in message_text)
                        or "использовано 5/5" in message_text
                        or "боёв в час 5/5" in message_text
                        or "боев в час 5/5" in message_text
                    )
                    if arena_exhausted or state.scheduled_arena_clicks >= 5:
                        await finish_arena_route()
                        return True

                    if await click_matching(message, ("рандомный бой",)):
                        state.scheduled_arena_clicks += 1
                        state.last_signature = None
                        logger.info(
                            "Arena random battle: %s/5",
                            state.scheduled_arena_clicks,
                        )
                        if state.scheduled_arena_clicks >= 5:
                            await asyncio.sleep(1.0)
                            await finish_arena_route()
                        return True

                    logger.info(
                        "Waiting for Random battle (%s/5); buttons=%s",
                        state.scheduled_arena_clicks,
                        texts,
                    )
                    return True

            logger.warning(
                "Unknown scheduled phase=%s step=%s",
                state.scheduled_phase,
                state.scheduled_step,
            )
            return True

    async def process_latest(force: bool = False) -> bool:
        async for message in client.iter_messages(game_bot, limit=1):
            if await handle_scheduled_route(message):
                return True
            return await engine.process(message, force=force)
        return False

    async def scheduled_loop() -> None:
        while True:
            try:
                now_moscow = datetime.now(MOSCOW_TZ)
                hour_key = now_moscow.strftime("%Y-%m-%d-%H")

                if (
                    state.enabled
                    and now_moscow.minute == 7
                    and state.scheduled_last_guild_hour != hour_key
                    and not state.scheduled_mode
                ):
                    await start_guild_route(hour_key)

                if (
                    state.enabled
                    and now_moscow.minute >= 10
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase == "wait_arena"
                ):
                    await start_arena_route(hour_key)

                if state.scheduled_mode and state.scheduled_phase != "wait_arena":
                    await process_latest(force=True)

            except Exception:
                logger.exception("Scheduled loop failed")

            await asyncio.sleep(3)

    async def begin_navigation(event: events.NewMessage.Event) -> None:
        if state.target_floor is None:
            state.enabled = False
            state.awaiting_floor = True
            await event.reply("Сначала выбери этаж. Напиши только номер, например: 25")
            return

        state.enabled = True
        state.awaiting_floor = False
        state.repair_mode = False
        state.repair_step = 0
        state.scheduled_mode = False
        state.scheduled_phase = ""
        state.scheduled_step = 0
        state.return_to_floor_mode = True
        state.return_to_floor_step = 0
        state.last_signature = None
        await event.reply(
            f"Запускаю фарм ✅\nЭтаж: {state.target_floor}\n"
            "Маршрут: Главное меню → Исследовать → этаж → последняя Локация → Начать/Продолжить исследование."
        )
        if not await process_latest():
            await event.reply("Жду следующего сообщения игры, чтобы продолжить переход.")

    async def activate_floor(floor: int, event: events.NewMessage.Event) -> None:
        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
        state.repair_mode = False
        state.repair_step = 0
        state.scheduled_mode = False
        state.scheduled_phase = ""
        state.scheduled_step = 0
        state.return_to_floor_mode = True
        state.return_to_floor_step = 0
        state.last_signature = None
        await event.reply(
            f"Автоматизация включена ✅\nВыбран этаж: {floor}\n"
            "Перехожу: Главное меню → Исследовать → этаж → последняя Локация → Начать/Продолжить исследование."
        )
        if not await process_latest():
            await event.reply("Жду следующего сообщения игры, чтобы продолжить переход.")

    @client.on(events.NewMessage(from_users=game_bot))
    async def on_game_message(event: events.NewMessage.Event) -> None:
        if await handle_scheduled_route(event.message):
            return
        await engine.process(event.message)

    @client.on(events.MessageEdited(from_users=game_bot))
    async def on_game_message_edited(event: events.MessageEdited.Event) -> None:
        if await handle_scheduled_route(event.message):
            return
        await engine.process(event.message)

    @client.on(events.NewMessage(chats="me", outgoing=True))
    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()
        command = raw.lower()

        if state.awaiting_floor and not command.startswith("/"):
            floor = parse_plain_floor(raw)
            if floor is None:
                await event.reply("Напиши номер этажа цифрами, например: 25")
                return
            await activate_floor(floor, event)
            return

        if not command.startswith("/"):
            return

        if command == "/start":
            await begin_navigation(event)
        elif command == "/on":
            state.enabled = False
            state.awaiting_floor = True
            state.return_to_floor_mode = False
            state.scheduled_mode = False
            state.scheduled_phase = ""
            await event.reply(
                "На каком этаже фармить?\nНапиши только номер, например: 25"
            )
        elif command.startswith("/floor"):
            floor = parse_floor(command.removeprefix("/floor"))
            if floor is None:
                state.awaiting_floor = True
                await event.reply(
                    "Напиши номер этажа следующим сообщением, например: 25"
                )
                return
            await activate_floor(floor, event)
        elif command == "/off":
            state.enabled = False
            state.awaiting_floor = False
            state.repair_mode = False
            state.return_to_floor_mode = False
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            await event.reply("Автоматизация выключена ⛔")
        elif command == "/status":
            await event.reply(state.status_text())
        elif command == "/click":
            clicked = await process_latest(force=True)
            await event.reply(
                "Кнопка нажата ✅" if clicked else "Подходящая кнопка не найдена."
            )
        elif command == "/help":
            await event.reply(HELP_TEXT)

    asyncio.create_task(scheduled_loop())

    if state.enabled:
        state.last_signature = None
        await process_latest()

    logger.info("Farmer is running. Control it from Saved Messages.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
