"""Identifier value objects for the scheduling domain.

These wrap raw UUIDs to provide strong typing and intent clarity across the
codebase while remaining lightweight and serializable.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkOrderId:
    value: UUID

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TaskId:
    value: UUID

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ResourceId:
    value: UUID

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ScheduleId:
    value: UUID

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


@dataclass(frozen=True, slots=True)
class WorkCellId:
    value: UUID

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)
