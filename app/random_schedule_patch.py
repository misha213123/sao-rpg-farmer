from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
STATE_PATH = ROOT / "state.py"


def patch_state() -> None:
    source = STATE_PATH.read_text(encoding="utf-8")

    marker = "    scheduled_arena_clicks: int = 0\n"
    fields = (
        "    random_schedule_hour: str | None = None\n"
        "    random_guild_minute: int | None = None\n"
        "    random_arena_minute: int | None = None\n"
    )
    if "random_schedule_hour:" not in source and marker in source:
        source = source.replace(marker, marker + fields, 1)

    STATE_PATH.write_text(source, encoding="utf-8")


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    if "import random\n" not in source:
        source = source.replace("import logging\n", "import logging\nimport random\n", 1)

    scheduled_pattern = re.compile(
        r"    async def scheduled_loop\(\) -> None:\n.*?\n    async def begin_navigation",
        re.DOTALL,
    )

    scheduled_replacement = '''    async def scheduled_loop() -> None:
        while True:
            try:
                now_moscow = datetime.now(MOSCOW_TZ)
                hour_key = now_moscow.strftime("%Y-%m-%d-%H")

                # Один раз в начале каждого часа выбираем стабильное расписание:
                # гильдия в диапазоне :01-:05, арена в диапазоне :06-:10.
                if state.random_schedule_hour != hour_key:
                    state.random_schedule_hour = hour_key
                    state.random_guild_minute = random.randint(1, 5)
                    state.random_arena_minute = random.randint(6, 10)
                    logger.info(
                        "Hourly random schedule selected: guild=:%02d arena=:%02d MSK",
                        state.random_guild_minute,
                        state.random_arena_minute,
                    )

                scheduled_enabled = (
                    state.enabled
                    and state.automation_mode in ("full", "scheduled_only")
                )

                # Пока активен любой маршрут, другой маршрут не запускаем.
                # Если время уже прошло из-за боя или предыдущего маршрута,
                # запуск произойдёт сразу после освобождения scheduled_mode.
                if scheduled_enabled and not state.scheduled_mode:
                    guild_due = (
                        state.random_guild_minute is not None
                        and now_moscow.minute >= state.random_guild_minute
                        and state.scheduled_last_guild_hour != hour_key
                    )
                    arena_due = (
                        state.random_arena_minute is not None
                        and now_moscow.minute >= state.random_arena_minute
                        and state.scheduled_last_arena_hour != hour_key
                    )

                    # Гильдия имеет приоритет, если оба маршрута просрочены.
                    if guild_due:
                        await start_guild_route(hour_key)
                    elif arena_due:
                        await start_arena_route(hour_key)

                if state.scheduled_mode:
                    await process_latest(force=True)

            except Exception:
                logger.exception("Scheduled loop failed")

            await asyncio.sleep(3)

    async def begin_navigation'''

    source, count = scheduled_pattern.subn(
        lambda _match: scheduled_replacement,
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not replace scheduled_loop in app/main.py")

    # Показываем выбранные минуты в /status без изменения основной логики статуса.
    status_call = '        elif command == "/status":\n            await event.reply(state.status_text())'
    status_replacement = '''        elif command == "/status":
            schedule_text = state.status_text()
            if state.random_schedule_hour is not None:
                guild_minute = (
                    f":{state.random_guild_minute:02d}"
                    if state.random_guild_minute is not None
                    else "не выбрано"
                )
                arena_minute = (
                    f":{state.random_arena_minute:02d}"
                    if state.random_arena_minute is not None
                    else "не выбрано"
                )
                schedule_text += (
                    f"\\nГильдейский зачёт в этом часу: {guild_minute} МСК"
                    f"\\nАрена в этом часу: {arena_minute} МСК"
                )
            await event.reply(schedule_text)'''
    if "Гильдейский зачёт в этом часу" not in source and status_call in source:
        source = source.replace(status_call, status_replacement, 1)

    MAIN_PATH.write_text(source, encoding="utf-8")


def patch_all() -> None:
    patch_state()
    patch_main()
