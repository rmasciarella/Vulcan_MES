"""
Constraint programming models for scheduling optimization.

Defines constraint structures and optimization objectives for the CP-SAT solver
to handle complex scheduling scenarios with resource, temporal, and skill constraints.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field
from ortools.sat.python import cp_model


class ConstraintType(str, Enum):
    """Types of constraints in the scheduling problem."""
    RESOURCE_CAPACITY = "resource_capacity"
    TEMPORAL_PRECEDENCE = "temporal_precedence"
    SKILL_REQUIREMENT = "skill_requirement"
    MACHINE_AVAILABILITY = "machine_availability"
    OPERATOR_AVAILABILITY = "operator_availability"
    SETUP_TIME = "setup_time"
    NO_OVERLAP = "no_overlap"


class OptimizationObjective(str, Enum):
    """Optimization objectives for the scheduler."""
    MINIMIZE_MAKESPAN = "minimize_makespan"
    MINIMIZE_TOTAL_DELAY = "minimize_total_delay"
    MAXIMIZE_UTILIZATION = "maximize_utilization"
    MINIMIZE_COST = "minimize_cost"
    BALANCE_WORKLOAD = "balance_workload"


class ResourceConstraints(BaseModel):
    """Resource capacity and availability constraints."""
    
    # Machine constraints
    machine_capacities: Dict[UUID, int] = Field(default_factory=dict)  # machine_id -> capacity
    machine_availability_windows: Dict[UUID, List[Tuple[int, int]]] = Field(default_factory=dict)  # time windows
    machine_setup_times: Dict[Tuple[UUID, str, str], int] = Field(default_factory=dict)  # (machine, from_task_type, to_task_type) -> minutes
    
    # Operator constraints
    operator_capacities: Dict[UUID, int] = Field(default_factory=dict)  # operator_id -> max concurrent tasks
    operator_availability_windows: Dict[UUID, List[Tuple[int, int]]] = Field(default_factory=dict)
    operator_skill_levels: Dict[Tuple[UUID, str], int] = Field(default_factory=dict)  # (operator_id, skill_code) -> level
    
    # Department constraints
    department_capacity_limits: Dict[str, int] = Field(default_factory=dict)
    
    def add_machine_constraint(
        self,
        machine_id: UUID,
        capacity: int = 1,
        availability_windows: Optional[List[Tuple[int, int]]] = None
    ) -> None:
        """Add machine capacity and availability constraints."""
        self.machine_capacities[machine_id] = capacity
        if availability_windows:
            self.machine_availability_windows[machine_id] = availability_windows
    
    def add_operator_constraint(
        self,
        operator_id: UUID,
        capacity: int = 1,
        availability_windows: Optional[List[Tuple[int, int]]] = None,
        skills: Optional[Dict[str, int]] = None
    ) -> None:
        """Add operator capacity, availability, and skill constraints."""
        self.operator_capacities[operator_id] = capacity
        if availability_windows:
            self.operator_availability_windows[operator_id] = availability_windows
        if skills:
            for skill_code, level in skills.items():
                self.operator_skill_levels[(operator_id, skill_code)] = level
    
    def add_setup_time(
        self,
        machine_id: UUID,
        from_task_type: str,
        to_task_type: str,
        setup_minutes: int
    ) -> None:
        """Add setup time constraint between task types on a machine."""
        self.machine_setup_times[(machine_id, from_task_type, to_task_type)] = setup_minutes


class TemporalConstraints(BaseModel):
    """Temporal relationships and timing constraints."""
    
    # Task precedence relationships
    precedence_constraints: List[Tuple[UUID, UUID]] = Field(default_factory=list)  # (predecessor, successor)
    
    # Time window constraints
    task_earliest_start: Dict[UUID, int] = Field(default_factory=dict)  # task_id -> minutes from epoch
    task_latest_end: Dict[UUID, int] = Field(default_factory=dict)  # task_id -> minutes from epoch
    
    # Duration constraints
    task_durations: Dict[UUID, int] = Field(default_factory=dict)  # task_id -> duration in minutes
    task_min_durations: Dict[UUID, int] = Field(default_factory=dict)
    task_max_durations: Dict[UUID, int] = Field(default_factory=dict)
    
    # Delay penalties
    delay_penalties: Dict[UUID, float] = Field(default_factory=dict)  # task_id -> penalty per minute
    
    def add_precedence(self, predecessor_id: UUID, successor_id: UUID) -> None:
        """Add precedence constraint between two tasks."""
        self.precedence_constraints.append((predecessor_id, successor_id))
    
    def add_time_window(
        self,
        task_id: UUID,
        earliest_start: datetime,
        latest_end: datetime,
        reference_time: datetime
    ) -> None:
        """Add time window constraint for a task."""
        earliest_minutes = int((earliest_start - reference_time).total_seconds() / 60)
        latest_minutes = int((latest_end - reference_time).total_seconds() / 60)
        
        self.task_earliest_start[task_id] = earliest_minutes
        self.task_latest_end[task_id] = latest_minutes
    
    def add_duration_constraint(
        self,
        task_id: UUID,
        duration_minutes: int,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None
    ) -> None:
        """Add duration constraints for a task."""
        self.task_durations[task_id] = duration_minutes
        if min_duration is not None:
            self.task_min_durations[task_id] = min_duration
        if max_duration is not None:
            self.task_max_durations[task_id] = max_duration


class SkillConstraints(BaseModel):
    """Skill-based assignment constraints."""
    
    # Required skills per task
    task_skill_requirements: Dict[UUID, List[Tuple[str, int]]] = Field(default_factory=dict)  # task_id -> [(skill, min_level)]
    
    # Operator skill certifications
    operator_skills: Dict[UUID, Dict[str, int]] = Field(default_factory=dict)  # operator_id -> {skill: level}
    
    # Skill preference weights (for optimization)
    skill_preference_weights: Dict[Tuple[UUID, UUID, str], float] = Field(default_factory=dict)  # (task_id, operator_id, skill) -> weight
    
    # Cross-training constraints
    cross_training_bonuses: Dict[Tuple[UUID, str], float] = Field(default_factory=dict)  # (operator_id, skill) -> bonus
    
    def add_task_skill_requirement(
        self,
        task_id: UUID,
        required_skills: List[Tuple[str, int]]
    ) -> None:
        """Add skill requirements for a task."""
        self.task_skill_requirements[task_id] = required_skills
    
    def add_operator_skills(
        self,
        operator_id: UUID,
        skills: Dict[str, int]
    ) -> None:
        """Add skill certifications for an operator."""
        self.operator_skills[operator_id] = skills
    
    def can_operator_perform_task(
        self,
        operator_id: UUID,
        task_id: UUID
    ) -> bool:
        """Check if operator has required skills for task."""
        task_requirements = self.task_skill_requirements.get(task_id, [])
        operator_skills = self.operator_skills.get(operator_id, {})
        
        for skill_code, min_level in task_requirements:
            if operator_skills.get(skill_code, 0) < min_level:
                return False
        
        return True
    
    def get_skill_match_score(
        self,
        operator_id: UUID,
        task_id: UUID
    ) -> float:
        """Calculate skill match score for operator-task assignment."""
        task_requirements = self.task_skill_requirements.get(task_id, [])
        operator_skills = self.operator_skills.get(operator_id, {})
        
        if not task_requirements:
            return 1.0
        
        total_score = 0.0
        for skill_code, min_level in task_requirements:
            operator_level = operator_skills.get(skill_code, 0)
            if operator_level >= min_level:
                # Bonus for exceeding minimum requirement
                score = 1.0 + (operator_level - min_level) * 0.1
                total_score += score
            else:
                # Penalty for not meeting requirement
                return 0.0
        
        return total_score / len(task_requirements)


class ConstraintViolation(BaseModel):
    """Represents a constraint violation in the scheduling problem."""
    
    constraint_type: ConstraintType
    severity: str = "error"  # error, warning, info
    description: str
    affected_entities: List[UUID] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
    impact_score: float = Field(ge=0.0, default=1.0)


class ConstraintValidator:
    """Validates constraints and identifies potential conflicts."""
    
    def __init__(
        self,
        resource_constraints: ResourceConstraints,
        temporal_constraints: TemporalConstraints,
        skill_constraints: SkillConstraints
    ):
        self.resource_constraints = resource_constraints
        self.temporal_constraints = temporal_constraints
        self.skill_constraints = skill_constraints
    
    def validate_all_constraints(
        self,
        task_ids: List[UUID],
        machine_ids: List[UUID],
        operator_ids: List[UUID]
    ) -> List[ConstraintViolation]:
        """Validate all constraints and return violations."""
        violations = []
        
        # Validate resource constraints
        violations.extend(self._validate_resource_constraints(task_ids, machine_ids, operator_ids))
        
        # Validate temporal constraints
        violations.extend(self._validate_temporal_constraints(task_ids))
        
        # Validate skill constraints  
        violations.extend(self._validate_skill_constraints(task_ids, operator_ids))
        
        return violations
    
    def _validate_resource_constraints(
        self,
        task_ids: List[UUID],
        machine_ids: List[UUID],
        operator_ids: List[UUID]
    ) -> List[ConstraintViolation]:
        """Validate resource capacity and availability constraints."""
        violations = []
        
        # Check machine capacity
        for machine_id in machine_ids:
            if machine_id not in self.resource_constraints.machine_capacities:
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.RESOURCE_CAPACITY,
                    description=f"Machine {machine_id} has no capacity defined",
                    affected_entities=[machine_id],
                    suggested_fix="Define machine capacity in resource constraints"
                ))
        
        # Check operator capacity
        for operator_id in operator_ids:
            if operator_id not in self.resource_constraints.operator_capacities:
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.RESOURCE_CAPACITY,
                    description=f"Operator {operator_id} has no capacity defined",
                    affected_entities=[operator_id],
                    suggested_fix="Define operator capacity in resource constraints"
                ))
        
        return violations
    
    def _validate_temporal_constraints(self, task_ids: List[UUID]) -> List[ConstraintViolation]:
        """Validate temporal and precedence constraints."""
        violations = []
        
        # Check for circular dependencies in precedence
        precedence_graph = {}
        for predecessor, successor in self.temporal_constraints.precedence_constraints:
            if predecessor not in precedence_graph:
                precedence_graph[predecessor] = []
            precedence_graph[predecessor].append(successor)
        
        # Detect cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: UUID) -> bool:
            if node in rec_stack:
                return True
            if node in visited:
                return False
                
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in precedence_graph.get(node, []):
                if has_cycle(neighbor):
                    return True
            
            rec_stack.remove(node)
            return False
        
        for task_id in task_ids:
            if task_id not in visited and has_cycle(task_id):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.TEMPORAL_PRECEDENCE,
                    description="Circular dependency detected in task precedence",
                    affected_entities=[task_id],
                    suggested_fix="Review and remove circular dependencies",
                    impact_score=5.0
                ))
        
        # Check time window feasibility
        for task_id in task_ids:
            earliest = self.temporal_constraints.task_earliest_start.get(task_id)
            latest = self.temporal_constraints.task_latest_end.get(task_id) 
            duration = self.temporal_constraints.task_durations.get(task_id)
            
            if earliest is not None and latest is not None and duration is not None:
                if earliest + duration > latest:
                    violations.append(ConstraintViolation(
                        constraint_type=ConstraintType.TEMPORAL_PRECEDENCE,
                        description=f"Task {task_id} time window too narrow for required duration",
                        affected_entities=[task_id],
                        suggested_fix="Expand time window or reduce task duration",
                        impact_score=3.0
                    ))
        
        return violations
    
    def _validate_skill_constraints(
        self,
        task_ids: List[UUID],
        operator_ids: List[UUID]
    ) -> List[ConstraintViolation]:
        """Validate skill requirement and capability constraints."""
        violations = []
        
        # Check if tasks have operators who can perform them
        for task_id in task_ids:
            task_requirements = self.skill_constraints.task_skill_requirements.get(task_id, [])
            if not task_requirements:
                continue
            
            capable_operators = []
            for operator_id in operator_ids:
                if self.skill_constraints.can_operator_perform_task(operator_id, task_id):
                    capable_operators.append(operator_id)
            
            if not capable_operators:
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.SKILL_REQUIREMENT,
                    description=f"Task {task_id} has no capable operators",
                    affected_entities=[task_id],
                    suggested_fix="Train operators or modify task requirements",
                    impact_score=4.0
                ))
        
        return violations


class CPSATConstraintBuilder:
    """Builds CP-SAT constraints from domain constraint models."""
    
    def __init__(self, model: cp_model.CpModel):
        self.model = model
        self.variables = {}  # Store created variables
    
    def create_task_variables(
        self,
        task_ids: List[UUID],
        horizon: int,
        durations: Dict[UUID, int]
    ) -> Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]]:
        """Create start, end, and interval variables for tasks."""
        task_vars = {}
        
        for task_id in task_ids:
            duration = durations.get(task_id, 60)  # Default 1 hour
            
            start_var = self.model.NewIntVar(0, horizon, f'start_{task_id}')
            end_var = self.model.NewIntVar(0, horizon, f'end_{task_id}')
            interval_var = self.model.NewIntervalVar(start_var, duration, end_var, f'interval_{task_id}')
            
            task_vars[task_id] = (start_var, end_var, interval_var)
        
        return task_vars
    
    def add_resource_constraints(
        self,
        task_vars: Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]],
        resource_constraints: ResourceConstraints,
        task_assignments: Dict[UUID, UUID]  # task_id -> resource_id
    ) -> None:
        """Add resource capacity constraints to the model."""
        
        # Group tasks by assigned resource
        resource_tasks = {}
        for task_id, resource_id in task_assignments.items():
            if resource_id not in resource_tasks:
                resource_tasks[resource_id] = []
            resource_tasks[resource_id].append(task_id)
        
        # Add no-overlap constraints for each resource
        for resource_id, assigned_tasks in resource_tasks.items():
            if len(assigned_tasks) > 1:
                intervals = [task_vars[task_id][2] for task_id in assigned_tasks]
                self.model.AddNoOverlap(intervals)
    
    def add_temporal_constraints(
        self,
        task_vars: Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]],
        temporal_constraints: TemporalConstraints
    ) -> None:
        """Add temporal and precedence constraints to the model."""
        
        # Add precedence constraints
        for predecessor_id, successor_id in temporal_constraints.precedence_constraints:
            if predecessor_id in task_vars and successor_id in task_vars:
                pred_end = task_vars[predecessor_id][1]  # end variable
                succ_start = task_vars[successor_id][0]  # start variable
                self.model.Add(pred_end <= succ_start)
        
        # Add time window constraints
        for task_id, (start_var, end_var, _) in task_vars.items():
            earliest_start = temporal_constraints.task_earliest_start.get(task_id)
            latest_end = temporal_constraints.task_latest_end.get(task_id)
            
            if earliest_start is not None:
                self.model.Add(start_var >= earliest_start)
            
            if latest_end is not None:
                self.model.Add(end_var <= latest_end)
    
    def add_skill_constraints(
        self,
        task_vars: Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]],
        skill_constraints: SkillConstraints,
        task_operator_assignments: Dict[UUID, UUID]  # task_id -> operator_id
    ) -> List[ConstraintViolation]:
        """Add skill-based assignment constraints and return violations."""
        violations = []
        
        for task_id, operator_id in task_operator_assignments.items():
            if not skill_constraints.can_operator_perform_task(operator_id, task_id):
                violations.append(ConstraintViolation(
                    constraint_type=ConstraintType.SKILL_REQUIREMENT,
                    description=f"Operator {operator_id} cannot perform task {task_id}",
                    affected_entities=[task_id, operator_id],
                    impact_score=5.0
                ))
        
        return violations
    
    def create_optimization_objective(
        self,
        task_vars: Dict[UUID, Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntervalVar]],
        objective_type: OptimizationObjective,
        weights: Optional[Dict[str, float]] = None
    ) -> cp_model.IntVar:
        """Create optimization objective based on type."""
        weights = weights or {}
        
        if objective_type == OptimizationObjective.MINIMIZE_MAKESPAN:
            # Minimize maximum end time
            makespan = self.model.NewIntVar(0, 10000, 'makespan')
            for task_id, (_, end_var, _) in task_vars.items():
                self.model.Add(makespan >= end_var)
            return makespan
        
        elif objective_type == OptimizationObjective.MINIMIZE_TOTAL_DELAY:
            # Minimize sum of delays from planned times
            total_delay = self.model.NewIntVar(0, 100000, 'total_delay')
            delay_vars = []
            
            for task_id, (start_var, _, _) in task_vars.items():
                planned_start = weights.get(f'planned_start_{task_id}', 0)
                delay = self.model.NewIntVar(0, 10000, f'delay_{task_id}')
                self.model.Add(delay >= start_var - planned_start)
                delay_vars.append(delay)
            
            self.model.Add(total_delay == sum(delay_vars))
            return total_delay
        
        else:
            # Default to makespan minimization
            return self.create_optimization_objective(
                task_vars, OptimizationObjective.MINIMIZE_MAKESPAN, weights
            )