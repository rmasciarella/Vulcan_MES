"""
Command and Query handlers for scheduling domain CQRS implementation.

Handles command execution (writes) and query processing (reads) with proper
separation of concerns and optimized performance for each operation type.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Type, Callable
from uuid import UUID
import time
import asyncio
from abc import ABC, abstractmethod

from pydantic import BaseModel

from ....shared.exceptions import ValidationError, DomainError, OptimizationError
from ..entities.task import Task
from ..entities.machine import Machine  
from ..entities.operator import Operator
from ..entities.job import Job
from ..repositories.task_repository import TaskRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.job_repository import JobRepository
from ..services.resource_allocation_service import ResourceAllocationService
from ..optimization.optimization_service import SchedulingOptimizationService
from ..read_models.machine_utilization import MachineUtilizationReadModel
from ..read_models.operator_load import OperatorLoadReadModel
from ..read_models.job_flow_metrics import JobFlowMetricsReadModel
from ..read_models.scheduling_dashboard import SchedulingDashboardReadModel

from .commands import (
    Command, CommandResult, 
    ScheduleTaskCommand, RescheduleTaskCommand, AssignResourceCommand,
    OptimizeScheduleCommand, UpdateTaskStatusCommand, HandleResourceDisruptionCommand
)
from .queries import (
    Query, QueryResult,
    GetMachineUtilizationQuery, GetOperatorWorkloadQuery, GetJobFlowMetricsQuery,
    GetDashboardSummaryQuery, GetTaskScheduleQuery, GetResourceAvailabilityQuery
)


class CommandHandler(ABC):
    """Base class for command handlers."""
    
    @abstractmethod
    async def handle(self, command: Command) -> CommandResult:
        """Handle a command and return result."""
        pass
    
    @abstractmethod
    def can_handle(self, command: Command) -> bool:
        """Check if this handler can handle the command."""
        pass


class QueryHandler(ABC):
    """Base class for query handlers."""
    
    @abstractmethod
    async def handle(self, query: Query) -> QueryResult:
        """Handle a query and return result."""
        pass
    
    @abstractmethod
    def can_handle(self, query: Query) -> bool:
        """Check if this handler can handle the query."""
        pass


class CommandBus:
    """Command bus for routing commands to appropriate handlers."""
    
    def __init__(self):
        self.handlers: List[CommandHandler] = []
        self.middleware: List[Callable] = []
    
    def register_handler(self, handler: CommandHandler) -> None:
        """Register a command handler."""
        self.handlers.append(handler)
    
    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware for command processing."""
        self.middleware.append(middleware)
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute a command through the appropriate handler."""
        start_time = time.time()
        
        try:
            # Find handler
            handler = self._find_handler(command)
            if not handler:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message=f"No handler found for command {type(command).__name__}",
                    errors=[f"Unhandled command type: {type(command).__name__}"]
                )
            
            # Apply middleware
            for middleware in self.middleware:
                command = await middleware(command)
            
            # Execute command
            result = await handler.handle(command)
            
            # Update processing time
            processing_time = (time.time() - start_time) * 1000
            result.processing_time_ms = processing_time
            
            return result
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Command execution failed: {str(e)}",
                errors=[str(e)],
                processing_time_ms=processing_time
            )
    
    def _find_handler(self, command: Command) -> Optional[CommandHandler]:
        """Find appropriate handler for command."""
        for handler in self.handlers:
            if handler.can_handle(command):
                return handler
        return None


class QueryBus:
    """Query bus for routing queries to appropriate handlers."""
    
    def __init__(self):
        self.handlers: List[QueryHandler] = []
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: Dict[str, datetime] = {}
    
    def register_handler(self, handler: QueryHandler) -> None:
        """Register a query handler."""
        self.handlers.append(handler)
    
    async def execute(self, query: Query) -> QueryResult:
        """Execute a query through the appropriate handler."""
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = self._get_cache_key(query)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                execution_time = (time.time() - start_time) * 1000
                cached_result.execution_time_ms = execution_time
                cached_result.cache_hit = True
                return cached_result
            
            # Find handler
            handler = self._find_handler(query)
            if not handler:
                return QueryResult(
                    query_id=query.query_id,
                    success=False,
                    errors=[f"No handler found for query {type(query).__name__}"]
                )
            
            # Execute query
            result = await handler.handle(query)
            
            # Cache result if successful
            if result.success and self._should_cache_query(query):
                self._cache_result(cache_key, result)
            
            # Update execution time
            execution_time = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return QueryResult(
                query_id=query.query_id,
                success=False,
                errors=[str(e)],
                execution_time_ms=execution_time
            )
    
    def _find_handler(self, query: Query) -> Optional[QueryHandler]:
        """Find appropriate handler for query."""
        for handler in self.handlers:
            if handler.can_handle(query):
                return handler
        return None
    
    def _get_cache_key(self, query: Query) -> str:
        """Generate cache key for query."""
        # Simple implementation - would use proper serialization
        return f"{type(query).__name__}_{hash(query.json())}"
    
    def _get_cached_result(self, cache_key: str) -> Optional[QueryResult]:
        """Get cached result if still valid."""
        if cache_key in self.cache:
            ttl = self.cache_ttl.get(cache_key)
            if ttl and ttl > datetime.utcnow():
                return self.cache[cache_key]
            else:
                # Remove expired entry
                self.cache.pop(cache_key, None)
                self.cache_ttl.pop(cache_key, None)
        return None
    
    def _cache_result(self, cache_key: str, result: QueryResult, ttl_seconds: int = 300) -> None:
        """Cache query result."""
        self.cache[cache_key] = result
        self.cache_ttl[cache_key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    def _should_cache_query(self, query: Query) -> bool:
        """Determine if query result should be cached."""
        # Cache read-heavy queries
        cacheable_types = [
            GetMachineUtilizationQuery,
            GetOperatorWorkloadQuery, 
            GetJobFlowMetricsQuery,
            GetDashboardSummaryQuery
        ]
        return type(query) in cacheable_types


class SchedulingCommandHandler(CommandHandler):
    """Main command handler for scheduling domain operations."""
    
    def __init__(
        self,
        task_repository: TaskRepository,
        machine_repository: MachineRepository,
        operator_repository: OperatorRepository,
        job_repository: JobRepository,
        resource_allocation_service: ResourceAllocationService,
        optimization_service: SchedulingOptimizationService
    ):
        self.task_repo = task_repository
        self.machine_repo = machine_repository
        self.operator_repo = operator_repository
        self.job_repo = job_repository
        self.resource_service = resource_allocation_service
        self.optimization_service = optimization_service
    
    def can_handle(self, command: Command) -> bool:
        """Check if this handler can process the command."""
        handled_types = [
            ScheduleTaskCommand,
            RescheduleTaskCommand,
            AssignResourceCommand,
            OptimizeScheduleCommand,
            UpdateTaskStatusCommand,
            HandleResourceDisruptionCommand
        ]
        return type(command) in handled_types
    
    async def handle(self, command: Command) -> CommandResult:
        """Handle scheduling commands."""
        if isinstance(command, ScheduleTaskCommand):
            return await self._handle_schedule_task(command)
        elif isinstance(command, RescheduleTaskCommand):
            return await self._handle_reschedule_task(command)
        elif isinstance(command, AssignResourceCommand):
            return await self._handle_assign_resource(command)
        elif isinstance(command, OptimizeScheduleCommand):
            return await self._handle_optimize_schedule(command)
        elif isinstance(command, UpdateTaskStatusCommand):
            return await self._handle_update_task_status(command)
        elif isinstance(command, HandleResourceDisruptionCommand):
            return await self._handle_resource_disruption(command)
        else:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Command type {type(command).__name__} not supported"
            )
    
    async def _handle_schedule_task(self, command: ScheduleTaskCommand) -> CommandResult:
        """Handle task scheduling command."""
        try:
            # Load task
            task = await self.task_repo.get_by_id(command.task_id)
            if not task:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message=f"Task {command.task_id} not found",
                    errors=["TASK_NOT_FOUND"]
                )
            
            # Validate time window
            if command.start_time >= command.end_time:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message="Start time must be before end time",
                    errors=["INVALID_TIME_WINDOW"]
                )
            
            # Check resource availability if not forced
            if not command.force_assignment:
                # Validate machine availability
                if command.machine_id:
                    machine = await self.machine_repo.get_by_id(command.machine_id)
                    if not machine or not machine.is_available:
                        return CommandResult(
                            command_id=command.command_id,
                            success=False,
                            message=f"Machine {command.machine_id} not available",
                            errors=["MACHINE_UNAVAILABLE"]
                        )
                
                # Validate operator availability
                for operator_id in command.operator_ids:
                    operator = await self.operator_repo.get_by_id(operator_id)
                    if not operator or not operator.is_available_for_work:
                        return CommandResult(
                            command_id=command.command_id,
                            success=False,
                            message=f"Operator {operator_id} not available",
                            errors=["OPERATOR_UNAVAILABLE"]
                        )
            
            # Schedule the task
            task.schedule(
                start_time=command.start_time,
                end_time=command.end_time,
                machine_id=command.machine_id
            )
            
            # Add operator assignments
            for operator_id in command.operator_ids:
                # This would create proper operator assignment
                pass
            
            # Save task
            await self.task_repo.update(task)
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Task {command.task_id} scheduled successfully",
                data={
                    "task_id": str(command.task_id),
                    "start_time": command.start_time.isoformat(),
                    "end_time": command.end_time.isoformat(),
                    "machine_id": str(command.machine_id) if command.machine_id else None,
                    "operator_count": len(command.operator_ids)
                },
                events_generated=1
            )
            
        except DomainError as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Domain validation failed: {str(e)}",
                errors=[str(e)]
            )
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Unexpected error scheduling task: {str(e)}",
                errors=[str(e)]
            )
    
    async def _handle_reschedule_task(self, command: RescheduleTaskCommand) -> CommandResult:
        """Handle task rescheduling command."""
        try:
            task = await self.task_repo.get_by_id(command.task_id)
            if not task:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message=f"Task {command.task_id} not found"
                )
            
            # Reschedule task
            task.reschedule(
                new_start=command.new_start_time,
                new_end=command.new_end_time,
                reason=command.reason
            )
            
            # Update resource assignments if specified
            if command.new_machine_id:
                task.assigned_machine_id = command.new_machine_id
            
            await self.task_repo.update(task)
            
            # Handle cascading dependencies if requested
            events_generated = 1
            cascaded_tasks = []
            
            if command.cascade_dependencies:
                # Find dependent tasks and reschedule them
                dependent_tasks = await self.task_repo.get_tasks_dependent_on(command.task_id)
                for dependent_task in dependent_tasks:
                    # Reschedule dependent task with appropriate delay
                    delay = command.new_start_time - task.planned_start_time if task.planned_start_time else timedelta(0)
                    if dependent_task.planned_start_time:
                        new_start = dependent_task.planned_start_time + delay
                        new_end = dependent_task.planned_end_time + delay if dependent_task.planned_end_time else new_start + timedelta(hours=1)
                        
                        dependent_task.reschedule(new_start, new_end, f"Cascaded from {command.task_id}")
                        await self.task_repo.update(dependent_task)
                        cascaded_tasks.append(str(dependent_task.id))
                        events_generated += 1
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Task {command.task_id} rescheduled successfully",
                data={
                    "task_id": str(command.task_id),
                    "new_start_time": command.new_start_time.isoformat(),
                    "new_end_time": command.new_end_time.isoformat(),
                    "cascaded_tasks": cascaded_tasks
                },
                events_generated=events_generated
            )
            
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Error rescheduling task: {str(e)}",
                errors=[str(e)]
            )
    
    async def _handle_assign_resource(self, command: AssignResourceCommand) -> CommandResult:
        """Handle resource assignment command."""
        try:
            task = await self.task_repo.get_by_id(command.task_id)
            if not task:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message=f"Task {command.task_id} not found"
                )
            
            # Assign machine
            if command.machine_id:
                task.assigned_machine_id = command.machine_id
            
            # Assign operators
            for operator_id in command.operator_ids:
                # This would create proper operator assignments
                pass
            
            await self.task_repo.update(task)
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Resources assigned to task {command.task_id}",
                data={
                    "task_id": str(command.task_id),
                    "machine_id": str(command.machine_id) if command.machine_id else None,
                    "operator_ids": [str(oid) for oid in command.operator_ids]
                },
                events_generated=1
            )
            
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Error assigning resources: {str(e)}",
                errors=[str(e)]
            )
    
    async def _handle_optimize_schedule(self, command: OptimizeScheduleCommand) -> CommandResult:
        """Handle schedule optimization command."""
        try:
            # Create optimization request
            from ..optimization.optimization_service import SchedulingOptimizationRequest
            
            optimization_request = SchedulingOptimizationRequest(
                job_ids=command.job_ids,
                task_ids=command.task_ids,
                department=command.department,
                optimization_start=command.optimization_start,
                optimization_end=command.optimization_end,
                objective=getattr(OptimizationObjective, command.objective.upper()),
                max_optimization_time_seconds=command.max_optimization_time_seconds,
                solution_quality_target=command.solution_quality_target,
                allow_overtime=command.allow_overtime,
                max_overtime_hours=command.max_overtime_hours
            )
            
            # Run optimization
            result = await self.optimization_service.optimize_schedule(optimization_request)
            
            if not result.is_feasible:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message="Optimization could not find feasible solution",
                    data={
                        "status": result.status,
                        "constraint_violations": len(result.constraint_violations),
                        "solution_time_seconds": result.solution_time_seconds
                    }
                )
            
            # Apply results if requested
            tasks_updated = 0
            if command.apply_immediately:
                for assignment in result.task_assignments:
                    task = await self.task_repo.get_by_id(assignment.task_id)
                    if task:
                        task.schedule(
                            start_time=assignment.start_time,
                            end_time=assignment.end_time,
                            machine_id=assignment.assigned_machine_id
                        )
                        await self.task_repo.update(task)
                        tasks_updated += 1
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Schedule optimization completed with {result.status} solution",
                data={
                    "optimization_status": result.status,
                    "objective_value": result.objective_value,
                    "makespan_hours": result.makespan_hours,
                    "task_assignments": len(result.task_assignments),
                    "tasks_updated": tasks_updated,
                    "solution_time_seconds": result.solution_time_seconds,
                    "avg_resource_utilization": result.avg_resource_utilization
                },
                events_generated=tasks_updated
            )
            
        except OptimizationError as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Optimization failed: {str(e)}",
                errors=[str(e)]
            )
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Unexpected optimization error: {str(e)}",
                errors=[str(e)]
            )
    
    async def _handle_update_task_status(self, command: UpdateTaskStatusCommand) -> CommandResult:
        """Handle task status update command."""
        try:
            task = await self.task_repo.get_by_id(command.task_id)
            if not task:
                return CommandResult(
                    command_id=command.command_id,
                    success=False,
                    message=f"Task {command.task_id} not found"
                )
            
            # Update task based on status
            if command.new_status == "IN_PROGRESS":
                task.start(command.actual_start_time)
            elif command.new_status == "COMPLETED":
                task.complete(command.actual_end_time)
            elif command.new_status == "FAILED":
                task.fail("Task failed", command.actual_end_time)
            elif command.new_status == "CANCELLED":
                task.cancel("Task cancelled")
            
            # Handle rework if needed
            if command.rework_required and command.rework_reason:
                task.record_rework(command.rework_reason)
            
            await self.task_repo.update(task)
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Task {command.task_id} status updated to {command.new_status}",
                data={
                    "task_id": str(command.task_id),
                    "old_status": task.status.value,
                    "new_status": command.new_status,
                    "rework_required": command.rework_required
                },
                events_generated=1
            )
            
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Error updating task status: {str(e)}",
                errors=[str(e)]
            )
    
    async def _handle_resource_disruption(self, command: HandleResourceDisruptionCommand) -> CommandResult:
        """Handle resource disruption command."""
        try:
            # Trigger reoptimization for affected scope
            optimization_result = await self.optimization_service.reoptimize_with_disruption(
                disruption_type=command.disruption_type,
                affected_resource_ids=command.affected_resource_ids,
                disruption_start=command.disruption_start,
                disruption_end=command.disruption_end,
                scope_hours=command.max_delay_acceptable_hours
            )
            
            # Apply reoptimization if feasible
            tasks_rescheduled = 0
            if optimization_result.is_feasible:
                for assignment in optimization_result.task_assignments:
                    task = await self.task_repo.get_by_id(assignment.task_id)
                    if task and assignment.delay_minutes > 0:  # Only reschedule delayed tasks
                        task.reschedule(
                            new_start=assignment.start_time,
                            new_end=assignment.end_time,
                            reason=f"Disruption response: {command.disruption_type}"
                        )
                        await self.task_repo.update(task)
                        tasks_rescheduled += 1
            
            return CommandResult(
                command_id=command.command_id,
                success=True,
                message=f"Handled {command.disruption_type} affecting {len(command.affected_resource_ids)} resources",
                data={
                    "disruption_type": command.disruption_type,
                    "affected_resources": len(command.affected_resource_ids),
                    "reoptimization_status": optimization_result.status,
                    "tasks_rescheduled": tasks_rescheduled,
                    "total_delay_hours": optimization_result.total_delay_hours
                },
                events_generated=tasks_rescheduled
            )
            
        except Exception as e:
            return CommandResult(
                command_id=command.command_id,
                success=False,
                message=f"Error handling resource disruption: {str(e)}",
                errors=[str(e)]
            )


class SchedulingQueryHandler(QueryHandler):
    """Main query handler for scheduling domain read operations."""
    
    def __init__(
        self,
        machine_utilization_model: MachineUtilizationReadModel,
        operator_load_model: OperatorLoadReadModel,
        job_flow_model: JobFlowMetricsReadModel,
        dashboard_model: SchedulingDashboardReadModel,
        task_repository: TaskRepository
    ):
        self.machine_model = machine_utilization_model
        self.operator_model = operator_load_model
        self.job_flow_model = job_flow_model
        self.dashboard_model = dashboard_model
        self.task_repo = task_repository
    
    def can_handle(self, query: Query) -> bool:
        """Check if this handler can process the query."""
        handled_types = [
            GetMachineUtilizationQuery,
            GetOperatorWorkloadQuery,
            GetJobFlowMetricsQuery,
            GetDashboardSummaryQuery,
            GetTaskScheduleQuery,
            GetResourceAvailabilityQuery
        ]
        return type(query) in handled_types
    
    async def handle(self, query: Query) -> QueryResult:
        """Handle scheduling queries."""
        try:
            if isinstance(query, GetMachineUtilizationQuery):
                return await self._handle_machine_utilization_query(query)
            elif isinstance(query, GetOperatorWorkloadQuery):
                return await self._handle_operator_workload_query(query)
            elif isinstance(query, GetJobFlowMetricsQuery):
                return await self._handle_job_flow_metrics_query(query)
            elif isinstance(query, GetDashboardSummaryQuery):
                return await self._handle_dashboard_summary_query(query)
            elif isinstance(query, GetTaskScheduleQuery):
                return await self._handle_task_schedule_query(query)
            else:
                return QueryResult(
                    query_id=query.query_id,
                    success=False,
                    errors=[f"Query type {type(query).__name__} not supported"]
                )
        except Exception as e:
            return QueryResult(
                query_id=query.query_id,
                success=False,
                errors=[str(e)]
            )
    
    async def _handle_machine_utilization_query(self, query: GetMachineUtilizationQuery) -> QueryResult:
        """Handle machine utilization query."""
        buckets = await self.machine_model.get_machine_utilization_buckets(
            machine_ids=query.machine_ids,
            start_time=query.start_time,
            end_time=query.end_time,
            bucket_type=query.bucket_type,
            include_inactive=query.include_inactive
        )
        
        # Add bottleneck analysis if requested
        bottlenecks = []
        if query.include_bottleneck_analysis:
            bottlenecks = await self.machine_model.get_machine_bottlenecks(
                start_time=query.start_time,
                end_time=query.end_time
            )
        
        return QueryResult(
            query_id=query.query_id,
            success=True,
            data={
                "utilization_buckets": [bucket.dict() for bucket in buckets],
                "bottlenecks": bottlenecks,
                "bucket_count": len(buckets),
                "time_range": {
                    "start": query.start_time.isoformat() if query.start_time else None,
                    "end": query.end_time.isoformat() if query.end_time else None
                }
            },
            metadata={
                "bucket_type": query.bucket_type,
                "include_bottlenecks": query.include_bottleneck_analysis
            }
        )
    
    async def _handle_operator_workload_query(self, query: GetOperatorWorkloadQuery) -> QueryResult:
        """Handle operator workload query."""
        # Get workload buckets
        buckets = await self.operator_model.get_operator_load_buckets(
            operator_ids=query.operator_ids,
            department=query.department,
            bucket_hours=8  # Default to shift-based buckets
        )
        
        # Get availability forecast if requested
        forecast = []
        if query.include_availability_forecast:
            forecast = await self.operator_model.get_availability_forecast(
                forecast_days=query.forecast_days,
                department=query.department,
                skill_codes=query.skill_codes
            )
        
        # Get overloaded operators if requested
        overloaded = []
        if query.include_overload_detection:
            overloaded = await self.operator_model.get_overloaded_operators(
                threshold_load=query.overload_threshold
            )
        
        return QueryResult(
            query_id=query.query_id,
            success=True,
            data={
                "workload_buckets": [bucket.dict() for bucket in buckets],
                "availability_forecast": [forecast_item.dict() for forecast_item in forecast],
                "overloaded_operators": overloaded,
                "bucket_count": len(buckets),
                "forecast_days": query.forecast_days
            },
            metadata={
                "include_forecast": query.include_availability_forecast,
                "include_overload_detection": query.include_overload_detection,
                "overload_threshold": query.overload_threshold
            }
        )
    
    async def _handle_job_flow_metrics_query(self, query: GetJobFlowMetricsQuery) -> QueryResult:
        """Handle job flow metrics query."""
        # Get throughput metrics
        throughput = None
        if query.include_throughput_analysis:
            throughput = await self.job_flow_model.get_throughput_metrics(
                start_time=query.start_time,
                end_time=query.end_time,
                department=query.department,
                job_types=query.job_types
            )
        
        # Get cycle time analysis
        cycle_time = None
        if query.include_cycle_time_analysis:
            cycle_time = await self.job_flow_model.get_cycle_time_analysis(
                department=query.department,
                analysis_days=query.analysis_period_days
            )
        
        # Get WIP analysis
        wip = None
        if query.include_wip_analysis:
            wip = await self.job_flow_model.get_wip_analysis(
                department=query.department
            )
        
        return QueryResult(
            query_id=query.query_id,
            success=True,
            data={
                "throughput_metrics": throughput.dict() if throughput else None,
                "cycle_time_analysis": cycle_time.dict() if cycle_time else None,
                "wip_analysis": wip.dict() if wip else None,
                "analysis_period_days": query.analysis_period_days
            },
            metadata={
                "include_throughput": query.include_throughput_analysis,
                "include_cycle_time": query.include_cycle_time_analysis,
                "include_wip": query.include_wip_analysis
            }
        )
    
    async def _handle_dashboard_summary_query(self, query: GetDashboardSummaryQuery) -> QueryResult:
        """Handle dashboard summary query."""
        # Get KPIs
        kpis = None
        if query.include_kpis:
            from ..read_models.scheduling_dashboard import DashboardTimeRange
            time_range = DashboardTimeRange(
                start_time=datetime.combine(query.date or date.today(), datetime.min.time()),
                end_time=datetime.combine(query.date or date.today(), datetime.min.time()) + timedelta(hours=query.time_range_hours)
            )
            kpis = await self.dashboard_model.get_dashboard_kpis(
                time_range=time_range,
                department=query.department
            )
        
        # Get alerts
        alerts = []
        if query.include_alerts:
            alerts = await self.dashboard_model.get_resource_alerts(
                severity_threshold=query.alert_severity_threshold,
                department=query.department,
                limit=query.max_alerts
            )
        
        # Get schedule health
        health = None
        if query.include_schedule_health:
            health = await self.dashboard_model.get_schedule_health_status(
                department=query.department
            )
        
        return QueryResult(
            query_id=query.query_id,
            success=True,
            data={
                "kpis": kpis.dict() if kpis else None,
                "alerts": [alert.dict() for alert in alerts],
                "schedule_health": health.dict() if health else None,
                "alert_count": len(alerts),
                "data_freshness": datetime.utcnow().isoformat()
            },
            metadata={
                "department": query.department,
                "time_range_hours": query.time_range_hours,
                "alert_severity_threshold": query.alert_severity_threshold
            },
            data_freshness=datetime.utcnow()
        )
    
    async def _handle_task_schedule_query(self, query: GetTaskScheduleQuery) -> QueryResult:
        """Handle task schedule query."""
        # Build filter criteria
        filters = {}
        if query.task_ids:
            filters['task_ids'] = query.task_ids
        if query.job_ids:
            filters['job_ids'] = query.job_ids
        if query.start_time:
            filters['start_time'] = query.start_time
        if query.end_time:
            filters['end_time'] = query.end_time
        if query.task_statuses:
            filters['statuses'] = query.task_statuses
        
        # Get tasks
        tasks = await self.task_repo.get_tasks_by_filters(
            filters=filters,
            offset=query.offset,
            limit=query.limit,
            sort_by=query.sort_by,
            sort_order=query.sort_order
        )
        
        # Build response data
        task_data = []
        for task in tasks:
            task_info = {
                "task_id": str(task.id),
                "job_id": str(task.job_id),
                "status": task.status.value,
                "planned_start_time": task.planned_start_time.isoformat() if task.planned_start_time else None,
                "planned_end_time": task.planned_end_time.isoformat() if task.planned_end_time else None,
                "actual_start_time": task.actual_start_time.isoformat() if task.actual_start_time else None,
                "actual_end_time": task.actual_end_time.isoformat() if task.actual_end_time else None,
                "delay_minutes": task.delay_minutes,
                "is_critical_path": task.is_critical_path
            }
            
            if query.include_resource_assignments:
                task_info["assigned_machine_id"] = str(task.assigned_machine_id) if task.assigned_machine_id else None
                task_info["operator_assignments"] = len(task.active_operator_assignments)
            
            if query.include_dependencies:
                task_info["predecessor_ids"] = [str(pid) for pid in task.predecessor_ids]
            
            task_data.append(task_info)
        
        return QueryResult(
            query_id=query.query_id,
            success=True,
            data={
                "tasks": task_data,
                "task_count": len(task_data),
                "offset": query.offset,
                "limit": query.limit,
                "has_more": len(task_data) == query.limit  # Simple check for pagination
            },
            metadata={
                "filters": filters,
                "sort_by": query.sort_by,
                "sort_order": query.sort_order
            }
        )