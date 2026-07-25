from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parent
ENGINE_PATH = ROOT / "engine.py"


def patch_engine() -> None:
    source = ENGINE_PATH.read_text(encoding="utf-8")

    fishing_import = (
        "from app.routes.fishing import record_fishing_result, select_fishing_action\n"
    )
    old_fishing_import = "from app.routes.fishing import select_fishing_action\n"
    if old_fishing_import in source:
        source = source.replace(old_fishing_import, fishing_import, 1)
    elif fishing_import not in source:
        source = source.replace(
            "from app.routes.farm import select_farm_action\n",
            "from app.routes.farm import select_farm_action\n" + fishing_import,
            1,
        )

    fishing_block = '''            # Рыбалка полностью изолирована от фарма, событий и расписания.
            if getattr(self.state, "automation_mode", "") == "fishing":
                record_fishing_result(message_text, self.state)
                selected, selected_kind = select_fishing_action(
                    message_text,
                    all_buttons,
                    self.state,
                )
                if selected is None:
                    logger.info(
                        "Fishing waiting. kind=%s buttons=%s text=%s",
                        selected_kind,
                        [text for text, _, _ in all_buttons],
                        message_text,
                    )
                    self.state.last_signature = signature
                    return False

'''
    old_fishing_block_with_stats = '''            # Рыбалка полностью изолирована от фарма, событий и расписания.
            if getattr(self.state, "automation_mode", "") == "fishing":
                record_fishing_result(message_text, self.state)
                selected, selected_kind = select_fishing_action(
                    message_text,
                    all_buttons,
                )
                if selected is None:
                    logger.info(
                        "Fishing waiting. kind=%s buttons=%s text=%s",
                        selected_kind,
                        [text for text, _, _ in all_buttons],
                        message_text,
                    )
                    self.state.last_signature = signature
                    return False

'''
    old_fishing_block = '''            # Рыбалка полностью изолирована от фарма, событий и расписания.
            if getattr(self.state, "automation_mode", "") == "fishing":
                selected, selected_kind = select_fishing_action(
                    message_text,
                    all_buttons,
                )
                if selected is None:
                    logger.info(
                        "Fishing waiting. kind=%s buttons=%s text=%s",
                        selected_kind,
                        [text for text, _, _ in all_buttons],
                        message_text,
                    )
                    self.state.last_signature = signature
                    return False

'''
    semi_auto_anchor = "            # Полуавтоматический режим полностью изолирован от обычных правил.\n"
    if old_fishing_block_with_stats in source:
        source = source.replace(old_fishing_block_with_stats, fishing_block, 1)
    elif old_fishing_block in source:
        source = source.replace(old_fishing_block, fishing_block, 1)
    elif "Fishing waiting. kind=%s" not in source and semi_auto_anchor in source:
        source = source.replace(
            semi_auto_anchor,
            fishing_block + semi_auto_anchor,
            1,
        )

    old_locations_guard = '''            if (
                button_text.startswith("локации") or " локации" in button_text
            ) and selected_kind != "repair_step":'''
    new_locations_guard = '''            if (
                button_text.startswith("локации") or " локации" in button_text
            ) and selected_kind not in ("repair_step", "fishing_navigation"):'''
    source = source.replace(old_locations_guard, new_locations_guard, 1)

    ENGINE_PATH.write_text(source, encoding="utf-8")


def patch_all() -> None:
    patch_engine()