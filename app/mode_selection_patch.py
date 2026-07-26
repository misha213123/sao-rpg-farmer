from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
STATE_PATH = ROOT / "state.py"
ENGINE_PATH = ROOT / "engine.py"


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


def patch_engine() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")
    old_call = '''                selected, selected_kind = select_farm_action(
                    buttons,
                    self.state.target_floor,
                )'''
    new_call = '''                selected, selected_kind = select_farm_action(
                    buttons,
                    self.state.target_floor,
                    self.state.target_location,
                )'''
    source = source.replace(old_call, new_call, 1)
    ENGINE_PATH.write_text(source, encoding="utf-8")


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    if "def parse_floor_location(" not in source:
        marker = '''def parse_plain_floor(value: str) -> int | None:
    value = value.strip()
    if not value.isdigit():
        return None
    floor = int(value)
    return floor if floor > 0 else None
'''
        replacement = marker + '''

def parse_floor_location(value: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"\\s*(\\d+)\\.(\\d+)\\s*", value)
    if not match:
        return None
    floor = int(match.group(1))
    location = int(match.group(2))
    if floor <= 0 or not 1 <= location <= 7:
        return None
    return floor, location
'''
        source = source.replace(marker, replacement, 1)

    startup_off_old = '''        if command == "/off":
            restored_enabled = False
            pending_floor = False
            continue
'''
    startup_off_new = '''        if command == "/off":
            restored_enabled = False
            pending_floor = False
            state.target_floor = None
            state.target_location = None
            continue
'''
    source = source.replace(startup_off_old, startup_off_new, 1)
    source = source.replace(
        '''        if command == "/start" and state.target_floor is not None:
            restored_enabled = True
''',
        "",
        1,
    )

    old_pending_restore = '''        if pending_floor:
            floor = parse_plain_floor(raw)
            if floor is not None:
                state.target_floor = floor
                restored_enabled = True
                pending_floor = False
            continue
'''
    new_pending_restore = '''        if pending_floor:
            selection = parse_floor_location(raw)
            if selection is not None:
                state.target_floor, state.target_location = selection
                restored_enabled = True
                pending_floor = False
            continue
'''
    source = source.replace(old_pending_restore, new_pending_restore, 1)

    source = source.replace(
        '@client.on(events.NewMessage(chats="me", outgoing=True))',
        '@client.on(events.NewMessage(outgoing=True))',
        1,
    )

    native_saved_handler_header = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()'''
    guarded_saved_handler_header = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        event_chat_id = getattr(event, "chat_id", None)
        peer_id = getattr(event.message, "peer_id", None)
        peer_user_id = getattr(peer_id, "user_id", None)
        if event_chat_id != me.id and peer_user_id != me.id:
            return
        raw = (event.raw_text or "").strip()'''
    if guarded_saved_handler_header not in source:
        source = source.replace(
            native_saved_handler_header,
            guarded_saved_handler_header,
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
                "4": "semi_auto",
                "полуавтоматический фарм": "semi_auto",
                "полуавтомат": "semi_auto",
                "5": "fishing",
                "рыбалка": "fishing",
            }
            selected_mode = mode_by_choice.get(choice)
            if selected_mode is None:
                await event.reply(
                    "Выбери режим цифрой:\\n"
                    "1 — Обычный фарм\\n"
                    "2 — Обычный фарм + Арена + Гильдейский зачёт\\n"
                    "3 — Только Арена + Гильдейский зачёт\\n"
                    "4 — Полуавтоматический фарм\\n"
                    "5 — Рыбалка"
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

            if selected_mode == "fishing":
                state.enabled = True
                state.awaiting_floor = False
                state.target_floor = None
                state.target_location = None
                state.return_to_floor_mode = False
                state.repair_mode = False
                await event.reply(
                    "Режим включён: Рыбалка 🎣\\n"
                    "Перехожу: /start → Локации → Рыбалка → Забросить удочку."
                )
                await client.send_message(game_bot, "/start")
                return

            state.enabled = False
            state.awaiting_floor = True
            state.return_to_floor_mode = False
            if selected_mode == "farm":
                mode_name = "Обычный фарм"
            elif selected_mode == "full":
                mode_name = "Обычный фарм + Арена + Гильдейский зачёт"
            else:
                mode_name = "Полуавтоматический фарм"
            await event.reply(
                f"Выбран режим: {mode_name}\\n"
                "Напиши этаж и локацию в формате ЭТАЖ.ЛОКАЦИЯ, например: 14.1\\n"
                "Локация должна быть от 1 до 7."
            )
            return

'''
    if "mode_by_choice =" not in source and awaiting_floor_marker in source:
        source = source.replace(
            awaiting_floor_marker,
            mode_block + awaiting_floor_marker,
            1,
        )

    old_awaiting = '''        if state.awaiting_floor and not command.startswith("/"):
            floor = parse_plain_floor(raw)
            if floor is None:
                await event.reply("Напиши номер этажа цифрами, например: 25")
                return
            await activate_floor(floor, event)
            return
'''
    new_awaiting = '''        if state.awaiting_floor and not command.startswith("/"):
            selection = parse_floor_location(raw)
            if selection is None:
                await event.reply(
                    "Напиши этаж и локацию в формате ЭТАЖ.ЛОКАЦИЯ, например: 14.1\\n"
                    "Локация должна быть от 1 до 7."
                )
                return
            floor, location = selection
            await activate_floor(floor, event, location)
            return
'''
    source = source.replace(old_awaiting, new_awaiting, 1)

    source = source.replace(
        '    async def activate_floor(floor: int, event: events.NewMessage.Event) -> None:',
        '    async def activate_floor(\n        floor: int,\n        event: events.NewMessage.Event,\n        location: int | None = None,\n    ) -> None:',
        1,
    )
    activate_marker = '''        state.target_floor = floor
        state.awaiting_floor = False
        state.enabled = True
'''
    activate_replacement = '''        state.target_floor = floor
        state.target_location = location or state.target_location or 1
        state.awaiting_floor = False
        state.enabled = True
        if state.automation_mode not in ("farm", "full", "semi_auto"):
            state.automation_mode = "farm"
        logger.info(
            "Floor/location selected from Saved Messages: %s.%s",
            floor,
            state.target_location,
        )
'''
    if "Floor/location selected from Saved Messages" not in source:
        source = source.replace(activate_marker, activate_replacement, 1)

    source = source.replace(
        'f"Автоматизация включена ✅\\nВыбран этаж: {floor}\\n"',
        'f"Автоматизация включена ✅\\nЭтаж: {floor}\\nЛокация: {state.target_location}\\n"',
        1,
    )
    source = source.replace(
        "Перехожу: Главное меню → Исследовать → этаж → последняя Локация → Начать/Продолжить исследование.",
        "Перехожу: Главное меню → Исследовать → этаж → выбранная локация → Начать/Продолжить исследование.",
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
                "3 — Только Арена + Гильдейский зачёт\\n"
                "4 — Полуавтоматический фарм\\n"
                "5 — Рыбалка\\n\\n"
                "Ответь цифрой: 1, 2, 3, 4 или 5"
            )
'''
    source = on_pattern.sub(lambda _match: on_replacement, source, count=1)

    off_marker = '''        elif command == "/off":
            state.enabled = False
'''
    off_replacement = '''        elif command == "/off":
            logger.info("Saved command received: /off")
            state.enabled = False
            state.awaiting_mode = False
            state.awaiting_floor = False
            state.automation_mode = "off"
            state.target_floor = None
            state.target_location = None
            state.return_to_floor_mode = False
            state.return_to_floor_step = 0
            state.repair_mode = False
            state.repair_step = 0
            state.stamina_mode = False
            state.stamina_step = 0
            state.stamina_route = ""
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.last_signature = None
'''
    if "Saved command received: /off" not in source:
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
    patch_engine()
    patch_main()

    from app.fishing_patch import patch_all as patch_fishing
    from app.random_schedule_patch import patch_all as patch_random_schedule

    patch_fishing()
    patch_random_schedule()
