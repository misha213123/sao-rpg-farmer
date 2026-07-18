from __future__ import annotations

import pathlib
import re
import runpy


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
ENGINE_PATH = ROOT / "engine.py"


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    # Каноническое расписание по московскому времени:
    # :50 — гильдейский зачёт, :57 — арена.
    source = source.replace(":07 —", ":50 —")
    source = source.replace(":10 —", ":57 —")
    source = source.replace("at :07 MSK", "at :50 MSK")
    source = source.replace("at :10 MSK", "at :57 MSK")
    source = source.replace("и :10 ничего", "и :57 ничего")
    source = source.replace("waiting for :10 MSK", "waiting for :57 MSK")
    source = source.replace("now_moscow.minute == 7", "now_moscow.minute == 50")
    source = source.replace("now_moscow.minute >= 10", "now_moscow.minute >= 57")

    # В маршрутах учитываем только буквы, цифры и пробелы — эмодзи игнорируются.
    source = source.replace(
        '''def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())''',
        '''def normalize(value: str | None) -> str:
    cleaned = re.sub(r"[^a-zа-яё0-9/]+", " ", (value or "").lower())
    return " ".join(cleaned.split())''',
        1,
    )

    guild_replacement = '''                if state.scheduled_step == 6:
                    no_guild_attacks = (
                        "осталось атак в этом часе 0" in message_text
                        or "осталось в этом часе 0 атак" in message_text
                        or "осталось 0 атак" in message_text
                        or ("0 атак" in message_text and "остал" in message_text)
                        or "нет доступных атак" in message_text
                        or "атаки исчерпаны" in message_text
                        or "лимит pvp боев исчерпан" in message_text
                        or "лимит pvp боёв исчерпан" in message_text
                        or ("лимит" in message_text and "исчерпан" in message_text)
                    )
                    if no_guild_attacks:
                        logger.info("Guild attacks exhausted; sending /start and waiting for :57 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        await client.send_message(game_bot, "/start")
                        return True

                    # Первый бой запускаем через «Подтвердить атаку».
                    if state.scheduled_confirm_clicks == 0:
                        if await click_matching(message, ("подтвердить атаку",)):
                            state.scheduled_confirm_clicks = 1
                            state.last_signature = None
                            logger.info("Initial guild battle started: 1/10")
                            return True

                    # Внутри боя используем заданный приоритет атак.
                    for combat_markers in (
                        ("скрытая атака",),
                        ("удар 2 рук",),
                        ("обычная атака",),
                    ):
                        if await click_matching(message, combat_markers):
                            state.last_signature = None
                            return True

                    # После каждого результата нажимаем только
                    # «Ещё раз: Agrognomiki» и проводим максимум 10 боёв.
                    if state.scheduled_confirm_clicks < 10:
                        repeated = await click_matching(
                            message, ("ещё раз", "agrognomiki")
                        )
                        if not repeated:
                            repeated = await click_matching(
                                message, ("еще раз", "agrognomiki")
                            )
                        if repeated:
                            state.scheduled_confirm_clicks += 1
                            state.last_signature = None
                            logger.info(
                                "Guild battle started: %s/10",
                                state.scheduled_confirm_clicks,
                            )
                            return True

                    if state.scheduled_confirm_clicks >= 10:
                        logger.info("Ten guild battles completed; sending /start and waiting for :57 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        await client.send_message(game_bot, "/start")
                        return True

                    logger.info(
                        "Waiting for guild combat/repeat/exhaustion; buttons=%s text=%s",
                        texts,
                        message_text,
                    )
                    return True

'''

    guild_pattern = re.compile(
        r"                if state\.scheduled_step == 6:\n.*?\n            if state\.scheduled_phase == \"arena\":",
        re.DOTALL,
    )
    source, guild_count = guild_pattern.subn(
        guild_replacement + '            if state.scheduled_phase == "arena":',
        source,
        count=1,
    )
    if guild_count != 1:
        raise RuntimeError("Could not patch guild route block in app/main.py")

    # Сообщение о лимите завершает арену и возвращает обычный фарм.
    source = source.replace(
        '''                    arena_exhausted = (
                        ("5/5" in message_text and "бо" in message_text)
                        or "использовано 5/5" in message_text
                        or "боёв в час 5/5" in message_text
                        or "боев в час 5/5" in message_text
                    )''',
        '''                    arena_exhausted = (
                        ("5/5" in message_text and "бо" in message_text)
                        or "использовано 5/5" in message_text
                        or "боёв в час 5/5" in message_text
                        or "боев в час 5/5" in message_text
                        or "достигли лимита рандомных боев" in message_text
                        or "достигли лимита рандомных боёв" in message_text
                        or "лимит 5 боев в час" in message_text
                        or "лимит 5 боёв в час" in message_text
                        or "лимит pvp боев исчерпан" in message_text
                        or "лимит pvp боёв исчерпан" in message_text
                    )''',
        1,
    )

    # Арена запускается каждый час в :57 независимо от состояния ожидания.
    source = source.replace(
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 57
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase == "wait_arena"
                ):
                    await start_arena_route(hour_key)''',
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 57
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase != "arena"
                ):
                    await start_arena_route(hour_key)''',
    )

    # Надёжный приём команд из «Избранного».
    source = source.replace(
        '@client.on(events.NewMessage(chats="me", outgoing=True))',
        '@client.on(events.NewMessage(outgoing=True))',
        1,
    )
    source = source.replace(
        '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()''',
        '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        if event.chat_id != me.id:
            return
        raw = (event.raw_text or "").strip()''',
        1,
    )

    MAIN_PATH.write_text(source, encoding="utf-8")


def patch_engine() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")
    old = '''                    self.state.return_to_floor_mode = self.state.target_floor is not None
                    logger.info(
                        "Equipment repair completed; returning to floor %s",
                        self.state.target_floor,
                    )'''
    new = '''                    self.state.return_to_floor_mode = self.state.target_floor is not None
                    await message.respond("/start")
                    self.state.last_signature = None
                    logger.info(
                        "Equipment repair completed; /start sent; returning to floor %s",
                        self.state.target_floor,
                    )'''
    if old in source:
        source = source.replace(old, new, 1)
    ENGINE_PATH.write_text(source, encoding="utf-8")


patch_engine()
patch_main()
runpy.run_module("app.main", run_name="__main__")
