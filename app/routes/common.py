from __future__ import annotations

import re
from typing import Any


def normalize_text(value: str | None) -> str:
    """Normalize game text while ignoring emoji and decorative symbols."""
    cleaned = re.sub(r"[^a-zа-яё0-9/]+", " ", (value or "").lower())
    return " ".join(cleaned.split())


def message_buttons(message: Any) -> list[tuple[str, int, int]]:
    """Return normalized button text together with row and column indexes."""
    result: list[tuple[str, int, int]] = []
    rows = getattr(message, "buttons", None)
    if not rows:
        return result

    for row_index, row in enumerate(rows):
        for column_index, button in enumerate(row):
            result.append(
                (
                    normalize_text(getattr(button, "text", "")),
                    row_index,
                    column_index,
                )
            )
    return result


def parse_floor(value: str) -> int | None:
    """Extract a positive floor number from a command or plain message."""
    match = re.search(r"\d+", value)
    if not match:
        return None
    floor = int(match.group())
    return floor if floor > 0 else None


def parse_plain_floor(value: str) -> int | None:
    """Parse a floor only when the whole message is a positive integer."""
    stripped = value.strip()
    if not stripped.isdigit():
        return None
    floor = int(stripped)
    return floor if floor > 0 else None
