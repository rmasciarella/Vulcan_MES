#!/usr/bin/env python3
"""
Hybrid Flexible Flow Shop Scheduler with Multi-Skill Workforce Constraints
Using Google OR-Tools CP-SAT Solver

This implementation follows verified OR-Tools patterns from official documentation
and examples, particularly flexible_job_shop_sat.py and shift_scheduling_sat.py
"""

import collections
import time
from typing import Any

from ortools.sat.python import cp_model  # type: ignore[import-not-found]


class HFFSScheduler:
    def __init__(self) -> None:
        """Initialize the Hybrid Flexible Flow Shop scheduling problem"""

        # Problem dimensions
        self.num_jobs: int = 5
        self.num_tasks: int = 100  # Per job
        self.num_operators: int = 10
        self.horizon_days: int = 30
        self.horizon: int = self.horizon_days * 24 * 60  # Total minutes

        # Time constants
        self.minutes_per_day: int = 24 * 60
        self.work_start: int = 7 * 60  # 7am in minutes from midnight
        self.work_end: int = 16 * 60  # 4pm in minutes from midnight
        self.lunch_start: int = 12 * 60  # Noon
        self.lunch_duration: int = 45  # 45 minutes

        # Holidays (days 5, 12, 26)
        self.holidays: set[int] = {5, 12, 26}

        # Due dates in minutes
        self.due_dates: dict[int, int] = {
            0: 10 * 24 * 60,  # 10 days
            1: 12 * 24 * 60,  # 12 days
            2: 8 * 24 * 60,  # 8 days
            3: 15 * 24 * 60,  # 15 days
            4: 11 * 24 * 60,  # 11 days
        }

        # Define operator skills (level 1-3)
        # Skills: welding, machining, inspection, assembly, programming
        self.operator_skills: dict[int, dict[str, int]] = {
            0: {
                "welding": 3,
                "machining": 2,
                "inspection": 1,
                "assembly": 2,
                "programming": 1,
            },
            1: {
                "welding": 2,
                "machining": 3,
                "inspection": 2,
                "assembly": 1,
                "programming": 2,
            },
            2: {
                "welding": 1,
                "machining": 2,
                "inspection": 3,
                "assembly": 2,
                "programming": 1,
            },
            3: {
                "welding": 2,
                "machining": 1,
                "inspection": 2,
                "assembly": 3,
                "programming": 2,
            },
            4: {
                "welding": 1,
                "machining": 2,
                "inspection": 1,
                "assembly": 2,
                "programming": 3,
            },
            5: {
                "welding": 3,
                "machining": 1,
                "inspection": 2,
                "assembly": 1,
                "programming": 2,
            },
            6: {
                "welding": 2,
                "machining": 3,
                "inspection": 1,
                "assembly": 2,
                "programming": 1,
            },
            7: {
                "welding": 1,
                "machining": 2,
                "inspection": 3,
                "assembly": 1,
                "programming": 2,
            },
            8: {
                "welding": 2,
                "machining": 1,
                "inspection": 2,
                "assembly": 3,
                "programming": 1,
            },
            9: {
                "welding": 1,
                "machining": 2,
                "inspection": 1,
                "assembly": 2,
                "programming": 3,
            },
        }

        # Operator cost per minute based on highest skill level
        self.operator_costs: dict[int, int] = {}
        for op_id, skills in self.operator_skills.items():
            max_skill = max(skills.values())
            self.operator_costs[op_id] = 2 * max_skill  # $2 per skill level per minute

        # Define task requirements
        self.task_requirements: dict[int, tuple[str, int]] = {}
        for task_id in range(self.num_tasks):
            if task_id < 20:
                self.task_requirements[task_id] = ("welding", 2)
            elif task_id < 40:
                self.task_requirements[task_id] = ("machining", 2)
            elif task_id < 60:
                self.task_requirements[task_id] = ("assembly", 1)
            elif task_id < 80:
                self.task_requirements[task_id] = ("inspection", 2)
            else:
                self.task_requirements[task_id] = ("programming", 1)

        # Tasks requiring 2 operators (every 15th task)
        self.two_operator_tasks: set[int] = {14, 29, 44, 59, 74, 89}

        # Critical sequences (tasks within these ranges maintain strict job priority)
        self.critical_sequences: list[tuple[int, int]] = [
            (20, 28),  # Critical welding
            (35, 42),  # Critical machining
            (60, 65),  # Critical assembly
            (85, 92),  # Critical inspection
        ]

        # WIP limits by zone
        self.wip_zones: list[tuple[int, int, int]] = [
            (0, 30, 3),  # Tasks 0-30: max 3 jobs
            (31, 60, 2),  # Tasks 31-60: max 2 jobs (bottleneck)
            (61, 99, 3),  # Tasks 61-99: max 3 jobs
        ]

    def get_task_duration_and_setup(self, task_id: int) -> list[tuple[int, int]]:
        """Get processing and setup times for a task"""
        # Every 10th task has flexible routing
        if (task_id + 1) % 10 == 0:
            # Two machine options with different times
            return [
                (120, 15),  # Option A: 120 min processing + 15 min setup
                (90, 20),  # Option B: 90 min processing + 20 min setup
            ]
        else:
            # Single machine option
            return [(60, 10)]  # 60 min processing + 10 min setup

    def is_attended_machine(self, task_id: int) -> bool:
        """Check if machine requires operator for entire duration"""
        # Every 5th task (4, 9, 14, ...) is unattended after setup
        return (task_id + 1) % 5 != 0

    def get_eligible_operators(self, task_id: int) -> list[int]:
        """Get operators qualified for a task based on skill requirements"""
        skill_type, min_level = self.task_requirements[task_id]
        eligible = []
        for op_id, skills in self.operator_skills.items():
            if skills[skill_type] >= min_level:
                eligible.append(op_id)
        return eligible

    def create_model(
        self,
    ) -> tuple[
        cp_model.CpModel,
        cp_model.IntVar,
        dict[tuple[int, int, int], cp_model.IntVar],
        dict[tuple[int, int, int], cp_model.IntVar],
        dict[tuple[int, int, int], cp_model.IntVar],
        dict[tuple[int, int, int, int], cp_model.IntVar],
        dict[int, cp_model.IntVar],
        dict[int, cp_model.IntVar],
        cp_model.IntVar,
    ]:
        """Create the CP-SAT model with all constraints"""
        model = cp_model.CpModel()

        # Storage for variables
        task_starts = {}
        task_ends = {}
        task_presences = {}  # For optional intervals (flexible routing)
        task_intervals = {}
        task_operators = {}  # Which operator(s) assigned to each task
        operator_intervals = collections.defaultdict(list)  # Intervals per operator
        machine_intervals = collections.defaultdict(list)  # Intervals per machine

        print("Creating variables for jobs and tasks...")

        # Create variables for each job and task
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks):
                task_options = self.get_task_duration_and_setup(task_id)
                num_options = len(task_options)

                if num_options == 1:
                    # Single machine option (90% of tasks)
                    processing_time, setup_time = task_options[0]
                    total_duration = processing_time + setup_time

                    # Create start and end variables
                    start_var = model.NewIntVar(
                        0, self.horizon, f"start_j{job_id}_t{task_id}"
                    )
                    end_var = model.NewIntVar(
                        0, self.horizon, f"end_j{job_id}_t{task_id}"
                    )

                    # Create interval
                    interval_var = model.NewIntervalVar(
                        start_var,
                        total_duration,
                        end_var,
                        f"interval_j{job_id}_t{task_id}",
                    )

                    task_starts[(job_id, task_id, 0)] = start_var
                    task_ends[(job_id, task_id, 0)] = end_var
                    task_intervals[(job_id, task_id, 0)] = interval_var
                    task_presences[(job_id, task_id, 0)] = model.NewConstant(1)

                    # Add to machine list (single machine for this task)
                    machine_id = task_id  # Simple mapping for non-flexible tasks
                    machine_intervals[machine_id].append(interval_var)

                else:
                    # Flexible routing (every 10th task)
                    option_presences = []

                    for option_id, (processing_time, setup_time) in enumerate(
                        task_options
                    ):
                        total_duration = processing_time + setup_time

                        # Create variables for this option
                        start_var = model.NewIntVar(
                            0, self.horizon, f"start_j{job_id}_t{task_id}_o{option_id}"
                        )
                        end_var = model.NewIntVar(
                            0, self.horizon, f"end_j{job_id}_t{task_id}_o{option_id}"
                        )
                        presence_var = model.NewBoolVar(
                            f"presence_j{job_id}_t{task_id}_o{option_id}"
                        )

                        # Create optional interval (OR-Tools pattern from flexible_job_shop_sat.py)
                        interval_var = model.NewOptionalIntervalVar(
                            start_var,
                            total_duration,
                            end_var,
                            presence_var,
                            f"interval_j{job_id}_t{task_id}_o{option_id}",
                        )

                        task_starts[(job_id, task_id, option_id)] = start_var
                        task_ends[(job_id, task_id, option_id)] = end_var
                        task_presences[(job_id, task_id, option_id)] = presence_var
                        task_intervals[(job_id, task_id, option_id)] = interval_var
                        option_presences.append(presence_var)

                        # Add to appropriate machine list
                        machine_id = (
                            task_id * 10 + option_id
                        )  # Unique machine ID for flexible tasks
                        machine_intervals[machine_id].append(interval_var)

                    # Exactly one option must be selected (OR-Tools pattern)
                    model.AddExactlyOne(option_presences)

        print("Adding precedence constraints within jobs...")

        # Precedence constraints between consecutive tasks in each job
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks - 1):
                current_options = len(self.get_task_duration_and_setup(task_id))
                next_options = len(self.get_task_duration_and_setup(task_id + 1))

                # For all combinations of current and next task options
                for curr_opt in range(current_options):
                    for next_opt in range(next_options):
                        # Next task starts after current task ends
                        model.Add(
                            task_starts[(job_id, task_id + 1, next_opt)]
                            >= task_ends[(job_id, task_id, curr_opt)]
                        ).OnlyEnforceIf(
                            [
                                task_presences[(job_id, task_id, curr_opt)],
                                task_presences[(job_id, task_id + 1, next_opt)],
                            ]
                        )

        print("Adding NoOverlap constraints for machines...")

        # NoOverlap constraint for each machine (OR-Tools pattern)
        for machine_id, intervals in machine_intervals.items():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)

        print("Adding operator assignment variables and constraints...")

        # Create operator assignment variables
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks):
                eligible_ops = self.get_eligible_operators(task_id)
                num_ops_needed = 2 if task_id in self.two_operator_tasks else 1

                # For each machine option
                for option_id in range(len(self.get_task_duration_and_setup(task_id))):
                    if num_ops_needed == 1:
                        # Single operator assignment
                        op_var = model.NewIntVarFromDomain(
                            cp_model.Domain.FromValues(eligible_ops),
                            f"op_j{job_id}_t{task_id}_o{option_id}",
                        )
                        task_operators[(job_id, task_id, option_id, 0)] = op_var
                    else:
                        # Two operators needed
                        for op_num in range(2):
                            op_var = model.NewIntVarFromDomain(
                                cp_model.Domain.FromValues(eligible_ops),
                                f"op{op_num}_j{job_id}_t{task_id}_o{option_id}",
                            )
                            task_operators[(job_id, task_id, option_id, op_num)] = (
                                op_var
                            )

                        # Ensure different operators
                        model.Add(
                            task_operators[(job_id, task_id, option_id, 0)]
                            != task_operators[(job_id, task_id, option_id, 1)]
                        ).OnlyEnforceIf(task_presences[(job_id, task_id, option_id)])

        print("Adding operator availability constraints...")

        # Create operator intervals for NoOverlap
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks):
                is_attended = self.is_attended_machine(task_id)

                for option_id in range(len(self.get_task_duration_and_setup(task_id))):
                    if (job_id, task_id, option_id) not in task_presences:
                        continue

                    presence = task_presences[(job_id, task_id, option_id)]
                    start = task_starts[(job_id, task_id, option_id)]

                    if is_attended:
                        # Operator needed for entire duration
                        duration = sum(
                            self.get_task_duration_and_setup(task_id)[option_id]
                        )
                    else:
                        # Operator only needed for setup
                        _, setup_time = self.get_task_duration_and_setup(task_id)[
                            option_id
                        ]
                        duration = setup_time

                    # For each operator that could be assigned
                    num_ops_needed = 2 if task_id in self.two_operator_tasks else 1
                    for op_num in range(num_ops_needed):
                        for op_id in self.get_eligible_operators(task_id):
                            # Create conditional interval for this operator
                            op_assigned = model.NewBoolVar(
                                f"op{op_id}_assigned_j{job_id}_t{task_id}_o{option_id}_n{op_num}"
                            )

                            # Link assignment variable to boolean
                            model.Add(
                                task_operators[(job_id, task_id, option_id, op_num)]
                                == op_id
                            ).OnlyEnforceIf(op_assigned)

                            # Create interval only if operator assigned and option selected
                            op_interval = model.NewOptionalIntervalVar(
                                start,
                                duration,
                                start + duration,
                                op_assigned,
                                f"op{op_id}_interval_j{job_id}_t{task_id}_o{option_id}_n{op_num}",
                            )
                            operator_intervals[op_id].append(op_interval)

                            # Link to task presence
                            model.AddImplication(op_assigned, presence)

        # NoOverlap for each operator
        for op_id, intervals in operator_intervals.items():
            if len(intervals) > 1:
                model.AddNoOverlap(intervals)

        print("Adding business hours constraints for attended operations...")

        # Business hours constraints for attended operations
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks):
                if self.is_attended_machine(task_id):
                    for option_id in range(
                        len(self.get_task_duration_and_setup(task_id))
                    ):
                        if (job_id, task_id, option_id) not in task_starts:
                            continue

                        start = task_starts[(job_id, task_id, option_id)]
                        task_ends[(job_id, task_id, option_id)]
                        presence = task_presences[(job_id, task_id, option_id)]

                        # Calculate day and time within day
                        start_day = model.NewIntVar(
                            0,
                            self.horizon_days,
                            f"start_day_j{job_id}_t{task_id}_o{option_id}",
                        )
                        start_time = model.NewIntVar(
                            0,
                            self.minutes_per_day - 1,
                            f"start_time_j{job_id}_t{task_id}_o{option_id}",
                        )

                        model.AddDivisionEquality(
                            start_day, start, self.minutes_per_day
                        )
                        model.AddModuloEquality(start_time, start, self.minutes_per_day)

                        # Must start and end within work hours (not on holidays)
                        for day in self.holidays:
                            model.Add(start_day != day).OnlyEnforceIf(presence)

                        # Must be within work hours
                        model.Add(start_time >= self.work_start).OnlyEnforceIf(presence)
                        model.Add(
                            start_time
                            + sum(self.get_task_duration_and_setup(task_id)[option_id])
                            <= self.work_end
                        ).OnlyEnforceIf(presence)

                        # Cannot overlap lunch break
                        # Either finish before lunch or start after lunch
                        before_lunch = model.NewBoolVar(
                            f"before_lunch_j{job_id}_t{task_id}_o{option_id}"
                        )
                        model.Add(
                            start_time
                            + sum(self.get_task_duration_and_setup(task_id)[option_id])
                            <= self.lunch_start
                        ).OnlyEnforceIf(before_lunch)
                        model.Add(
                            start_time >= self.lunch_start + self.lunch_duration
                        ).OnlyEnforceIf(before_lunch.Not())
                        model.AddBoolOr(
                            [before_lunch, before_lunch.Not()]
                        ).OnlyEnforceIf(presence)

        print("Adding critical sequence constraints...")

        # Critical sequence constraints (cross-job precedence)
        for start_task, end_task in self.critical_sequences:
            for job_id in range(self.num_jobs - 1):
                # Job j+1 cannot enter critical sequence until job j exits
                for j_opt in range(len(self.get_task_duration_and_setup(end_task))):
                    for j1_opt in range(
                        len(self.get_task_duration_and_setup(start_task))
                    ):
                        model.Add(
                            task_starts[(job_id + 1, start_task, j1_opt)]
                            >= task_ends[(job_id, end_task, j_opt)]
                        ).OnlyEnforceIf(
                            [
                                task_presences[(job_id, end_task, j_opt)],
                                task_presences[(job_id + 1, start_task, j1_opt)],
                            ]
                        )

        print("Adding WIP constraints by zone...")

        # WIP constraints by zone
        for zone_start, zone_end, max_wip in self.wip_zones:
            # For each time point, count active jobs in zone
            # Simplified approach: ensure no more than max_wip jobs can be in zone simultaneously
            zone_jobs = []
            for job_id in range(self.num_jobs):
                # Job is in zone if any task in zone range is active
                in_zone = model.NewBoolVar(
                    f"job{job_id}_in_zone_{zone_start}_{zone_end}"
                )

                # Job enters zone at start of first task in range
                zone_entry = model.NewIntVar(
                    0, self.horizon, f"job{job_id}_enter_zone_{zone_start}"
                )
                zone_exit = model.NewIntVar(
                    0, self.horizon, f"job{job_id}_exit_zone_{zone_end}"
                )

                # Link to actual task times
                for opt in range(len(self.get_task_duration_and_setup(zone_start))):
                    model.Add(
                        zone_entry <= task_starts[(job_id, zone_start, opt)]
                    ).OnlyEnforceIf(task_presences[(job_id, zone_start, opt)])

                for opt in range(len(self.get_task_duration_and_setup(zone_end))):
                    model.Add(
                        zone_exit >= task_ends[(job_id, zone_end, opt)]
                    ).OnlyEnforceIf(task_presences[(job_id, zone_end, opt)])

                zone_jobs.append((zone_entry, zone_exit, in_zone))

            # Ensure at most max_wip jobs overlap in zone
            # This is a simplified constraint - full implementation would check all time points
            for i in range(self.num_jobs):
                for j in range(i + 1, self.num_jobs):
                    for k in range(j + 1, self.num_jobs):
                        if max_wip < 3:
                            # These three jobs cannot all be in zone simultaneously
                            overlap_ij = model.NewBoolVar(
                                f"overlap_{i}_{j}_zone_{zone_start}"
                            )
                            overlap_jk = model.NewBoolVar(
                                f"overlap_{j}_{k}_zone_{zone_start}"
                            )
                            overlap_ik = model.NewBoolVar(
                                f"overlap_{i}_{k}_zone_{zone_start}"
                            )

                            # Define overlaps
                            model.Add(zone_jobs[i][0] < zone_jobs[j][1]).OnlyEnforceIf(
                                overlap_ij
                            )
                            model.Add(zone_jobs[j][0] < zone_jobs[i][1]).OnlyEnforceIf(
                                overlap_ij
                            )

                            model.Add(zone_jobs[j][0] < zone_jobs[k][1]).OnlyEnforceIf(
                                overlap_jk
                            )
                            model.Add(zone_jobs[k][0] < zone_jobs[j][1]).OnlyEnforceIf(
                                overlap_jk
                            )

                            model.Add(zone_jobs[i][0] < zone_jobs[k][1]).OnlyEnforceIf(
                                overlap_ik
                            )
                            model.Add(zone_jobs[k][0] < zone_jobs[i][1]).OnlyEnforceIf(
                                overlap_ik
                            )

                            # Not all three can overlap
                            model.AddBoolOr(
                                [overlap_ij.Not(), overlap_jk.Not(), overlap_ik.Not()]
                            )

        print("Setting up objective function...")

        # Calculate completion times and tardiness
        job_completions = {}
        tardiness_vars = {}

        for job_id in range(self.num_jobs):
            # Job completion is end of last task
            last_task_ends = []
            for opt in range(len(self.get_task_duration_and_setup(self.num_tasks - 1))):
                last_task_ends.append(task_ends[(job_id, self.num_tasks - 1, opt)])

            completion = model.NewIntVar(0, self.horizon, f"completion_j{job_id}")

            # Set completion based on which option is selected
            for opt in range(len(self.get_task_duration_and_setup(self.num_tasks - 1))):
                model.Add(
                    completion == task_ends[(job_id, self.num_tasks - 1, opt)]
                ).OnlyEnforceIf(task_presences[(job_id, self.num_tasks - 1, opt)])

            job_completions[job_id] = completion

            # Calculate tardiness
            tardiness = model.NewIntVar(0, self.horizon, f"tardiness_j{job_id}")
            model.AddMaxEquality(tardiness, [completion - self.due_dates[job_id], 0])
            tardiness_vars[job_id] = tardiness

        # Makespan
        makespan = model.NewIntVar(0, self.horizon, "makespan")
        model.AddMaxEquality(makespan, list(job_completions.values()))

        # Total tardiness
        total_tardiness = model.NewIntVar(
            0, self.horizon * self.num_jobs, "total_tardiness"
        )
        model.Add(total_tardiness == sum(tardiness_vars.values()))

        # Primary objective: minimize (2 * total_tardiness + makespan)
        primary_objective = model.NewIntVar(
            0, self.horizon * (2 * self.num_jobs + 1), "primary_objective"
        )
        model.Add(primary_objective == 2 * total_tardiness + makespan)

        return (
            model,
            primary_objective,
            task_starts,
            task_ends,
            task_presences,
            task_operators,
            job_completions,
            tardiness_vars,
            makespan,
        )

    def solve(self) -> dict[str, Any] | None:
        """Solve the scheduling problem with hierarchical optimization"""

        print("\n" + "=" * 80)
        print("HYBRID FLEXIBLE FLOW SHOP SCHEDULER")
        print("=" * 80)

        # Phase 1: Optimize primary objective
        print("\nPhase 1: Optimizing makespan and tardiness...")
        print("-" * 40)

        (
            model,
            primary_obj,
            starts,
            ends,
            presences,
            operators,
            completions,
            tardiness,
            makespan,
        ) = self.create_model()
        model.Minimize(primary_obj)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300  # 5 minute time limit
        solver.parameters.num_search_workers = 8  # Parallel search
        solver.parameters.log_search_progress = True

        start_time = time.time()
        status = solver.Solve(model)
        phase1_time = time.time() - start_time

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print(
                f"No feasible solution found in Phase 1. Status: {solver.StatusName(status)}"
            )
            return None

        primary_value = solver.Value(primary_obj)
        makespan_value = solver.Value(makespan)

        print("\nPhase 1 Results:")
        print(f"  Primary objective value: {primary_value}")
        print(
            f"  Makespan: {makespan_value:.0f} minutes ({makespan_value/60/24:.1f} days)"
        )
        print(
            f"  Total tardiness: {sum(solver.Value(tardiness[j]) for j in range(self.num_jobs)):.0f} minutes"
        )
        print(f"  Solution time: {phase1_time:.2f} seconds")

        # Store Phase 1 solution
        phase1_solution = {
            "makespan": makespan_value,
            "tardiness": {j: solver.Value(tardiness[j]) for j in range(self.num_jobs)},
            "completions": {
                j: solver.Value(completions[j]) for j in range(self.num_jobs)
            },
            "objective": primary_value,
            "status": solver.StatusName(status),
        }

        # Phase 2: Minimize operator cost while maintaining solution quality
        print("\nPhase 2: Optimizing operator costs...")
        print("-" * 40)

        # Create new model with primary objective constraint
        (
            model2,
            primary_obj2,
            starts2,
            ends2,
            presences2,
            operators2,
            completions2,
            tardiness2,
            makespan2,
        ) = self.create_model()

        # Constrain primary objective to be within 10% of Phase 1 solution
        model2.Add(primary_obj2 <= int(primary_value * 1.1))

        # Calculate operator cost
        operator_cost = model2.NewIntVar(
            0,
            self.horizon * max(self.operator_costs.values()) * self.num_operators,
            "operator_cost",
        )

        # Sum costs for all operator assignments
        cost_terms = []
        for key in operators2:
            job_id, task_id, option_id, op_num = key
            is_attended = self.is_attended_machine(task_id)

            if is_attended:
                duration = sum(self.get_task_duration_and_setup(task_id)[option_id])
            else:
                _, setup_time = self.get_task_duration_and_setup(task_id)[option_id]
                duration = setup_time

            for op_id in self.get_eligible_operators(task_id):
                cost_if_assigned = model2.NewIntVar(
                    0,
                    duration * self.operator_costs[op_id],
                    f"cost_j{job_id}_t{task_id}_o{option_id}_op{op_id}_n{op_num}",
                )
                is_assigned = model2.NewBoolVar(
                    f"assigned_j{job_id}_t{task_id}_o{option_id}_op{op_id}_n{op_num}"
                )

                model2.Add(operators2[key] == op_id).OnlyEnforceIf(is_assigned)
                model2.Add(
                    cost_if_assigned == duration * self.operator_costs[op_id]
                ).OnlyEnforceIf(is_assigned)
                model2.Add(cost_if_assigned == 0).OnlyEnforceIf(is_assigned.Not())

                # Only count cost if task option is selected
                actual_cost = model2.NewIntVar(
                    0,
                    duration * self.operator_costs[op_id],
                    f"actual_cost_j{job_id}_t{task_id}_o{option_id}_op{op_id}_n{op_num}",
                )
                model2.Add(actual_cost == cost_if_assigned).OnlyEnforceIf(
                    presences2[(job_id, task_id, option_id)]
                )
                model2.Add(actual_cost == 0).OnlyEnforceIf(
                    presences2[(job_id, task_id, option_id)].Not()
                )

                cost_terms.append(actual_cost)

        model2.Add(operator_cost == sum(cost_terms))
        model2.Minimize(operator_cost)

        solver2 = cp_model.CpSolver()
        solver2.parameters.max_time_in_seconds = 300
        solver2.parameters.num_search_workers = 8

        start_time = time.time()
        status2 = solver2.Solve(model2)
        phase2_time = time.time() - start_time

        if status2 not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("No feasible solution found in Phase 2. Using Phase 1 solution.")
            return phase1_solution

        print("\nPhase 2 Results:")
        print(f"  Operator cost: ${solver2.Value(operator_cost):.2f}")
        print(
            f"  Makespan: {solver2.Value(makespan2):.0f} minutes ({solver2.Value(makespan2)/60/24:.1f} days)"
        )
        print(f"  Solution time: {phase2_time:.2f} seconds")

        # Display final solution details
        print("\n" + "=" * 80)
        print("FINAL SOLUTION SUMMARY")
        print("=" * 80)

        print("\nJob Completion vs Due Dates:")
        print("-" * 40)
        total_tardiness = 0
        for job_id in range(self.num_jobs):
            completion = solver2.Value(completions2[job_id])
            due = self.due_dates[job_id]
            tardiness_val = max(0, completion - due)
            total_tardiness += tardiness_val

            status_str = (
                "ON TIME"
                if tardiness_val == 0
                else f"LATE by {tardiness_val/60/24:.1f} days"
            )
            print(
                f"  Job {job_id}: Completed at {completion/60/24:.1f} days, Due at {due/60/24:.1f} days - {status_str}"
            )

        print(
            f"\nTotal Tardiness: {total_tardiness:.0f} minutes ({total_tardiness/60/24:.1f} days)"
        )

        print("\nSample Task Assignments (first 10 tasks of Job 0):")
        print("-" * 40)
        for task_id in range(min(10, self.num_tasks)):
            for option_id in range(len(self.get_task_duration_and_setup(task_id))):
                if solver2.Value(presences2[(0, task_id, option_id)]) == 1:
                    start = solver2.Value(starts2[(0, task_id, option_id)])
                    end = solver2.Value(ends2[(0, task_id, option_id)])

                    # Get operator assignment
                    if task_id in self.two_operator_tasks:
                        op1 = solver2.Value(operators2[(0, task_id, option_id, 0)])
                        op2 = solver2.Value(operators2[(0, task_id, option_id, 1)])
                        op_str = f"Operators {op1}, {op2}"
                    else:
                        op = solver2.Value(operators2[(0, task_id, option_id, 0)])
                        op_str = f"Operator {op}"

                    machine_type = (
                        "Attended"
                        if self.is_attended_machine(task_id)
                        else "Unattended"
                    )
                    print(
                        f"  Task {task_id}: Start={start:.0f}, End={end:.0f}, {op_str}, {machine_type}"
                    )

        print("\nCritical Sequence Timing (Job 0):")
        print("-" * 40)
        for seq_start, seq_end in self.critical_sequences:
            for opt in range(len(self.get_task_duration_and_setup(seq_start))):
                if solver2.Value(presences2[(0, seq_start, opt)]) == 1:
                    start = solver2.Value(starts2[(0, seq_start, opt)])
                    break
            for opt in range(len(self.get_task_duration_and_setup(seq_end))):
                if solver2.Value(presences2[(0, seq_end, opt)]) == 1:
                    end = solver2.Value(ends2[(0, seq_end, opt)])
                    break

            print(
                f"  Tasks {seq_start}-{seq_end}: Start={start:.0f}, End={end:.0f}, Duration={(end-start):.0f} min"
            )

        print("\nResource Utilization Metrics:")
        print("-" * 40)

        # Calculate machine utilization (simplified)
        total_machine_time = 0
        for job_id in range(self.num_jobs):
            for task_id in range(self.num_tasks):
                for option_id in range(len(self.get_task_duration_and_setup(task_id))):
                    if (job_id, task_id, option_id) in presences2:
                        if solver2.Value(presences2[(job_id, task_id, option_id)]) == 1:
                            total_machine_time += sum(
                                self.get_task_duration_and_setup(task_id)[option_id]
                            )

        available_machine_time = self.num_tasks * solver2.Value(makespan2)  # Simplified
        machine_utilization = (
            (total_machine_time / available_machine_time) * 100
            if available_machine_time > 0
            else 0
        )

        print(f"  Average Machine Utilization: {machine_utilization:.1f}%")
        print(f"  Total Operator Cost: ${solver2.Value(operator_cost):.2f}")
        print(f"  Total Solution Time: {phase1_time + phase2_time:.2f} seconds")

        print("\nSolver Statistics:")
        print("-" * 40)
        print(f"  Phase 1: {solver.StatusName(status)}")
        print(f"  Phase 2: {solver2.StatusName(status2)}")

        return {
            "makespan": solver2.Value(makespan2),
            "total_tardiness": total_tardiness,
            "operator_cost": solver2.Value(operator_cost),
            "job_completions": {
                j: solver2.Value(completions2[j]) for j in range(self.num_jobs)
            },
            "status": solver2.StatusName(status2),
        }


def main() -> None:
    """Main entry point"""
    scheduler = HFFSScheduler()
    solution = scheduler.solve()

    if solution:
        print("\n" + "=" * 80)
        print("SCHEDULING COMPLETE")
        print("=" * 80)
        print("\nFinal Metrics:")
        print(f"  Makespan: {solution['makespan']/60/24:.1f} days")
        print(f"  Total Tardiness: {solution['total_tardiness']/60/24:.1f} days")
        print(f"  Operator Cost: ${solution['operator_cost']:.2f}")
    else:
        print("\nFailed to find a feasible solution.")


if __name__ == "__main__":
    main()
