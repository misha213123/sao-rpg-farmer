from __future__ import annotations

import pathlib
import re
import runpy


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    arena_import = (
        "from app.routes.arena import ARENA_MAX_BATTLES, "
        "select_battle_button, should_finish_arena\n"
    )
    if "from app.routes.arena import" not in source:
        source = source.replace(
            "from app.engine import FarmerEngine\n",
            "from app.engine import FarmerEngine\n" + arena_import,
            1,
        )

    guild_import = '''from app.routes.guild import (
    GUILD_MAX_BATTLES,
    GUILD_ROUTE_STEPS,
    select_combat_button,
    select_confirm_button,
    select_repeat_button,
    select_route_button,
    should_finish_guild,
)
'''
    if "from app.routes.guild import" not in source:
        anchor = arena_import if arena_import in source else "from app.engine import FarmerEngine\n"
        source = source.replace(anchor, anchor + guild_import, 1)

    source = source.replace(":07 —", ":04 —")
    source = source.replace(":10 —", ":02 —")
    source = source.replace("at :07 MSK", "at :04 MSK")
    source = source.replace("at :10 MSK", "at :02 MSK")
    source = source.replace("и :10 ничего", "и :02 ничего")
    source = source.replace("waiting for :10 MSK", "waiting for :02 MSK")
    source = source.replace("now_moscow.minute == 7", "now_moscow.minute == 4")
    source = source.replace("now_moscow.minute >= 10", "now_moscow.minute >= 2")

    source = source.replace(
        '''def normalize(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())''',
        '''def normalize(value: str | None) -> str:
    cleaned = re.sub(r"[^a-zа-яё0-9/]+", " ", (value or "").lower())
    return " ".join(cleaned.split())''',
        1,
    )

    guild_steps_replacement = '''                if state.scheduled_step in GUILD_ROUTE_STEPS:
                    route_button = select_route_button(buttons, state.scheduled_step)
                    if route_button is not None:
                        button_text, row, column = route_button
                        await asyncio.sleep(1.0)
                        await message.click(i=row, j=column)
                        logger.info(
                            "Guild route clicked: %s (step=%s)",
                            button_text,
                            state.scheduled_step,
                        )
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

'''
    if "select_route_button(buttons" not in source:
        guild_steps_pattern = re.compile(
            r"                route_steps: dict\[int, tuple\[str, \.\.\.\]\] = \{.*?"
            r"                    return True\n\n"
            r"                if state\.scheduled_step == 6:",
            re.DOTALL,
        )
        source = guild_steps_pattern.sub(
            guild_steps_replacement + "                if state.scheduled_step == 6:",
            source,
            count=1,
        )

    guild_replacement = '''                if state.scheduled_step == 6:
                    if should_finish_guild(
                        message_text,
                        state.scheduled_confirm_clicks,
                    ):
                        logger.info(
                            "Guild completed or exhausted at %s/%s; sending /start and returning to farming",
                            state.scheduled_confirm_clicks,
                            GUILD_MAX_BATTLES,
                        )
                        state.scheduled_mode = False
                        state.scheduled_phase = ""
                        state.scheduled_step = 0
                        state.return_to_floor_mode = state.target_floor is not None
                        state.last_signature = None
                        await client.send_message(game_bot, "/start")
                        return True

                    if state.scheduled_confirm_clicks == 0:
                        confirm_button = select_confirm_button(buttons)
                        if confirm_button is not None:
                            button_text, row, column = confirm_button
                            await asyncio.sleep(1.0)
                            await message.click(i=row, j=column)
                            state.scheduled_confirm_clicks = 1
                            state.last_signature = None
                            logger.info(
                                "Initial guild battle started: 1/%s (button=%s)",
                                GUILD_MAX_BATTLES,
                                button_text,
                            )
                            return True

                    combat_button = select_combat_button(buttons)
                    if combat_button is not None:
                        button_text, row, column = combat_button
                        await asyncio.sleep(1.0)
                        await message.click(i=row, j=column)
                        state.last_signature = None
                        logger.info("Guild combat action: %s", button_text)
                        return True

                    if state.scheduled_confirm_clicks < GUILD_MAX_BATTLES:
                        repeat_button = select_repeat_button(buttons)
                        if repeat_button is not None:
                            button_text, row, column = repeat_button
                            await asyncio.sleep(1.0)
                            await message.click(i=row, j=column)
                            state.scheduled_confirm_clicks += 1
                            state.last_signature = None
                            logger.info(
                                "Guild battle started: %s/%s (button=%s)",
                                state.scheduled_confirm_clicks,
                                GUILD_MAX_BATTLES,
                                button_text,
                            )
                            return True

                    logger.info(
                        "Waiting for guild combat/repeat/exhaustion (%s/%s); buttons=%s text=%s",
                        state.scheduled_confirm_clicks,
                        GUILD_MAX_BATTLES,
                        texts,
                        message_text,
                    )
                    return True

'''
    if "select_confirm_button(buttons)" not in source:
        guild_pattern = re.compile(
            r"                if state\.scheduled_step == 6:\n.*?\n            if state\.scheduled_phase == \"arena\":",
            re.DOTALL,
        )
        source = guild_pattern.sub(
            guild_replacement + '            if state.scheduled_phase == "arena":',
            source,
            count=1,
        )

    arena_replacement = '''                if state.scheduled_step == 2:
                    if should_finish_arena(
                        message_text,
                        state.scheduled_arena_clicks,
                    ):
                        await finish_arena_route()
                        return True

                    battle_button = select_battle_button(
                        buttons,
                        state.scheduled_arena_clicks,
                    )
                    if battle_button is not None:
                        button_text, row, column = battle_button
                        await asyncio.sleep(1.0)
                        await message.click(i=row, j=column)
                        state.scheduled_arena_clicks += 1
                        state.last_signature = None
                        logger.info(
                            "Arena battle started: %s/%s (button=%s)",
                            state.scheduled_arena_clicks,
                            ARENA_MAX_BATTLES,
                            button_text,
                        )
                        return True

                    logger.info(
                        "Waiting for arena battle button (%s/%s); buttons=%s text=%s",
                        state.scheduled_arena_clicks,
                        ARENA_MAX_BATTLES,
                        texts,
                        message_text,
                    )
                    return True

'''
    if "select_battle_button(" not in source:
        arena_pattern = re.compile(
            r"                if state\.scheduled_step == 2:\n.*?\n            logger\.warning\(",
            re.DOTALL,
        )
        source = arena_pattern.sub(
            arena_replacement + "            logger.warning(",
            source,
            count=1,
        )

    source = source.replace(
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 2
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase == "wait_arena"
                ):
                    await start_arena_route(hour_key)''',
        '''                if (
                    state.enabled
                    and now_moscow.minute >= 2
                    and state.scheduled_last_arena_hour != hour_key
                    and state.scheduled_phase != "arena"
                ):
                    await start_arena_route(hour_key)''',
    )

    source = source.replace(
        '@client.on(events.NewMessage(chats="me", outgoing=True))',
        '@client.on(events.NewMessage())',
        1,
    )
    source = source.replace(
        '@client.on(events.NewMessage(outgoing=True))',
        '@client.on(events.NewMessage())',
        1,
    )

    plain_handler = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        raw = (event.raw_text or "").strip()'''
    robust_handler = '''    async def on_saved_message(event: events.NewMessage.Event) -> None:
        event_chat_id = getattr(event, "chat_id", None)
        sender_id = getattr(event, "sender_id", None)
        peer_id = getattr(event.message, "peer_id", None)
        peer_user_id = getattr(peer_id, "user_id", None)
        is_saved_messages = event_chat_id == me.id or peer_user_id == me.id
        is_own_message = sender_id == me.id or getattr(event.message, "out", False)
        if not is_saved_messages or not is_own_message:
            return
        raw = (event.raw_text or "").strip()
        logger.info("Saved Messages input received: %r", raw)'''
    if "Saved Messages input received" not in source:
        source = source.replace(plain_handler, robust_handler, 1)

    MAIN_PATH.write_text(source, encoding="utf-8")


patch_main()

from app.mode_selection_patch import patch_all

patch_all()
runpy.run_module("app.main", run_name="__main__")
