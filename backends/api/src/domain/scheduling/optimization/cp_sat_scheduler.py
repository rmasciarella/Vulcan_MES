"""
CP-SAT scheduler implementation using OR-Tools.

Provides constraint programming solver for optimal task scheduling with
resource allocation, temporal constraints, and skill-based assignments.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from uuid import UUID
from enum import Enum
import time

from pydantic import BaseModel, Field
from ortools.sat.python import cp_model

from .constraint_models import (
    ResourceConstraints,
    TemporalConstraints,
    SkillConstraints,
    OptimizationObjective,
    ConstraintViolation,
    ConstraintValidator,
    CPSATConstraintBuilder
)


class SolutionStatus(str, Enum):
    """Status of the optimization solution."""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"
    MODEL_INVALID = "model_invalid"


class TaskAssignment(BaseModel):
    """Represents a task assignment in the solution."""
    
    task_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    
    # Resource assignments
    assigned_machine_id: Optional[UUID] = None
    assigned_operator_ids: List[UUID] = Field(default_factory=list)
    
    # Assignment quality metrics
    assignment_score: float = Field(ge=0.0, default=1.0)
    skill_match_score: float = Field(ge=0.0, le=1.0, default=1.0)
    
    # Constraint satisfaction
    delay_minutes: int = Field(ge=0, default=0)
    constraint_violations: List[str] = Field(default_factory=list)


class OptimizationResult(BaseModel):
    """Result of the scheduling optimization."""
    
    status: SolutionStatus
    objective_value: float = Field(default=0.0)
    solution_time_seconds: float = Field(ge=0.0)
    
    # Task assignments
    task_assignments: List[TaskAssignment] = Field(default_factory=list)
    
    # Solution quality metrics
    makespan_hours: float = Field(ge=0.0, default=0.0)
    total_delay_hours: float = Field(ge=0.0, default=0.0)
    resource_utilization: Dict[UUID, float] = Field(default_factory=dict)
    
    # Constraint analysis
    constraint_violations: List[ConstraintViolation] = Field(default_factory=list)
    feasibility_score: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Optimization metadata
    solver_iterations: int = Field(ge=0, default=0)
    variables_count: int = Field(ge=0, default=0)
    constraints_count: int = Field(ge=0, default=0)
    
    @property
    def is_feasible(self) -> bool:
        """Check if solution is feasible."""
        return self.status in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE)
    
    @property
    def avg_resource_utilization(self) -> float:
        """Calculate average resource utilization."""
        if not self.resource_utilization:
            return 0.0
        return sum(self.resource_utilization.values()) / len(self.resource_utilization)
    
    def get_task_assignment(self, task_id: UUID) -> Optional[TaskAssignment]:
        """Get assignment for a specific task."""
        for assignment in self.task_assignments:
            if assignment.task_id == task_id:
                return assignment
        return None


class SchedulingProblem(BaseModel):
    """Defines a complete scheduling problem for optimization."""
    
    # Problem identification
    problem_id: str = Field(default="scheduling_problem")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Time horizon
    planning_horizon_start: datetime
    planning_horizon_end: datetime
    time_granularity_minutes: int = Field(default=15, ge=1)
    
    # Tasks to schedule
    task_ids: List[UUID] = Field(default_factory=list)
    task_durations: Dict[UUID, int] = Field(default_factory=dict)  # minutes
    task_priorities: Dict[UUID, float] = Field(default_factory=dict)
    
    # Resources
    machine_ids: List[UUID] = Field(default_factory=list)
    operator_ids: List[UUID] = Field(default_factory=list)
    
    # Pre-assignments (optional constraints)
    fixed_task_assignments: Dict[UUID, UUID] = Field(default_factory=dict)  # task_id -> resource_id
    preferred_assignments: Dict[UUID, List[UUID]] = Field(default_factory=dict)  # task_id -> [resource_ids]
    
    # Constraint models
    resource_constraints: ResourceConstraints = Field(default_factory=ResourceConstraints)
    temporal_constraints: TemporalConstraints = Field(default_factory=TemporalConstraints)
    skill_constraints: SkillConstraints = Field(default_factory=SkillConstraints)
    
    # Optimization settings
    optimization_objective: OptimizationObjective = OptimizationObjective.MINIMIZE_MAKESPAN
    objective_weights: Dict[str, float] = Field(default_factory=dict)
    
    # Solution constraints
    max_solution_time_seconds: float = Field(default=300.0, ge=1.0)  # 5 minutes default
    solution_quality_tolerance: float = Field(default=0.01, ge=0.001, le=0.1)
    
    @property
    def horizon_minutes(self) -> int:
        """Calculate planning horizon in minutes."""
        return int((self.planning_horizon_end - self.planning_horizon_start).total_seconds() / 60)
    
    @property
    def time_slots(self) -> int:
        """Calculate number of time slots in the horizon."""
        return self.horizon_minutes // self.time_granularity_minutes
    
    def validate_problem(self) -> List[ConstraintViolation]:
        """Validate the problem definition."""
        violations = []
        
        # Basic validation
        if not self.task_ids:
            violations.append(ConstraintViolation(
                constraint_type="problem_definition",
                description="No tasks defined in the problem",
                severity="error"
            ))
        
        if not self.machine_ids and not self.operator_ids:
            violations.append(ConstraintViolation(
                constraint_type="problem_definition", 
                description="No resources defined in the problem",
                severity="error"
            ))
        
        if self.planning_horizon_start >= self.planning_horizon_end:
            violations.append(ConstraintViolation(
                constraint_type="problem_definition",
                description="Invalid planning horizon: start >= end",
                severity="error"
            ))
        
        # Validate using constraint validator
        validator = ConstraintValidator(
            self.resource_constraints,
            self.temporal_constraints,
            self.skill_constraints
        )
        
        violations.extend(validator.validate_all_constraints(
            self.task_ids,
            self.machine_ids,
            self.operator_ids
        ))
        
        return violations


class CPSATScheduler:
    """
    CP-SAT scheduler for optimal task scheduling.
    
    Uses Google OR-Tools CP-SAT solver to find optimal or near-optimal
    solutions for complex scheduling problems with multiple constraints.
    """
    
    def __init__(self):
        """Initialize the CP-SAT scheduler."""
        self.model = None
        self.solver = None
        self.last_solution = None
    
    def solve(self, problem: SchedulingProblem) -> OptimizationResult:
        """
        Solve the scheduling problem using CP-SAT.
        
        Args:
            problem: Complete problem definition with constraints
            
        Returns:
            Optimization result with solution or infeasibility proof
        """
        start_time = time.time()
        
        # Validate problem
        violations = problem.validate_problem()
        if any(v.severity == "error" for v in violations):
            return OptimizationResult(
                status=SolutionStatus.MODEL_INVALID,
                constraint_violations=violations,
                solution_time_seconds=time.time() - start_time
            )
        
        try:
            # Create CP model
            self.model = cp_model.CpModel()
            constraint_builder = CPSATConstraintBuilder(self.model)
            
            # Create variables for tasks
            task_vars = constraint_builder.create_task_variables(
                problem.task_ids,
                problem.time_slots,
                problem.task_durations
            )
            
            # Build resource assignments
            task_resource_assignments = self._build_resource_assignments(problem)
            
            # Add constraints
            constraint_builder.add_resource_constraints(
                task_vars,
                problem.resource_constraints,
                task_resource_assignments
            )
            
            constraint_builder.add_temporal_constraints(
                task_vars,
                problem.temporal_constraints
            )
            
            skill_violations = constraint_builder.add_skill_constraints(
                task_vars,
                problem.skill_constraints,
                self._get_task_operator_assignments(problem, task_resource_assignments)
            )
            violations.extend(skill_violations)
            
            # Set optimization objective
            objective_var = constraint_builder.create_optimization_objective(
                task_vars,
                problem.optimization_objective,
                problem.objective_weights
            )
            
            if problem.optimization_objective == OptimizationObjective.MINIMIZE_MAKESPAN:
                self.model.Minimize(objective_var)
            elif problem.optimization_objective == OptimizationObjective.MINIMIZE_TOTAL_DELAY:
                self.model.Minimize(objective_var)
            else:
                self.model.Minimize(objective_var)  # Default
            
            # Configure solver
            self.solver = cp_model.CpSolver()
            self.solver.parameters.max_time_in_seconds = problem.max_solution_time_seconds
            self.solver.parameters.relative_gap_limit = problem.solution_quality_tolerance
            
            # Solve the model
            solve_status = self.solver.Solve(self.model)
            solution_time = time.time() - start_time
            
            # Convert solution
            return self._convert_solution(
                solve_status,
                problem,
                task_vars,
                task_resource_assignments,
                violations,
                solution_time,
                objective_var
            )
            
        except Exception as e:
            return OptimizationResult(
                status=SolutionStatus.MODEL_INVALID,
                constraint_violations=[ConstraintViolation(
                    constraint_type="solver_error",
                    description=f"Solver error: {str(e)}",
                    severity="error"
                )],
                solution_time_seconds=time.time() - start_time
            )
    
    def _build_resource_assignments(self, problem: SchedulingProblem) -> Dict[UUID, UUID]:
        """Build initial resource assignments for tasks."""
        assignments = {}
        
        # Use fixed assignments first
        assignments.update(problem.fixed_task_assignments)
        
        # Assign remaining tasks using simple heuristic
        unassigned_tasks = [t for t in problem.task_ids if t not in assignments]
        available_machines = problem.machine_ids.copy()
        
        for task_id in unassigned_tasks:
            # Simple round-robin assignment to machines
            if available_machines:
                machine_id = available_machines[len(assignments) % len(available_machines)]
                assignments[task_id] = machine_id
        
        return assignments
    
    def _get_task_operator_assignments(
        self,
        problem: SchedulingProblem,
        task_resource_assignments: Dict[UUID, UUID]
    ) -> Dict[UUID, UUID]:
        """Generate operator assignments based on skill constraints."""
        operator_assignments = {}
        
        for task_id in problem.task_ids:
            # Find best operator for this task
            best_operator = None
            best_score = 0.0
            
            for operator_id in problem.operator_ids:
                if problem.skill_constraints.can_operator_perform_task(operator_id, task_id):
                    score = problem.skill_constraints.get_skill_match_score(operator_id, task_id)
                    if score > best_score:
                        best_score = score
                        best_operator = operator_id
            
            if best_operator:
                operator_assignments[task_id] = best_operator
        
        return operator_assignments
    
    def _convert_solution(
        self,
        solve_status: int,
        problem: SchedulingProblem,
        task_vars: Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]],
        task_resource_assignments: Dict[UUID, UUID],
        violations: List[ConstraintViolation],
        solution_time: float,
        objective_var: cp_model.IntVar
    ) -> OptimizationResult:
        """Convert CP-SAT solution to optimization result."""
        
        # Map CP-SAT status to our status
        status_mapping = {
            cp_model.OPTIMAL: SolutionStatus.OPTIMAL,
            cp_model.FEASIBLE: SolutionStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolutionStatus.INFEASIBLE,
            cp_model.UNKNOWN: SolutionStatus.UNKNOWN,
            cp_model.MODEL_INVALID: SolutionStatus.MODEL_INVALID
        }
        
        status = status_mapping.get(solve_status, SolutionStatus.UNKNOWN)
        
        if status not in (SolutionStatus.OPTIMAL, SolutionStatus.FEASIBLE):
            return OptimizationResult(
                status=status,
                constraint_violations=violations,
                solution_time_seconds=solution_time,
                variables_count=len(task_vars) * 3,  # start, end, interval per task
                constraints_count=self.model.Proto().constraints.__len__()
            )
        
        # Extract task assignments
        task_assignments = []
        makespan = 0
        total_delay = 0
        
        for task_id, (start_var, end_var, _) in task_vars.items():
            start_minutes = self.solver.Value(start_var) * problem.time_granularity_minutes
            end_minutes = self.solver.Value(end_var) * problem.time_granularity_minutes
            
            start_time = problem.planning_horizon_start + timedelta(minutes=start_minutes)
            end_time = problem.planning_horizon_start + timedelta(minutes=end_minutes)
            duration = end_minutes - start_minutes
            
            # Calculate delay
            planned_start = problem.temporal_constraints.task_earliest_start.get(task_id, 0)
            delay = max(0, start_minutes - planned_start * problem.time_granularity_minutes)
            total_delay += delay
            
            # Get resource assignments
            machine_id = task_resource_assignments.get(task_id)
            operator_assignments = self._get_task_operator_assignments(problem, task_resource_assignments)
            operator_id = operator_assignments.get(task_id)
            operator_ids = [operator_id] if operator_id else []
            
            # Calculate skill match score
            skill_score = 1.0
            if operator_id:
                skill_score = problem.skill_constraints.get_skill_match_score(operator_id, task_id)
            
            task_assignments.append(TaskAssignment(
                task_id=task_id,
                start_time=start_time,
                end_time=end_time,
                duration_minutes=duration,
                assigned_machine_id=machine_id,
                assigned_operator_ids=operator_ids,
                skill_match_score=skill_score,
                delay_minutes=int(delay)
            ))
            
            makespan = max(makespan, end_minutes)
        
        # Calculate resource utilization
        resource_utilization = self._calculate_resource_utilization(
            problem,
            task_assignments,
            task_resource_assignments
        )
        
        # Calculate feasibility score
        feasibility_score = 1.0
        if violations:
            error_violations = [v for v in violations if v.severity == "error"]
            if error_violations:
                feasibility_score = 0.0
            else:
                feasibility_score = max(0.0, 1.0 - len(violations) * 0.1)
        
        return OptimizationResult(
            status=status,
            objective_value=self.solver.Value(objective_var),
            solution_time_seconds=solution_time,
            task_assignments=task_assignments,
            makespan_hours=makespan / 60.0,
            total_delay_hours=total_delay / 60.0,
            resource_utilization=resource_utilization,
            constraint_violations=violations,
            feasibility_score=feasibility_score,
            solver_iterations=self.solver.NumBranches(),
            variables_count=len(task_vars) * 3,
            constraints_count=self.model.Proto().constraints.__len__()
        )
    
    def _calculate_resource_utilization(
        self,
        problem: SchedulingProblem,
        task_assignments: List[TaskAssignment],
        task_resource_assignments: Dict[UUID, UUID]
    ) -> Dict[UUID, float]:
        """Calculate utilization for each resource."""
        utilization = {}
        horizon_minutes = problem.horizon_minutes
        
        # Calculate machine utilization
        machine_usage = {}
        for assignment in task_assignments:
            if assignment.assigned_machine_id:
                machine_id = assignment.assigned_machine_id
                if machine_id not in machine_usage:
                    machine_usage[machine_id] = 0
                machine_usage[machine_id] += assignment.duration_minutes
        
        for machine_id in problem.machine_ids:
            usage = machine_usage.get(machine_id, 0)
            utilization[machine_id] = min(1.0, usage / horizon_minutes) if horizon_minutes > 0 else 0.0
        
        # Calculate operator utilization
        operator_usage = {}
        for assignment in task_assignments:
            for operator_id in assignment.assigned_operator_ids:
                if operator_id not in operator_usage:
                    operator_usage[operator_id] = 0
                operator_usage[operator_id] += assignment.duration_minutes
        
        for operator_id in problem.operator_ids:
            usage = operator_usage.get(operator_id, 0)
            utilization[operator_id] = min(1.0, usage / horizon_minutes) if horizon_minutes > 0 else 0.0
        
        return utilization
    
    def get_solution_statistics(self) -> Dict[str, float]:
        """Get detailed solver statistics."""
        if not self.solver:
            return {}
        
        return {
            "solution_time_seconds": self.solver.WallTime(),
            "objective_value": self.solver.ObjectiveValue(),
            "best_objective_bound": self.solver.BestObjectiveBound(),
            "num_branches": self.solver.NumBranches(),
            "num_conflicts": self.solver.NumConflicts(),
            "num_binary_propagations": self.solver.NumBinaryPropagations(),
            "num_integer_propagations": self.solver.NumIntegerPropagations()
        }