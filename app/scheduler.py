from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import random


@dataclass(frozen=True, slots=True)
class HourlySchedule:
    """One stable schedule for a single Moscow-time hour."""

    hour_key: str
    guild_minute: int
    arena_minute: int

    @classmethod
    def create(cls, now_moscow: datetime) -> "HourlySchedule":
        return cls(
            hour_key=now_moscow.strftime("%Y-%m-%d-%H"),
            guild_minute=random.randint(1, 5),
            arena_minute=random.randint(6, 10),
        )

    def guild_due(self, now_moscow: datetime) -> bool:
        return (
            now_moscow.strftime("%Y-%m-%d-%H") == self.hour_key
            and now_moscow.minute >= self.guild_minute
        )

    def arena_due(self, now_moscow: datetime) -> bool:
        return (
            now_moscow.strftime("%Y-%m-%d-%H") == self.hour_key
            and now_moscow.minute >= self.arena_minute
        )
