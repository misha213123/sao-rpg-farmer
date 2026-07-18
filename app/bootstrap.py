from __future__ import annotations

import pathlib
import re
import runpy


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
ENGINE_PATH = ROOT / "engine.py"


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    # Актуальное расписание по московскому времени.
    source = source.replace(":07 —", ":10 —")
    source = source.replace(":10 —", ":12 —")
    source = source.replace("at :07 MSK", "at :10 MSK")
    source = source.replace("at :10 MSK", "at :12 MSK")
    source = source.replace("и :10 ничего", "и :12 ничего")
    source = source.replace("waiting for :10 MSK", "waiting for :12 MSK")
    source = source.replace("now_moscow.minute == 7", "now_moscow.minute == 10")
    source = source.replace("now_moscow.minute >= 10", "now_moscow.minute >= 12")

    # Гильдия: первый бой запускается через «Подтвердить атаку»,
    # после каждой победы нажимается только «Ещё раз: Agrognomiki».
    # Если атак нет, отправляем /start и ждём арену в :12.
    guild_replacement = '''                if state.scheduled_step == 6:
                    no_guild_attacks = (
                        "осталось атак в этом часе: 0" in message_text
                        or "осталось атак в этом часе 0" in message_text
                        or "осталось в этом часе 0 атак" in message_text
                        or "осталось 0 атак" in message_text
                        or ("0 атак" in message_text and "остал" in message_text)
                        or "нет доступных атак" in message_text
                        or "атаки исчерпаны" in message_text
                        or "боёв больше нет" in message_text
                        or "боев больше нет" in message_text
                    )
                    if no_guild_attacks:
                        logger.info("Guild attacks unavailable; sending /start and waiting for :12 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        await client.send_message(game_bot, "/start")
                        return True

                    # Первый бой: единственный раз нажимаем «Подтвердить атаку».
                    if state.scheduled_confirm_clicks == 0:
                        if await click_matching(message, ("подтвердить атаку",)):
                            state.scheduled_confirm_clicks = 1
                            state.last_signature = None
                            logger.info("Initial guild battle started")
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

                    # После победы запускаем следующий бой только кнопкой
                    # «Ещё раз: Agrognomiki». Всего должно быть 10 боёв.
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
                        logger.info("Ten guild battles completed; sending /start and waiting for :12 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        await client.send_message(game_bot, "/start")
                        return True

                    logger.info(
                        "Waiting for guild combat/repeat/0 attacks; buttons=%s text=%s",
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

    # Арена: первый бой — «Рандомный бой», следующие — «Ещё бой».
    # Если боёв нет или уже 5/5, сразу /start и обычный фарм.
    arena_replacement = '''                if state.scheduled_step == 2:
                    arena_exhausted = (
                        ("5/5" in message_text and "бо" in message_text)
                        or "использовано 5/5" in message_text
                        or "рандомных боев использовано: 5/5" in message_text
                        or "рандомных боёв использовано: 5/5" in message_text
                        or "боёв в час 5/5" in message_text
                        or "боев в час 5/5" in message_text
                        or "нет доступных боев" in message_text
                        or "нет доступных боёв" in message_text
                        or "рандомные бои недоступны" in message_text
                        or "бои исчерпаны" in message_text
                        or "боёв больше нет" in message_text
                        or "боев больше нет" in message_text
                    )
                    if arena_exhausted:
                        await finish_arena_route()
                        return True

                    # Первый бой открываем через «Рандомный бой».
                    if state.scheduled_arena_clicks == 0:
                        if await click_matching(message, ("рандомный бой",)):
                            state.scheduled_arena_clicks = 1
                            state.last_signature = None
                            logger.info("Arena battle started: 1/5")
                            return True

                    # После результата нажимаем именно «Ещё бой».
                    if state.scheduled_arena_clicks < 5:
                        for text, row, column in buttons:
                            if "ещё бой" in text or "еще бой" in text:
                                await asyncio.sleep(1.0)
                                await message.click(i=row, j=column)
                                state.scheduled_arena_clicks += 1
                                state.last_signature = None
                                logger.info(
                                    "Arena battle started: %s/5",
                                    state.scheduled_arena_clicks,
                                )
                                return True

                    if state.scheduled_arena_clicks >= 5:
                        await finish_arena_route()
                        return True

                    logger.info(
                        "Waiting for arena repeat (%s/5); buttons=%s text=%s",
                        state.scheduled_arena_clicks,
                        texts,
                        message_text,
                    )
                    return True

'''

    arena_pattern = re.compile(
        r"                if state\.scheduled_step == 2:\n.*?\n            logger\.warning\(",
        re.DOTALL,
    )
    source, arena_count = arena_pattern.subn(
        arena_replacement + "            logger.warning(",
        source,
        count=1,
    )
    if arena_count != 1:
        raise RuntimeError("Could not patch arena route block in app/main.py")

    # Арена должна запускаться в :12 независимо от того, успела ли гильдия
    # корректно перейти в wait_arena. Это устраняет пропуск запуска арены.
    source = source.replace(
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 12
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase == "wait_arena"
                ):
                    await start_arena_route(hour_key)''',
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 12
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase != "arena"
                ):
                    await start_arena_route(hour_key)''',
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
                    # После второго «Починить всё» отправляем игровому боту /start.
                    # Далее обычная навигация вернёт персонажа на сохранённый этаж.
                    await message.respond("/start")
                    self.state.last_signature = None
                    logger.info(
                        "Equipment repair completed; /start sent; returning to floor %s",
                        self.state.target_floor,
                    )'''
    if old not in source:
        raise RuntimeError("Could not patch repair completion in app/engine.py")
    ENGINE_PATH.write_text(source.replace(old, new, 1), encoding="utf-8")


patch_engine()
patch_main()
runpy.run_module("app.main", run_name="__main__")