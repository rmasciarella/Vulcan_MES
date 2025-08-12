"""
CQRS (Command Query Responsibility Segregation) implementation for scheduling domain.

Separates read and write operations to optimize performance and scalability.
Commands modify state while queries provide optimized read views.
"""

from .commands import (
    ScheduleTaskCommand,
    RescheduleTaskCommand,
    AssignResourceCommand,
    OptimizeScheduleCommand
)
from .queries import (
    GetMachineUtilizationQuery,
    GetOperatorWorkloadQuery,
    GetJobFlowMetricsQuery,
    GetDashboardSummaryQuery
)
from .handlers import (
    CommandBus,
    QueryBus,
    SchedulingCommandHandler,
    SchedulingQueryHandler
)
from .events import (
    SchedulingDomainEventHandler,
    ReadModelProjectionUpdater
)

__all__ = [
    "ScheduleTaskCommand",
    "RescheduleTaskCommand", 
    "AssignResourceCommand",
    "OptimizeScheduleCommand",
    "GetMachineUtilizationQuery",
    "GetOperatorWorkloadQuery",
    "GetJobFlowMetricsQuery", 
    "GetDashboardSummaryQuery",
    "CommandBus",
    "QueryBus",
    "SchedulingCommandHandler",
    "SchedulingQueryHandler",
    "SchedulingDomainEventHandler",
    "ReadModelProjectionUpdater",
]