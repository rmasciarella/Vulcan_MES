"""TimeSlot value object.

A lightweight wrapper over the existing TimeWindow value object to provide the
ubiquitous language term "TimeSlot" used by planners and UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .time_window import TimeWindow


@dataclass(frozen=True)
class TimeSlot:
    start: datetime
    end: datetime

    @classmethod
    def from_window(cls, window: TimeWindow) -> "TimeSlot":
        return cls(start=window.start, end=window.end)

    def to_window(self) -> TimeWindow:
        return TimeWindow(start=self.start, end=self.end)
