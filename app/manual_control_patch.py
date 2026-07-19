from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
ENGINE_PATH = ROOT / "engine.py"


def patch_engine() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")

    old_navigation = (
        "            if selected is None and not self.state.repair_mode "
        "and self.state.target_floor is not None:\n"
    )
    new_navigation = '''            manual_main_menu = (
                "вы вернулись в главное меню" in message_text
                and not self.state.return_to_floor_mode
            )
            if (
                selected is None
                and not self.state.repair_mode
                and self.state.target_floor is not None
                and not manual_main_menu
            ):
'''
    if "manual_main_menu = (" not in source:
        if old_navigation not in source:
            raise RuntimeError("Could not patch manual main-menu handling")
        source = source.replace(old_navigation, new_navigation, 1)

    old_click = '''            await asyncio.sleep(delay)

            try:
                await message.click(i=row, j=column)'''
    new_click = '''            await asyncio.sleep(delay)

            # /off должен останавливать даже уже запланированный клик.
            if not self.state.enabled:
                logger.info("Click cancelled because automation is disabled")
                return False

            try:
                await message.click(i=row, j=column)'''
    if "Click cancelled because automation is disabled" not in source:
        if old_click not in source:
            raise RuntimeError("Could not patch click cancellation after /off")
        source = source.replace(old_click, new_click, 1)

    ENGINE_PATH.write_text(source, encoding="utf-8")


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    old_off = '''        elif command == "/off":
            state.enabled = False
            state.awaiting_floor = False
            state.repair_mode = False
            state.return_to_floor_mode = False
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            await event.reply("Автоматизация выключена ⛔")'''
    new_off = '''        elif command == "/off":
            state.enabled = False
            state.awaiting_floor = False
            state.repair_mode = False
            state.repair_step = 0
            state.return_to_floor_mode = False
            state.return_to_floor_step = 0
            state.scheduled_mode = False
            state.scheduled_phase = ""
            state.scheduled_step = 0
            state.scheduled_confirm_clicks = 0
            state.scheduled_arena_clicks = 0
            state.last_signature = None
            await event.reply("Автоматизация полностью выключена ⛔")'''
    if "Автоматизация полностью выключена" not in source:
        if old_off not in source:
            raise RuntimeError("Could not patch /off command")
        source = source.replace(old_off, new_off, 1)

    MAIN_PATH.write_text(source, encoding="utf-8")


patch_engine()
patch_main()

from app import start_guard  # noqa: E402,F401
