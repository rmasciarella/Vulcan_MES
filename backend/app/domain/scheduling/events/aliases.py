"""Event aliases and additional domain events for ubiquitous language alignment."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .domain_events import (
    JobCreated,
    MachineAllocated,
    OperatorAssigned,
)

# Ubiquitous-language aligned aliases
WorkOrderCreated = JobCreated


@dataclass(frozen=True)
class ResourceAssigned:
    """Unified event fired when a resource (machine or operator) is assigned.

    This complements MachineAllocated and OperatorAssigned by providing a single
    event that UI/event consumers can subscribe to without caring about the
    specific resource type.
    """

    resource_type: str  # 'machine' | 'operator'
    resource_id: UUID
    task_id: UUID
    job_id: UUID | None = None
    start: datetime | None = None
    end: datetime | None = None
