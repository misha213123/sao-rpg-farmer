from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
STATE_PATH = ROOT / "state.py"


def patch_state() -> None:
    source = STATE_PATH.read_text(encoding="utf-8")

    if "awaiting_mode:" not in source:
        source = source.replace(
            "    awaiting_floor: bool = False\n",
            "    awaiting_floor: bool = False\n"
            "    awaiting_mode: bool = False\n"
            "    automation_mode: str = \"off\"\n",
            1,
        )

    STATE_PATH.write_text(source, encoding="utf-8")


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    source = source.replace(
        '@client.on(events.NewMessage(outgoing=True))',
        '@client.on(events.NewMessage(chats="me", outgoing=True))',
        1,
    )

    saved_handler_header = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        event_chat_id = getattr(event, "chat_id", None)
        peer_id = getattr(event.message, "peer_id", None)
        peer_user_id = getattr(peer_id, "user_id", None)
        if event_chat_id != me.id and peer_user_id != me.id:
            return
        raw = (event.raw_text or "").strip()'''
    native_saved_handler_header = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()'''
    source = source.replace(
        saved_handler_header,
        native_saved_handler_header,
        1,
    )

    awaiting_floor_marker = '        if state.awaiting_floor and not command.startswith("/"):\n'
    mode_block = '''        if state.awaiting_mode and not command.startswith("/"):
            choice = command.strip()
            mode_by_choice = {
                "1": "farm",
                "обычный фарм": "farm",
                "2": "full",
                "обычный фарм арена и гильдейский зачет": "full",
                "обычный фарм арена и гильдейский зачёт": "full",
                "3": "scheduled_only",
                "арена и гильдейский зачет": "scheduled_only",
                "арена и гильдейский зачёт": "scheduled_only",
                "только арена и гильдейский зачет": "scheduled_only",
                "только арена и гильдейский зачёт": "scheduled_only",
            }
            selected_mode = mode_by_choice.get(choice)
            if selected_mode is None:
                await event.reply(
                    "Выбери режим цифрой:\\n"
                    "1 — Обычный фарм\\n"
                    "2 — Обычный фарм + Арена + Гильдейский зачёт\\n"
                    "3 — Только Арена + Гильдейский зачёт"
                )
                return

            logger.info("Mode selected from Saved Messages: %s", selected_mode)
            state.awaiting_mode = False
            state.automation_mode = selected_mode
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.last_signature = None

            if selected_mode == "scheduled_only":
                state.enabled = True
                state.awaiting_floor = False
                state.return_to_floor_mode = False
                await event.reply(
                    "Режим включён: Арена + Гильдейский зачёт ✅\\n"
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
                f"Выбран режим: {mode_name}\\n"
                "На каком этаже фармить? Напиши только номер, например: 25"
            )
            return

'''
    if "mode_by_choice =" not in source and awaiting_floor_marker in source:
        source = source.replace(
            awaiting_floor_marker,
            mode_block + awaiting_floor_marker,
            1,
        )

    on_pattern = re.compile(
        r'        elif command == "/on":\n.*?(?=        elif command\.startswith\("/floor"\):)',
        re.DOTALL,
    )
    on_replacement = '''        elif command == "/on":
            logger.info("Saved command received: /on")
            state.enabled = False
            state.awaiting_mode = True
            state.awaiting_floor = False
            state.return_to_floor_mode = False
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.last_signature = None
            await event.reply(
                "Что запустить?\\n"
                "1 — Обычный фарм\\n"
                "2 — Обычный фарм + Арена + Гильдейский зачёт\\n"
                "3 — Только Арена + Гильдейский зачёт\\n\\n"
                "Ответь цифрой: 1, 2 или 3"
            )
'''
    # Важно: lambda не даёт re.sub интерпретировать \\n внутри
    # сгенерированного Python-кода как реальные переносы строк.
    source = on_pattern.sub(lambda _: on_replacement, source, count=1)

    activate_marker = '''        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
'''
    activate_replacement = '''        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
        if state.automation_mode not in ("farm", "full"):
            state.automation_mode = "farm"
        logger.info("Floor selected from Saved Messages: %s", floor)
'''
    if "Floor selected from Saved Messages" not in source and activate_marker in source:
        source = source.replace(activate_marker, activate_replacement, 1)

    off_marker = '''        elif command == "/off":
            state.enabled = False
'''
    off_replacement = '''        elif command == "/off":
            logger.info("Saved command received: /off")
            state.enabled = False
            state.awaiting_mode = False
            state.automation_mode = "off"
'''
    if "Saved command received: /off" not in source and off_marker in source:
        source = source.replace(off_marker, off_replacement, 1)

    guild_condition = re.compile(
        r'(\s+state\.enabled\n)(\s+and now_moscow\.minute == 4\n)'
    )
    source = guild_condition.sub(
        r'\1                    and state.automation_mode in ("full", "scheduled_only")\n\2',
        source,
        count=1,
    )

    arena_condition = re.compile(
        r'(\s+state\.enabled\n)(\s+and now_moscow\.minute >= 2\n)'
    )
    source = arena_condition.sub(
        r'\1                    and state.automation_mode in ("full", "scheduled_only")\n\2',
        source,
        count=1,
    )

    game_handler = '''        if await handle_scheduled_route(event.message):
            return
        await engine.process(event.message)
'''
    scheduled_only_handler = '''        if await handle_scheduled_route(event.message):
            return
        if state.automation_mode == "scheduled_only":
            return
        await engine.process(event.message)
'''
    if source.count('if state.automation_mode == "scheduled_only":') < 2:
        source = source.replace(game_handler, scheduled_only_handler, 2)

    MAIN_PATH.write_text(source, encoding="utf-8")


def patch_all() -> None:
    patch_state()
    patch_main()
