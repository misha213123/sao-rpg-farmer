from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
STATE_PATH = ROOT / "state.py"


def patch_state() -> None:
    source = STATE_PATH.read_text(encoding="utf-8")
    if "automation_mode:" not in source:
        source = source.replace(
            "    target_floor: int | None = None\n",
            "    target_floor: int | None = None\n"
            "    awaiting_mode: bool = False\n"
            "    automation_mode: str = \"off\"\n",
            1,
        )
    STATE_PATH.write_text(source, encoding="utf-8")


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    # После /on сначала выбирается один из трёх режимов.
    awaiting_floor_marker = '''        if state.awaiting_floor and not command.startswith("/"):
'''
    mode_choice_block = '''        if state.awaiting_mode and not command.startswith("/"):
            choice = command.strip()
            mode_by_choice = {
                "1": "farm",
                "обычный фарм": "farm",
                "2": "full",
                "обычный фарм арена и гильдейский зачет": "full",
                "обычный фарм арена и гильдейский зачёт": "full",
                "3": "guild_only",
                "арена и гильдейский зачет": "guild_only",
                "арена и гильдейский зачёт": "guild_only",
                "только арена и гильдейский зачет": "guild_only",
                "только арена и гильдейский зачёт": "guild_only",
            }
            selected_mode = mode_by_choice.get(choice)
            if selected_mode is None:
                await event.reply(
                    "Выбери режим цифрой:\n"
                    "1 — Обычный фарм\n"
                    "2 — Обычный фарм + Арена + Гильдейский зачёт\n"
                    "3 — Только Арена + Гильдейский зачёт"
                )
                return

            state.awaiting_mode = False
            state.automation_mode = selected_mode
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.last_signature = None

            if selected_mode == "guild_only":
                state.enabled = True
                state.awaiting_floor = False
                state.return_to_floor_mode = False
                await event.reply(
                    "Режим включён: Арена + Гильдейский зачёт ✅\n"
                    "Обычный фарм отключён."
                )
                return

            state.enabled = False
            state.awaiting_floor = True
            state.return_to_floor_mode = False
            mode_name = (
                "Обычный фарм"
                if selected_mode == "farm"
                else "Обычный фарм + Арена + Гильдейский зачёт"
            )
            await event.reply(
                f"Выбран режим: {mode_name}\n"
                "На каком этаже фармить? Напиши только номер, например: 25"
            )
            return

'''
    if "mode_by_choice =" not in source:
        if awaiting_floor_marker not in source:
            raise RuntimeError("Could not insert /on mode selection")
        source = source.replace(
            awaiting_floor_marker,
            mode_choice_block + awaiting_floor_marker,
            1,
        )

    on_pattern = re.compile(
        r'''        elif command == "/on":\n.*?            \)\n        elif command\.startswith\("/floor"\):''',
        re.DOTALL,
    )
    on_replacement = '''        elif command == "/on":
            state.enabled = False
            state.awaiting_mode = True
            state.awaiting_floor = False
            state.return_to_floor_mode = False
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.last_signature = None
            await event.reply(
                "Что запустить?\n"
                "1 — Обычный фарм\n"
                "2 — Обычный фарм + Арена + Гильдейский зачёт\n"
                "3 — Только Арена + Гильдейский зачёт\n\n"
                "Ответь цифрой: 1, 2 или 3"
            )
        elif command.startswith("/floor"):'''
    source, on_count = on_pattern.subn(on_replacement, source, count=1)
    if on_count != 1 and "Что запустить?" not in source:
        raise RuntimeError("Could not replace /on command")

    # /off также сбрасывает выбранный режим и ожидание ответа.
    off_marker = '''        elif command == "/off":
            state.enabled = False
'''
    off_replacement = '''        elif command == "/off":
            state.enabled = False
            state.awaiting_mode = False
            state.automation_mode = "off"
'''
    if 'state.automation_mode = "off"' not in source:
        if off_marker not in source:
            raise RuntimeError("Could not extend /off command")
        source = source.replace(off_marker, off_replacement, 1)

    # При выборе этажа сохраняем выбранный режим. Если этаж меняют напрямую,
    # по умолчанию включается только обычный фарм.
    activate_marker = '''        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
'''
    activate_replacement = '''        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
        if state.automation_mode not in ("farm", "full"):
            state.automation_mode = "farm"
'''
    if "state.automation_mode not in" not in source:
        source = source.replace(activate_marker, activate_replacement, 1)

    # Гильдия работает в полном режиме и в режиме без обычного фарма.
    guild_condition = '''                    state.enabled
                    and now_moscow.minute == 4
'''
    guild_condition_new = '''                    state.enabled
                    and state.automation_mode in ("full", "guild_only")
                    and now_moscow.minute == 4
'''
    if 'state.automation_mode in ("full", "guild_only")' not in source:
        if guild_condition not in source:
            raise RuntimeError("Could not gate guild schedule by mode")
        source = source.replace(guild_condition, guild_condition_new, 1)

    # Арена работает в полном режиме и в режиме без обычного фарма.
    arena_condition = '''                    state.enabled
                    and now_moscow.minute >= 2
'''
    arena_condition_new = '''                    state.enabled
                    and state.automation_mode in ("full", "guild_only")
                    and now_moscow.minute >= 2
'''
    if 'state.automation_mode in ("full", "guild_only")\n                    and now_moscow.minute >= 2' not in source:
        if arena_condition not in source:
            raise RuntimeError("Could not gate arena schedule by mode")
        source = source.replace(arena_condition, arena_condition_new, 1)

    # В режиме «Арена + Гильдия» обычный обработчик фарма не запускается.
    game_handler_marker = '''        if await handle_scheduled_route(event.message):
            return
        await engine.process(event.message)
'''
    game_handler_replacement = '''        if await handle_scheduled_route(event.message):
            return
        if state.automation_mode == "guild_only":
            return
        await engine.process(event.message)
'''
    if source.count('if state.automation_mode == "guild_only":') < 2:
        if source.count(game_handler_marker) != 2:
            raise RuntimeError("Could not gate ordinary farming handlers")
        source = source.replace(game_handler_marker, game_handler_replacement, 2)

    MAIN_PATH.write_text(source, encoding="utf-8")


def patch_all() -> None:
    patch_state()
    patch_main()
