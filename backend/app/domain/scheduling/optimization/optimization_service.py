"""
Scheduling optimization service integrating OR-Tools with domain entities.

Bridges the gap between domain models (Task, Machine, Operator) and the 
CP-SAT optimization solver, providing high-level scheduling optimization.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from ....shared.exceptions import OptimizationError, ValidationError
from ..entities.task import Task
from ..entities.machine import Machine
from ..entities.operator import Operator
from ..entities.job import Job
from ..repositories.task_repository import TaskRepository
from ..repositories.machine_repository import MachineRepository
from ..repositories.operator_repository import OperatorRepository
from ..repositories.job_repository import JobRepository
from ..services.resource_allocation_service import ResourceAllocationService

from .cp_sat_scheduler import CPSATScheduler, SchedulingProblem, OptimizationResult, TaskAssignment
from .constraint_models import (
    ResourceConstraints,
    TemporalConstraints,
    SkillConstraints,
    OptimizationObjective
)


class SchedulingOptimizationRequest(BaseModel):
    """Request for scheduling optimization."""
    
    # Scope definition
    job_ids: Optional[List[UUID]] = None  # Specific jobs to optimize
    task_ids: Optional[List[UUID]] = None  # Specific tasks to optimize
    department: Optional[str] = None  # Department filter
    
    # Time horizon
    optimization_start: datetime
    optimization_end: datetime
    
    # Optimization preferences
    objective: OptimizationObjective = OptimizationObjective.MINIMIZE_MAKESPAN
    priority_weights: Dict[str, float] = Field(default_factory=dict)
    
    # Constraint preferences
    allow_overtime: bool = False
    max_overtime_hours: float = Field(default=2.0, ge=0.0, le=8.0)
    respect_skill_levels: bool = True
    min_skill_level_override: Optional[int] = None
    
    # Solution preferences  
    max_optimization_time_seconds: float = Field(default=300.0, ge=30.0, le=1800.0)
    solution_quality_target: float = Field(default=0.95, ge=0.5, le=1.0)
    
    # Resource preferences
    preferred_machine_assignments: Dict[UUID, UUID] = Field(default_factory=dict)  # task_id -> machine_id
    preferred_operator_assignments: Dict[UUID, UUID] = Field(default_factory=dict)  # task_id -> operator_id
    
    # Constraints to ignore (for what-if analysis)
    ignore_skill_constraints: bool = False
    ignore_availability_windows: bool = False


class SchedulingOptimizationService:
    """
    Service for optimizing task schedules using constraint programming.
    
    Integrates domain entities with OR-Tools CP-SAT solver to provide
    optimal or near-optimal scheduling solutions with resource allocation.
    """
    
    def __init__(
        self,
        task_repository: TaskRepository,
        machine_repository: MachineRepository,
        operator_repository: OperatorRepository,
        job_repository: JobRepository,
        resource_allocation_service: ResourceAllocationService
    ):
        """Initialize the optimization service."""
        self.task_repo = task_repository
        self.machine_repo = machine_repository
        self.operator_repo = operator_repository
        self.job_repo = job_repository
        self.resource_service = resource_allocation_service
        self.scheduler = CPSATScheduler()
    
    async def optimize_schedule(
        self,
        request: SchedulingOptimizationRequest
    ) -> OptimizationResult:
        """
        Optimize task schedule based on the request parameters.
        
        Args:
            request: Optimization request with constraints and preferences
            
        Returns:
            Optimization result with optimal task assignments
            
        Raises:
            OptimizationError: If optimization fails
            ValidationError: If request is invalid
        """
        # Validate request
        await self._validate_request(request)
        
        # Load domain entities
        tasks = await self._load_tasks(request)
        machines = await self._load_machines(request)
        operators = await self._load_operators(request)
        
        if not tasks:
            raise ValidationError("No tasks found for optimization")
        
        # Build scheduling problem
        problem = await self._build_scheduling_problem(request, tasks, machines, operators)
        
        # Solve optimization problem
        result = self.scheduler.solve(problem)
        
        # Post-process and validate solution
        if result.is_feasible:
            result = await self._post_process_solution(result, tasks, machines, operators)
        
        return result
    
    async def optimize_job_schedule(
        self,
        job_id: UUID,
        objective: OptimizationObjective = OptimizationObjective.MINIMIZE_MAKESPAN,
        max_time_seconds: float = 300.0
    ) -> OptimizationResult:
        """
        Optimize schedule for a specific job.
        
        Args:
            job_id: Job to optimize
            objective: Optimization objective
            max_time_seconds: Maximum optimization time
            
        Returns:
            Optimization result for the job
        """
        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise ValidationError(f"Job {job_id} not found")
        
        request = SchedulingOptimizationRequest(
            job_ids=[job_id],
            optimization_start=datetime.utcnow(),
            optimization_end=datetime.utcnow() + timedelta(days=7),
            objective=objective,
            max_optimization_time_seconds=max_time_seconds
        )
        
        return await self.optimize_schedule(request)
    
    async def reoptimize_with_disruption(
        self,
        disruption_type: str,
        affected_resource_ids: List[UUID],
        disruption_start: datetime,
        disruption_end: datetime,
        scope_hours: float = 24.0
    ) -> OptimizationResult:
        """
        Reoptimize schedule after a disruption (machine breakdown, operator absence, etc.).
        
        Args:
            disruption_type: Type of disruption (machine_breakdown, operator_absence, etc.)
            affected_resource_ids: IDs of affected resources
            disruption_start: When disruption starts
            disruption_end: When disruption ends (None for unknown)
            scope_hours: Hours of schedule to reoptimize
            
        Returns:
            Reoptimized schedule avoiding the disruption
        """
        optimization_end = disruption_start + timedelta(hours=scope_hours)
        
        request = SchedulingOptimizationRequest(
            optimization_start=disruption_start,
            optimization_end=optimization_end,
            objective=OptimizationObjective.MINIMIZE_TOTAL_DELAY,
            max_optimization_time_seconds=180.0  # Shorter time for reactive optimization
        )
        
        # Load affected tasks
        tasks = await self._load_tasks_in_timeframe(disruption_start, optimization_end)
        machines = await self.machine_repo.get_all()
        operators = await self.operator_repo.get_all()
        
        # Build problem with disruption constraints
        problem = await self._build_scheduling_problem(request, tasks, machines, operators)
        
        # Add disruption constraints
        await self._add_disruption_constraints(
            problem, disruption_type, affected_resource_ids, disruption_start, disruption_end
        )
        
        return self.scheduler.solve(problem)
    
    async def evaluate_what_if_scenario(
        self,
        scenario_name: str,
        scenario_changes: Dict[str, any],
        base_request: SchedulingOptimizationRequest
    ) -> Tuple[OptimizationResult, OptimizationResult]:
        """
        Evaluate a what-if scenario against the baseline schedule.
        
        Args:
            scenario_name: Description of the scenario
            scenario_changes: Changes to apply to the baseline
            base_request: Base optimization request
            
        Returns:
            Tuple of (baseline_result, scenario_result)
        """
        # Get baseline result
        baseline_result = await self.optimize_schedule(base_request)
        
        # Apply scenario changes
        scenario_request = base_request.copy(deep=True)
        await self._apply_scenario_changes(scenario_request, scenario_changes)
        
        # Get scenario result
        scenario_result = await self.optimize_schedule(scenario_request)
        
        return baseline_result, scenario_result
    
    async def _validate_request(self, request: SchedulingOptimizationRequest) -> None:
        """Validate optimization request."""
        if request.optimization_start >= request.optimization_end:
            raise ValidationError("Optimization start must be before end time")
        
        if request.max_optimization_time_seconds < 30:
            raise ValidationError("Optimization time must be at least 30 seconds")
        
        horizon_hours = (request.optimization_end - request.optimization_start).total_seconds() / 3600
        if horizon_hours > 168:  # 1 week
            raise ValidationError("Optimization horizon cannot exceed 1 week")
    
    async def _load_tasks(self, request: SchedulingOptimizationRequest) -> List[Task]:
        """Load tasks to be optimized based on request criteria."""
        if request.task_ids:
            # Load specific tasks
            tasks = []
            for task_id in request.task_ids:
                task = await self.task_repo.get_by_id(task_id)
                if task:
                    tasks.append(task)
            return tasks
        
        elif request.job_ids:
            # Load tasks from specific jobs
            tasks = []
            for job_id in request.job_ids:
                job_tasks = await self.task_repo.get_by_job_id(job_id)
                tasks.extend(job_tasks)
            return tasks
        
        else:
            # Load tasks by time window and department
            return await self.task_repo.get_tasks_in_timeframe(
                start_time=request.optimization_start,
                end_time=request.optimization_end,
                department=request.department,
                statuses=["PENDING", "READY", "SCHEDULED"]
            )
    
    async def _load_tasks_in_timeframe(
        self, 
        start_time: datetime, 
        end_time: datetime
    ) -> List[Task]:
        """Load tasks that overlap with the given timeframe."""
        return await self.task_repo.get_tasks_in_timeframe(
            start_time=start_time,
            end_time=end_time,
            statuses=["PENDING", "READY", "SCHEDULED", "IN_PROGRESS"]
        )
    
    async def _load_machines(self, request: SchedulingOptimizationRequest) -> List[Machine]:
        """Load available machines for optimization."""
        machines = await self.machine_repo.get_all()
        
        # Filter by department
        if request.department:
            machines = [m for m in machines if m.department == request.department]
        
        # Filter active machines
        machines = [m for m in machines if m.is_active]
        
        return machines
    
    async def _load_operators(self, request: SchedulingOptimizationRequest) -> List[Operator]:
        """Load available operators for optimization."""
        operators = await self.operator_repo.get_all()
        
        # Filter by department
        if request.department:
            operators = [o for o in operators if o.department == request.department]
        
        # Filter active operators
        operators = [o for o in operators if o.is_active and o.is_available_for_work]
        
        return operators
    
    async def _build_scheduling_problem(
        self,
        request: SchedulingOptimizationRequest,
        tasks: List[Task],
        machines: List[Machine],
        operators: List[Operator]
    ) -> SchedulingProblem:
        """Build CP-SAT scheduling problem from domain entities."""
        
        problem = SchedulingProblem(
            problem_id=f"schedule_opt_{int(datetime.utcnow().timestamp())}",
            planning_horizon_start=request.optimization_start,
            planning_horizon_end=request.optimization_end,
            optimization_objective=request.objective,
            max_solution_time_seconds=request.max_optimization_time_seconds
        )
        
        # Add tasks
        for task in tasks:
            problem.task_ids.append(task.id)
            problem.task_durations[task.id] = task.planned_duration.minutes if task.planned_duration else 60
            problem.task_priorities[task.id] = 1.0  # Could be derived from job priority
        
        # Add resources
        problem.machine_ids = [m.id for m in machines]
        problem.operator_ids = [o.id for o in operators]
        
        # Build constraints
        await self._build_resource_constraints(problem, request, tasks, machines, operators)
        await self._build_temporal_constraints(problem, request, tasks)
        await self._build_skill_constraints(problem, request, tasks, operators)
        
        return problem
    
    async def _build_resource_constraints(
        self,
        problem: SchedulingProblem,
        request: SchedulingOptimizationRequest,
        tasks: List[Task],
        machines: List[Machine],
        operators: List[Operator]
    ) -> None:
        """Build resource capacity and availability constraints."""
        
        resource_constraints = ResourceConstraints()
        
        # Machine constraints
        for machine in machines:
            availability_windows = []
            if not request.ignore_availability_windows:
                # Convert machine availability to time windows
                # Simplified: assume machines are available during business hours
                start_minutes = 0
                end_minutes = problem.time_slots
                availability_windows = [(start_minutes, end_minutes)]
            
            resource_constraints.add_machine_constraint(
                machine.id,
                capacity=1,  # Most machines handle one task at a time
                availability_windows=availability_windows
            )
        
        # Operator constraints
        for operator in operators:
            availability_windows = []
            if not request.ignore_availability_windows:
                # Convert operator working hours to availability windows
                working_hours = operator.default_working_hours
                # This would need proper conversion from working hours to time slots
                start_minutes = 0
                end_minutes = problem.time_slots
                availability_windows = [(start_minutes, end_minutes)]
            
            # Get operator skills
            skills = {}
            for skill in operator.active_skills:
                skills[skill.skill.skill_code] = skill.proficiency_level
            
            max_capacity = 2 if request.allow_overtime else 1
            
            resource_constraints.add_operator_constraint(
                operator.id,
                capacity=max_capacity,
                availability_windows=availability_windows,
                skills=skills
            )
        
        problem.resource_constraints = resource_constraints
    
    async def _build_temporal_constraints(
        self,
        problem: SchedulingProblem,
        request: SchedulingOptimizationRequest,
        tasks: List[Task]
    ) -> None:
        """Build temporal and precedence constraints."""
        
        temporal_constraints = TemporalConstraints()
        
        for task in tasks:
            # Add precedence relationships
            for predecessor_id in task.predecessor_ids:
                temporal_constraints.add_precedence(predecessor_id, task.id)
            
            # Add time windows if task has planned times
            if task.planned_start_time and task.planned_end_time:
                temporal_constraints.add_time_window(
                    task.id,
                    earliest_start=max(task.planned_start_time, request.optimization_start),
                    latest_end=min(task.planned_end_time, request.optimization_end),
                    reference_time=request.optimization_start
                )
            
            # Add duration constraints
            duration = task.planned_duration.minutes if task.planned_duration else 60
            temporal_constraints.add_duration_constraint(
                task.id,
                duration_minutes=duration
            )
        
        problem.temporal_constraints = temporal_constraints
    
    async def _build_skill_constraints(
        self,
        problem: SchedulingProblem,
        request: SchedulingOptimizationRequest,
        tasks: List[Task],
        operators: List[Operator]
    ) -> None:
        """Build skill-based assignment constraints."""
        
        if request.ignore_skill_constraints:
            return
        
        skill_constraints = SkillConstraints()
        
        # Add task skill requirements
        for task in tasks:
            required_skills = []
            
            # Convert role requirements to skill requirements
            for role_req in task.role_requirements:
                min_level = request.min_skill_level_override or role_req.minimum_level
                required_skills.append((role_req.skill_type, min_level))
            
            # Fallback to legacy skill requirements
            if not required_skills:
                for skill_req in task.skill_requirements:
                    min_level = request.min_skill_level_override or skill_req.minimum_level
                    required_skills.append((skill_req.skill_type, min_level))
            
            if required_skills:
                skill_constraints.add_task_skill_requirement(task.id, required_skills)
        
        # Add operator skills
        for operator in operators:
            skills = {}
            for skill in operator.active_skills:
                skills[skill.skill.skill_code] = skill.proficiency_level
            
            if skills:
                skill_constraints.add_operator_skills(operator.id, skills)
        
        problem.skill_constraints = skill_constraints
    
    async def _add_disruption_constraints(
        self,
        problem: SchedulingProblem,
        disruption_type: str,
        affected_resource_ids: List[UUID],
        disruption_start: datetime,
        disruption_end: Optional[datetime]
    ) -> None:
        """Add constraints for handling disruptions."""
        
        disruption_start_minutes = int((disruption_start - problem.planning_horizon_start).total_seconds() / 60)
        disruption_end_minutes = problem.time_slots
        
        if disruption_end:
            disruption_end_minutes = min(
                disruption_end_minutes,
                int((disruption_end - problem.planning_horizon_start).total_seconds() / 60)
            )
        
        if disruption_type == "machine_breakdown":
            # Remove machine availability during disruption
            for machine_id in affected_resource_ids:
                if machine_id in problem.resource_constraints.machine_availability_windows:
                    # Remove disruption period from availability windows
                    windows = problem.resource_constraints.machine_availability_windows[machine_id]
                    updated_windows = []
                    
                    for start, end in windows:
                        if end <= disruption_start_minutes or start >= disruption_end_minutes:
                            # Window doesn't overlap with disruption
                            updated_windows.append((start, end))
                        else:
                            # Split window around disruption
                            if start < disruption_start_minutes:
                                updated_windows.append((start, disruption_start_minutes))
                            if disruption_end_minutes < end:
                                updated_windows.append((disruption_end_minutes, end))
                    
                    problem.resource_constraints.machine_availability_windows[machine_id] = updated_windows
        
        elif disruption_type == "operator_absence":
            # Remove operator availability during disruption
            for operator_id in affected_resource_ids:
                if operator_id in problem.resource_constraints.operator_availability_windows:
                    # Similar logic to machine breakdown
                    windows = problem.resource_constraints.operator_availability_windows[operator_id]
                    updated_windows = []
                    
                    for start, end in windows:
                        if end <= disruption_start_minutes or start >= disruption_end_minutes:
                            updated_windows.append((start, end))
                        else:
                            if start < disruption_start_minutes:
                                updated_windows.append((start, disruption_start_minutes))
                            if disruption_end_minutes < end:
                                updated_windows.append((disruption_end_minutes, end))
                    
                    problem.resource_constraints.operator_availability_windows[operator_id] = updated_windows
    
    async def _apply_scenario_changes(
        self,
        request: SchedulingOptimizationRequest,
        changes: Dict[str, any]
    ) -> None:
        """Apply what-if scenario changes to optimization request."""
        
        if "additional_machines" in changes:
            # Would need to add new machine entities
            pass
        
        if "additional_operators" in changes:
            # Would need to add new operator entities  
            pass
        
        if "extended_hours" in changes:
            # Extend optimization window
            extension_hours = changes["extended_hours"]
            request.optimization_end += timedelta(hours=extension_hours)
            request.allow_overtime = True
        
        if "priority_changes" in changes:
            # Update task priorities
            request.priority_weights.update(changes["priority_changes"])
        
        if "skill_relaxation" in changes:
            # Relax skill requirements
            if changes["skill_relaxation"]:
                request.min_skill_level_override = 1  # Lower minimum skill level
    
    async def _post_process_solution(
        self,
        result: OptimizationResult,
        tasks: List[Task],
        machines: List[Machine],
        operators: List[Operator]
    ) -> OptimizationResult:
        """Post-process and validate the optimization solution."""
        
        # Create lookup maps for entities
        task_map = {t.id: t for t in tasks}
        machine_map = {m.id: m for m in machines}
        operator_map = {o.id: o for o in operators}
        
        # Enhance task assignments with domain information
        enhanced_assignments = []
        
        for assignment in result.task_assignments:
            task = task_map.get(assignment.task_id)
            if not task:
                continue
            
            # Calculate assignment quality score
            score = 1.0
            
            # Machine compatibility score
            if assignment.assigned_machine_id:
                machine = machine_map.get(assignment.assigned_machine_id)
                if machine:
                    # Check if machine can handle this task type
                    if hasattr(task, 'task_type') and hasattr(machine, 'can_perform_task_type'):
                        if machine.can_perform_task_type(task.task_type.value):
                            score *= 1.0
                        else:
                            score *= 0.5  # Penalty for incompatible assignment
            
            # Operator skill match score already calculated
            score *= assignment.skill_match_score
            
            # Update assignment with enhanced score
            assignment.assignment_score = score
            enhanced_assignments.append(assignment)
        
        result.task_assignments = enhanced_assignments
        
        return result