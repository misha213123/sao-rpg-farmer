from __future__ import annotations

import pathlib
import re
import runpy


ROOT = pathlib.Path(__file__).resolve().parent
MAIN_PATH = ROOT / "main.py"
ENGINE_PATH = ROOT / "engine.py"


def patch_main() -> None:
    source = MAIN_PATH.read_text(encoding="utf-8")

    source = source.replace(":07 —", ":30 —")
    source = source.replace(":10 —", ":32 —")
    source = source.replace("at :07 MSK", "at :30 MSK")
    source = source.replace("at :10 MSK", "at :32 MSK")
    source = source.replace("и :10 ничего", "и :32 ничего")
    source = source.replace("waiting for :10 MSK", "waiting for :32 MSK")
    source = source.replace("now_moscow.minute == 7", "now_moscow.minute == 30")
    source = source.replace("now_moscow.minute >= 10", "now_moscow.minute >= 32")

    replacement = '''                if state.scheduled_step == 6:
                    zero_attacks = (
                        "осталось атак в этом часе: 0" in message_text
                        or "осталось атак в этом часе 0" in message_text
                        or "осталось в этом часе 0 атак" in message_text
                        or "осталось 0 атак" in message_text
                        or ("0 атак" in message_text and "остал" in message_text)
                    )
                    if zero_attacks:
                        logger.info("Guild attacks exhausted; waiting for :32 MSK")
                        state.scheduled_phase = "wait_arena"
                        state.scheduled_step = 0
                        state.last_signature = None
                        return True

                    # После победы игра показывает «Ещё раз: Agrognomiki».
                    # Считаем завершённый бой именно здесь и запускаем следующий.
                    repeated = await click_matching(message, ("ещё раз", "agrognomiki"))
                    if not repeated:
                        repeated = await click_matching(message, ("еще раз", "agrognomiki"))
                    if repeated:
                        state.scheduled_confirm_clicks += 1
                        state.last_signature = None
                        logger.info(
                            "Guild battle completed: %s/10",
                            state.scheduled_confirm_clicks,
                        )
                        if state.scheduled_confirm_clicks >= 10:
                            logger.info("Ten guild battles completed; waiting for :32 MSK")
                            state.scheduled_phase = "wait_arena"
                            state.scheduled_step = 0
                        return True

                    # На экране выбранной цели подтверждаем новую атаку.
                    if await click_matching(message, ("подтвердить атаку",)):
                        state.last_signature = None
                        return True

                    # Внутри каждого боя используем боевой приоритет.
                    for combat_markers in (
                        ("скрытая атака",),
                        ("удар 2 рук",),
                        ("обычная атака",),
                    ):
                        if await click_matching(message, combat_markers):
                            state.last_signature = None
                            return True

                    # Промежуточные экраны после боя.
                    for marker in ("продолжить", "вернуться"):
                        if await click_matching(message, (marker,)):
                            state.last_signature = None
                            return True

                    logger.info(
                        "Waiting for guild target/confirm/combat/0 attacks; buttons=%s text=%s",
                        texts,
                        message_text,
                    )
                    return True

'''

    pattern = re.compile(
        r"                if state\.scheduled_step == 6:\n.*?\n            if state\.scheduled_phase == \"arena\":",
        re.DOTALL,
    )
    source, count = pattern.subn(
        replacement + '            if state.scheduled_phase == "arena":',
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not patch guild route block in app/main.py")

    MAIN_PATH.write_text(source, encoding="utf-8")


def patch_engine() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")
    old = '''                    self.state.return_to_floor_mode = self.state.target_floor is not None
                    logger.info(
                        "Equipment repair completed; returning to floor %s",
                        self.state.target_floor,
                    )'''
    new = '''                    self.state.return_to_floor_mode = self.state.target_floor is not None
                    # После второго «Починить всё» обязательно открываем главное меню,
                    # затем обычная навигация вернёт персонажа на сохранённый этаж.
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
