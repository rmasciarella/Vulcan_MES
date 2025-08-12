"""Repository aliases to match ubiquitous language across domains."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Union
from uuid import UUID

from ..entities.machine import Machine
from ..entities.operator import Operator
from .domain_repositories import JobRepository as WorkOrderRepository

ResourceEntity = Union[Machine, Operator]


class ResourceRepository(ABC):
    """Common repository contract for resource lookups across types."""

    @abstractmethod
    def find_by_id(self, resource_id: UUID) -> ResourceEntity | None: ...

    @abstractmethod
    def find_all(self) -> Iterable[ResourceEntity]: ...
