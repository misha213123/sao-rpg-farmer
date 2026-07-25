from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.routes.common import message_buttons, normalize_text


@dataclass(frozen=True, slots=True)
class ButtonTarget:
    text: str
    row: int
    column: int


def find_button(message, markers: Iterable[str]) -> ButtonTarget | None:
    """Find the first button containing all normalized markers."""
    normalized_markers = tuple(normalize_text(marker) for marker in markers)
    for text, row, column in message_buttons(message):
        if all(marker in text for marker in normalized_markers):
            return ButtonTarget(text=text, row=row, column=column)
    return None


def has_text(message, *markers: str) -> bool:
    """Return True when normalized message text contains every marker."""
    text = normalize_text(getattr(message, "raw_text", ""))
    return all(normalize_text(marker) in text for marker in markers)
