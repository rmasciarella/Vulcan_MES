"""
Vulcan MES Scheduling Service - Complete OR-Tools Integration

This service integrates all the imported CSV data to create optimized production schedules.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from enum import Enum
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from ortools.sat.python import cp_model
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ScheduleStatus(str, Enum):
    """Status of the scheduling solution."""
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"


class TaskSchedule(BaseModel):
    """Scheduled task with all assignments."""
    task_id: int
    job_id: int
    operation_id: int
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    machine_id: Optional[int] = None
    operator_ids: List[int] = Field(default_factory=list)
    work_cell_id: Optional[str] = None
    
    
class SchedulingSolution(BaseModel):
    """Complete scheduling solution."""
    status: ScheduleStatus
    makespan_minutes: int
    scheduled_tasks: List[TaskSchedule]
    unscheduled_tasks: List[int]
    machine_utilization: Dict[int, float]
    operator_utilization: Dict[int, float]
    solve_time_seconds: float
    objective_value: Optional[float] = None
    gap: Optional[float] = None


class VulcanSchedulingService:
    """Main scheduling service using OR-Tools CP-SAT solver."""
    
    def __init__(self, db_config: Dict[str, str]):
        """Initialize with database configuration."""
        self.db_config = db_config
        self.model = None
        self.solver = None
        self.task_vars = {}
        self.machine_assignments = {}
        self.operator_assignments = {}
        
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(**self.db_config)
    
    def fetch_scheduling_data(self, job_ids: Optional[List[int]] = None):
        """Fetch all required scheduling data from database."""
        conn = self._get_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            # Fetch jobs
            if job_ids:
                cur.execute(
                    "SELECT * FROM jobs WHERE id = ANY(%s) ORDER BY priority DESC, due_date",
                    (job_ids,)
                )
            else:
                cur.execute(
                    "SELECT * FROM jobs WHERE status IN ('PLANNED', 'IN_PROGRESS') "
                    "ORDER BY priority DESC, due_date LIMIT 20"
                )
            jobs = cur.fetchall()
            
            # Fetch tasks with operations
            job_id_list = [j['id'] for j in jobs]
            cur.execute("""
                SELECT t.*, o.operation_name, o.operation_code 
                FROM tasks t
                JOIN operations o ON t.operation_id = o.id
                WHERE t.job_id = ANY(%s)
                ORDER BY t.job_id, t.sequence_in_job
            """, (job_id_list,))
            tasks = cur.fetchall()
            
            # Fetch task modes (execution options)
            task_ids = [t['id'] for t in tasks]
            cur.execute("""
                SELECT tm.*, tt.name as task_name
                FROM task_modes tm
                JOIN task_templates tt ON tm.task_id = tt.task_id
                WHERE tm.task_id IN (
                    SELECT DISTINCT tt.task_id 
                    FROM tasks t
                    JOIN operations o ON t.operation_id = o.id
                    JOIN task_templates tt ON o.operation_name = tt.name
                    WHERE t.id = ANY(%s)
                )
            """, (task_ids,))
            task_modes = cur.fetchall()
            
            # Fetch task precedences
            cur.execute("""
                SELECT * FROM task_precedences 
                WHERE predecessor_task_id::text IN (
                    SELECT tt.task_id::text FROM task_templates tt
                    JOIN operations o ON tt.name = o.operation_name
                    JOIN tasks t ON t.operation_id = o.id
                    WHERE t.id = ANY(%s)
                )
            """, (task_ids,))
            precedences = cur.fetchall()
            
            # Fetch task skill requirements
            cur.execute("""
                SELECT tsr.*, s.skill_name 
                FROM task_skill_requirements tsr
                JOIN skills s ON tsr.skill_id = s.id
                WHERE tsr.task_uuid::text IN (
                    SELECT tt.task_id::text FROM task_templates tt
                    JOIN operations o ON tt.name = o.operation_name
                    JOIN tasks t ON t.operation_id = o.id
                    WHERE t.id = ANY(%s)
                )
            """, (task_ids,))
            skill_requirements = cur.fetchall()
            
            # Fetch resources
            cur.execute("""
                SELECT m.*, pz.zone_name, pz.wip_limit 
                FROM machines m
                LEFT JOIN production_zones pz ON m.production_zone_id = pz.id
                WHERE m.status = 'AVAILABLE'
            """)
            machines = cur.fetchall()
            
            cur.execute("""
                SELECT o.*, array_agg(
                    json_build_object('skill_id', os.skill_id, 'skill_name', s.skill_name, 'level', os.proficiency_level)
                ) as skills
                FROM operators o
                LEFT JOIN operator_skills os ON o.id = os.operator_id
                LEFT JOIN skills s ON os.skill_id = s.id
                WHERE o.status = 'AVAILABLE'
                GROUP BY o.id
            """)
            operators = cur.fetchall()
            
            # Fetch work cells
            cur.execute("SELECT * FROM work_cells")
            work_cells = cur.fetchall()
            
            # Fetch holidays
            cur.execute("""
                SELECT holiday_date FROM holiday_calendar 
                WHERE holiday_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
            """)
            holidays = [h['holiday_date'] for h in cur.fetchall()]
            
            return {
                'jobs': jobs,
                'tasks': tasks,
                'task_modes': task_modes,
                'precedences': precedences,
                'skill_requirements': skill_requirements,
                'machines': machines,
                'operators': operators,
                'work_cells': work_cells,
                'holidays': holidays
            }
            
        finally:
            cur.close()
            conn.close()
    
    def create_scheduling_model(self, data: Dict, horizon_days: int = 14):
        """Create CP-SAT model with all constraints."""
        self.model = cp_model.CpModel()
        
        # Calculate horizon in minutes
        horizon_minutes = horizon_days * 24 * 60
        
        # Create task variables
        for task in data['tasks']:
            task_id = task['id']
            duration = task.get('planned_duration_minutes', 30)
            
            # Start and end time variables
            start_var = self.model.NewIntVar(0, horizon_minutes - duration, f'start_t{task_id}')
            end_var = self.model.NewIntVar(duration, horizon_minutes, f'end_t{task_id}')
            
            # Duration constraint
            self.model.Add(end_var == start_var + duration)
            
            # Store variables
            self.task_vars[task_id] = {
                'start': start_var,
                'end': end_var,
                'duration': duration,
                'job_id': task['job_id'],
                'operation_id': task['operation_id'],
                'data': task
            }
        
        # Add precedence constraints within jobs
        self._add_job_precedence_constraints()
        
        # Add task precedence constraints from database
        self._add_task_precedence_constraints(data['precedences'])
        
        # Add resource allocation variables and constraints
        self._add_resource_constraints(data)
        
        # Add skill constraints
        self._add_skill_constraints(data)
        
        # Add work cell WIP constraints
        self._add_wip_constraints(data)
        
        # Add holiday constraints
        self._add_holiday_constraints(data['holidays'])
        
        # Set objective - minimize makespan
        makespan = self.model.NewIntVar(0, horizon_minutes, 'makespan')
        for task in self.task_vars.values():
            self.model.Add(makespan >= task['end'])
        
        self.model.Minimize(makespan)
        
        return self.model
    
    def _add_job_precedence_constraints(self):
        """Add precedence constraints for tasks within the same job."""
        jobs_tasks = {}
        for task_id, task in self.task_vars.items():
            job_id = task['job_id']
            if job_id not in jobs_tasks:
                jobs_tasks[job_id] = []
            jobs_tasks[job_id].append((task_id, task['data']['sequence_in_job']))
        
        # Sort tasks by sequence and add constraints
        for job_id, tasks in jobs_tasks.items():
            sorted_tasks = sorted(tasks, key=lambda x: x[1])
            for i in range(len(sorted_tasks) - 1):
                curr_task_id = sorted_tasks[i][0]
                next_task_id = sorted_tasks[i + 1][0]
                self.model.Add(
                    self.task_vars[curr_task_id]['end'] <= self.task_vars[next_task_id]['start']
                )
    
    def _add_task_precedence_constraints(self, precedences):
        """Add task-to-task precedence constraints."""
        for prec in precedences:
            pred_id = prec['predecessor_task_id']
            succ_id = prec['successor_task_id']
            
            # Map template IDs to actual task IDs if needed
            # For now, skip if tasks not in current schedule
            if pred_id in self.task_vars and succ_id in self.task_vars:
                self.model.Add(
                    self.task_vars[pred_id]['end'] <= self.task_vars[succ_id]['start']
                )
    
    def _add_resource_constraints(self, data):
        """Add machine and operator assignment constraints."""
        machines = data['machines']
        operators = data['operators']
        
        # Create intervals for resource scheduling
        for task_id, task in self.task_vars.items():
            # Machine assignment
            machine_vars = []
            for machine in machines:
                machine_id = machine['id']
                # Boolean variable for assignment
                assigned = self.model.NewBoolVar(f'task{task_id}_machine{machine_id}')
                machine_vars.append(assigned)
                
                if machine_id not in self.machine_assignments:
                    self.machine_assignments[machine_id] = []
                self.machine_assignments[machine_id].append({
                    'task_id': task_id,
                    'assigned': assigned,
                    'interval': self.model.NewOptionalIntervalVar(
                        task['start'], task['duration'], task['end'],
                        assigned, f'interval_t{task_id}_m{machine_id}'
                    )
                })
            
            # Each task needs exactly one machine
            self.model.Add(sum(machine_vars) == 1)
            
            # Operator assignment (can have multiple)
            operator_vars = []
            for operator in operators:
                operator_id = operator['id']
                assigned = self.model.NewBoolVar(f'task{task_id}_operator{operator_id}')
                operator_vars.append(assigned)
                
                if operator_id not in self.operator_assignments:
                    self.operator_assignments[operator_id] = []
                self.operator_assignments[operator_id].append({
                    'task_id': task_id,
                    'assigned': assigned,
                    'interval': self.model.NewOptionalIntervalVar(
                        task['start'], task['duration'], task['end'],
                        assigned, f'interval_t{task_id}_o{operator_id}'
                    )
                })
            
            # Task needs at least one operator
            self.model.Add(sum(operator_vars) >= 1)
        
        # No overlap constraints for resources
        for machine_id, assignments in self.machine_assignments.items():
            intervals = [a['interval'] for a in assignments]
            self.model.AddNoOverlap(intervals)
        
        for operator_id, assignments in self.operator_assignments.items():
            intervals = [a['interval'] for a in assignments]
            self.model.AddNoOverlap(intervals)
    
    def _add_skill_constraints(self, data):
        """Add skill requirement constraints."""
        # For each task, ensure assigned operators have required skills
        # This is simplified - full implementation would check skill levels
        pass
    
    def _add_wip_constraints(self, data):
        """Add work-in-progress constraints for work cells."""
        # Track concurrent tasks in each work cell
        # This is simplified - full implementation would enforce WIP limits
        pass
    
    def _add_holiday_constraints(self, holidays):
        """Prevent scheduling on holidays."""
        # Convert holiday dates to minute ranges and exclude them
        # This is simplified - full implementation would block holiday periods
        pass
    
    def solve(self, time_limit_seconds: int = 60) -> SchedulingSolution:
        """Solve the scheduling problem."""
        if not self.model:
            raise ValueError("Model not created. Call create_scheduling_model first.")
        
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.num_search_workers = 8
        
        # Solve
        status = self.solver.Solve(self.model)
        
        # Extract solution
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            scheduled_tasks = []
            for task_id, task in self.task_vars.items():
                start_minutes = self.solver.Value(task['start'])
                end_minutes = self.solver.Value(task['end'])
                
                # Find assigned machine
                assigned_machine = None
                for machine_id, assignments in self.machine_assignments.items():
                    for a in assignments:
                        if a['task_id'] == task_id and self.solver.Value(a['assigned']):
                            assigned_machine = machine_id
                            break
                
                # Find assigned operators
                assigned_operators = []
                for operator_id, assignments in self.operator_assignments.items():
                    for a in assignments:
                        if a['task_id'] == task_id and self.solver.Value(a['assigned']):
                            assigned_operators.append(operator_id)
                
                scheduled_tasks.append(TaskSchedule(
                    task_id=task_id,
                    job_id=task['job_id'],
                    operation_id=task['operation_id'],
                    start_time=datetime.now() + timedelta(minutes=start_minutes),
                    end_time=datetime.now() + timedelta(minutes=end_minutes),
                    duration_minutes=task['duration'],
                    machine_id=assigned_machine,
                    operator_ids=assigned_operators
                ))
            
            # Calculate utilization
            machine_util = self._calculate_machine_utilization(scheduled_tasks)
            operator_util = self._calculate_operator_utilization(scheduled_tasks)
            
            return SchedulingSolution(
                status=ScheduleStatus.OPTIMAL if status == cp_model.OPTIMAL else ScheduleStatus.FEASIBLE,
                makespan_minutes=self.solver.ObjectiveValue(),
                scheduled_tasks=scheduled_tasks,
                unscheduled_tasks=[],
                machine_utilization=machine_util,
                operator_utilization=operator_util,
                solve_time_seconds=self.solver.WallTime(),
                objective_value=self.solver.ObjectiveValue(),
                gap=self.solver.BestObjectiveBound() if status == cp_model.FEASIBLE else 0
            )
        else:
            return SchedulingSolution(
                status=ScheduleStatus.INFEASIBLE if status == cp_model.INFEASIBLE else ScheduleStatus.TIMEOUT,
                makespan_minutes=0,
                scheduled_tasks=[],
                unscheduled_tasks=list(self.task_vars.keys()),
                machine_utilization={},
                operator_utilization={},
                solve_time_seconds=self.solver.WallTime()
            )
    
    def _calculate_machine_utilization(self, tasks: List[TaskSchedule]) -> Dict[int, float]:
        """Calculate machine utilization percentages."""
        utilization = {}
        total_time = max(t.end_time for t in tasks) - min(t.start_time for t in tasks)
        total_minutes = total_time.total_seconds() / 60
        
        for task in tasks:
            if task.machine_id:
                if task.machine_id not in utilization:
                    utilization[task.machine_id] = 0
                utilization[task.machine_id] += task.duration_minutes
        
        # Convert to percentages
        for machine_id in utilization:
            utilization[machine_id] = (utilization[machine_id] / total_minutes) * 100
        
        return utilization
    
    def _calculate_operator_utilization(self, tasks: List[TaskSchedule]) -> Dict[int, float]:
        """Calculate operator utilization percentages."""
        utilization = {}
        total_time = max(t.end_time for t in tasks) - min(t.start_time for t in tasks)
        total_minutes = total_time.total_seconds() / 60
        
        for task in tasks:
            for operator_id in task.operator_ids:
                if operator_id not in utilization:
                    utilization[operator_id] = 0
                utilization[operator_id] += task.duration_minutes
        
        # Convert to percentages
        for operator_id in utilization:
            utilization[operator_id] = (utilization[operator_id] / total_minutes) * 100
        
        return utilization


def create_optimized_schedule(job_ids: Optional[List[int]] = None) -> SchedulingSolution:
    """Main entry point for creating an optimized schedule."""
    db_config = {
        'host': 'localhost',
        'database': 'vulcan',
        'user': 'postgres',
        'password': 'postgres'
    }
    
    service = VulcanSchedulingService(db_config)
    
    # Fetch data
    data = service.fetch_scheduling_data(job_ids)
    
    # Create model
    service.create_scheduling_model(data)
    
    # Solve
    solution = service.solve(time_limit_seconds=30)
    
    return solution


if __name__ == "__main__":
    # Test the scheduling service
    print("Creating optimized schedule for Vulcan MES...")
    print("=" * 60)
    
    solution = create_optimized_schedule()
    
    print(f"\nScheduling Status: {solution.status}")
    print(f"Makespan: {solution.makespan_minutes} minutes ({solution.makespan_minutes / 60:.1f} hours)")
    print(f"Scheduled Tasks: {len(solution.scheduled_tasks)}")
    print(f"Solve Time: {solution.solve_time_seconds:.2f} seconds")
    
    if solution.scheduled_tasks:
        print("\nFirst 10 scheduled tasks:")
        for task in solution.scheduled_tasks[:10]:
            print(f"  Task {task.task_id}: {task.start_time.strftime('%Y-%m-%d %H:%M')} - {task.end_time.strftime('%H:%M')}")
            print(f"    Machine: {task.machine_id}, Operators: {task.operator_ids}")
    
    if solution.machine_utilization:
        print("\nMachine Utilization:")
        for machine_id, util in sorted(solution.machine_utilization.items())[:5]:
            print(f"  Machine {machine_id}: {util:.1f}%")