"""
CriticalSequenceManager Domain Service

Domain service for managing critical operation sequences.
Matches DOMAIN.md specification exactly.
"""

from datetime import datetime
from decimal import Decimal

from ..entities.job import Job
from ..entities.task import Task
from ..value_objects.duration import Duration


class CriticalSequenceManager:
    """
    Domain service for managing critical operation sequences.
    Matches DOMAIN.md specification exactly.
    """

    def identify_critical_sequences(self, job: Job) -> list[list[Task]]:
        """
        Identify sequences of critical tasks that must be prioritized.
        Returns list of task sequences.
        Matches DOMAIN.md specification exactly.

        Args:
            job: Job to analyze for critical sequences

        Returns:
            List of task sequences, where each sequence is a list of consecutive critical tasks
        """
        sequences = []
        current_sequence = []

        for task in job.get_tasks_in_sequence():
            if task.is_critical:
                current_sequence.append(task)
            else:
                if len(current_sequence) >= 2:  # Sequence of at least 2 critical tasks
                    sequences.append(current_sequence)
                current_sequence = []

        # Don't forget last sequence
        if len(current_sequence) >= 2:
            sequences.append(current_sequence)

        return sequences

    def calculate_sequence_duration(self, sequence: list[Task]) -> Duration:
        """
        Calculate minimum duration for a critical sequence.
        Matches DOMAIN.md specification exactly.

        Args:
            sequence: List of tasks in the critical sequence

        Returns:
            Minimum duration for the sequence
        """
        total = Duration.from_minutes(Decimal("0"))

        for task in sequence:
            # Use minimum duration from machine options
            if task.machine_options:
                min_duration = min(opt.total_duration() for opt in task.machine_options)
                total = total + min_duration
            else:
                # Fallback to planned duration if no machine options
                if task.planned_duration:
                    total = total + task.planned_duration

        return total

    def prioritize_job_sequence(self, jobs: list[Job]) -> list[Job]:
        """
        Sort jobs by criticality and due date.
        Jobs with more critical sequences get higher priority.
        Matches DOMAIN.md specification exactly.

        Args:
            jobs: List of jobs to prioritize

        Returns:
            Jobs sorted by priority (highest priority first)
        """

        def job_priority_score(job: Job) -> tuple[int, int, datetime]:
            critical_sequences = self.identify_critical_sequences(job)
            num_critical_tasks = sum(len(seq) for seq in critical_sequences)

            # Return (negative critical count for descending sort, priority, due_date)
            return (
                -num_critical_tasks,
                -job.priority,  # Negative for descending sort
                job.due_date or datetime.max,
            )

        return sorted(jobs, key=job_priority_score)

    def find_critical_path_tasks(self, job: Job) -> list[Task]:
        """
        Find all tasks that are on the critical path.

        Args:
            job: Job to analyze

        Returns:
            List of tasks on the critical path
        """
        critical_path_tasks = []

        for task in job.get_tasks_in_sequence():
            if task.is_critical_path:
                critical_path_tasks.append(task)

        return critical_path_tasks

    def calculate_critical_path_duration(self, job: Job) -> Duration:
        """
        Calculate the total duration of the critical path.

        Args:
            job: Job to analyze

        Returns:
            Total duration of the critical path
        """
        critical_tasks = self.find_critical_path_tasks(job)

        if not critical_tasks:
            return Duration.from_minutes(Decimal("0"))

        total_duration = Duration.from_minutes(Decimal("0"))

        for task in critical_tasks:
            if task.machine_options:
                # Use minimum duration from available options
                min_duration = min(opt.total_duration() for opt in task.machine_options)
                total_duration = total_duration + min_duration
            elif task.planned_duration:
                total_duration = total_duration + task.planned_duration

        return total_duration

    def identify_bottleneck_sequences(
        self, jobs: list[Job]
    ) -> list[tuple[Job, list[Task], Duration]]:
        """
        Identify bottleneck sequences across multiple jobs.

        Args:
            jobs: List of jobs to analyze

        Returns:
            List of (job, sequence, duration) tuples for bottleneck sequences
        """
        bottlenecks = []

        for job in jobs:
            sequences = self.identify_critical_sequences(job)

            for sequence in sequences:
                duration = self.calculate_sequence_duration(sequence)
                bottlenecks.append((job, sequence, duration))

        # Sort by duration (longest first)
        bottlenecks.sort(key=lambda x: x[2].minutes, reverse=True)

        return bottlenecks

    def suggest_parallel_execution_opportunities(
        self, job: Job
    ) -> list[tuple[Task, list[Task]]]:
        """
        Suggest opportunities for parallel task execution.

        Args:
            job: Job to analyze

        Returns:
            List of (anchor_task, parallel_tasks) tuples where parallel_tasks
            could potentially run in parallel with anchor_task
        """
        opportunities = []
        tasks = job.get_tasks_in_sequence()

        for i, anchor_task in enumerate(tasks):
            if anchor_task.is_critical:
                continue  # Critical tasks should not be delayed

            parallel_candidates = []

            # Look for tasks that could run in parallel
            for j, candidate_task in enumerate(tasks):
                if i == j:
                    continue

                # Check if candidate could run in parallel
                if not candidate_task.is_critical and self._can_run_in_parallel(
                    anchor_task, candidate_task, tasks
                ):
                    parallel_candidates.append(candidate_task)

            if parallel_candidates:
                opportunities.append((anchor_task, parallel_candidates))

        return opportunities

    def _can_run_in_parallel(
        self, task1: Task, task2: Task, all_tasks: list[Task]
    ) -> bool:
        """
        Check if two tasks can potentially run in parallel.

        Args:
            task1: First task
            task2: Second task
            all_tasks: All tasks in the job

        Returns:
            True if tasks could potentially run in parallel
        """
        # Basic checks
        if task1.id == task2.id:
            return False

        # Check if they have direct dependencies
        if task1.id in task2.predecessor_ids or task2.id in task1.predecessor_ids:
            return False

        # Check for indirect dependencies (simplified check)
        set(task1.predecessor_ids)
        set(task2.predecessor_ids)

        # If one task's predecessors include the other task's position in sequence,
        # they likely can't run in parallel
        task1_seq = next(i for i, t in enumerate(all_tasks) if t.id == task1.id)
        task2_seq = next(i for i, t in enumerate(all_tasks) if t.id == task2.id)

        # Simple heuristic: tasks that are close in sequence are less likely
        # to be parallelizable
        sequence_gap = abs(task1_seq - task2_seq)
        if sequence_gap < 3:  # Arbitrary threshold
            return False

        return True

    def calculate_schedule_criticality_score(self, job: Job) -> float:
        """
        Calculate an overall criticality score for a job's schedule.

        Args:
            job: Job to score

        Returns:
            Criticality score (0.0 to 1.0, higher is more critical)
        """
        tasks = job.get_tasks_in_sequence()
        if not tasks:
            return 0.0

        critical_tasks = [t for t in tasks if t.is_critical_path]
        critical_sequences = self.identify_critical_sequences(job)

        # Base score from proportion of critical tasks
        critical_task_ratio = len(critical_tasks) / len(tasks)

        # Bonus for long critical sequences
        max_sequence_length = max((len(seq) for seq in critical_sequences), default=0)
        sequence_bonus = min(0.3, max_sequence_length * 0.05)

        # Bonus for job priority
        priority_bonus = min(0.2, job.priority * 0.05)

        # Penalty for schedule slack (if due date is far)
        time_pressure_factor = 1.0
        if job.due_date and job.release_date:
            total_time = (job.due_date - job.release_date).total_seconds()
            critical_path_time = float(
                self.calculate_critical_path_duration(job).seconds
            )

            if total_time > 0:
                time_pressure_factor = min(1.0, critical_path_time / total_time)

        total_score = (
            critical_task_ratio + sequence_bonus + priority_bonus
        ) * time_pressure_factor

        return min(1.0, total_score)
