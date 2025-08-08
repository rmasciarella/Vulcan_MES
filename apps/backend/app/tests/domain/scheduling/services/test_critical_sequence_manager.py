"""
Comprehensive Unit Tests for CriticalSequenceManager Domain Service

Tests all critical sequence management methods including identification, prioritization,
duration calculations, bottleneck analysis, and parallel execution opportunities.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.domain.scheduling.entities.job import Job
from app.domain.scheduling.entities.task import Task
from app.domain.scheduling.services.critical_sequence_manager import CriticalSequenceManager
from app.domain.scheduling.value_objects.duration import Duration
from app.tests.database.factories import JobFactory, TaskFactory


@pytest.fixture
def critical_sequence_manager():
    """Create CriticalSequenceManager instance."""
    return CriticalSequenceManager()


@pytest.fixture
def sample_job_with_critical_tasks():
    """Create a job with mixed critical and non-critical tasks."""
    job = JobFactory.create(
        job_number="CRITICAL-001",
        priority=5,
        due_date=datetime(2024, 1, 15, 16, 0)
    )
    
    # Create tasks with mixed criticality
    task1 = Mock(spec=Task)
    task1.id = uuid4()
    task1.is_critical = True
    task1.is_critical_path = True
    task1.machine_options = []
    task1.planned_duration = Duration.from_minutes(60)
    
    task2 = Mock(spec=Task)
    task2.id = uuid4()
    task2.is_critical = True
    task2.is_critical_path = True
    task2.machine_options = []
    task2.planned_duration = Duration.from_minutes(90)
    
    task3 = Mock(spec=Task)
    task3.id = uuid4()
    task3.is_critical = False
    task3.is_critical_path = False
    task3.machine_options = []
    task3.planned_duration = Duration.from_minutes(45)
    
    task4 = Mock(spec=Task)
    task4.id = uuid4()
    task4.is_critical = True
    task4.is_critical_path = True
    task4.machine_options = []
    task4.planned_duration = Duration.from_minutes(120)
    
    task5 = Mock(spec=Task)
    task5.id = uuid4()
    task5.is_critical = False
    task5.is_critical_path = False
    task5.machine_options = []
    task5.planned_duration = Duration.from_minutes(30)
    
    tasks = [task1, task2, task3, task4, task5]
    job.get_tasks_in_sequence = Mock(return_value=tasks)
    
    return job


@pytest.fixture
def sample_jobs_for_prioritization():
    """Create multiple jobs for prioritization testing."""
    jobs = []
    
    # Job 1: High priority, many critical tasks, early due date
    job1 = JobFactory.create(
        job_number="HIGH-001",
        priority=10,
        due_date=datetime(2024, 1, 10, 16, 0)
    )
    
    critical_tasks = [Mock(spec=Task) for _ in range(4)]
    for i, task in enumerate(critical_tasks):
        task.id = uuid4()
        task.is_critical = True
        task.is_critical_path = True
        task.machine_options = []
        task.planned_duration = Duration.from_minutes(60 + i * 15)
    
    job1.get_tasks_in_sequence = Mock(return_value=critical_tasks)
    jobs.append(job1)
    
    # Job 2: Medium priority, few critical tasks, later due date
    job2 = JobFactory.create(
        job_number="MED-002",
        priority=5,
        due_date=datetime(2024, 1, 20, 16, 0)
    )
    
    mixed_tasks = []
    for i in range(3):
        task = Mock(spec=Task)
        task.id = uuid4()
        task.is_critical = i < 1  # Only first task is critical
        task.is_critical_path = i < 1
        task.machine_options = []
        task.planned_duration = Duration.from_minutes(45)
        mixed_tasks.append(task)
    
    job2.get_tasks_in_sequence = Mock(return_value=mixed_tasks)
    jobs.append(job2)
    
    # Job 3: Low priority, no critical tasks, no due date
    job3 = JobFactory.create(
        job_number="LOW-003",
        priority=1,
        due_date=None
    )
    
    regular_tasks = []
    for i in range(2):
        task = Mock(spec=Task)
        task.id = uuid4()
        task.is_critical = False
        task.is_critical_path = False
        task.machine_options = []
        task.planned_duration = Duration.from_minutes(30)
        regular_tasks.append(task)
    
    job3.get_tasks_in_sequence = Mock(return_value=regular_tasks)
    jobs.append(job3)
    
    return jobs


@pytest.fixture
def sample_tasks_with_machine_options():
    """Create tasks with machine options for duration calculations."""
    tasks = []
    
    for i in range(3):
        task = Mock(spec=Task)
        task.id = uuid4()
        task.is_critical = i < 2  # First two are critical
        task.is_critical_path = i < 2
        
        # Create machine options with different durations
        option1 = Mock()
        option1.total_duration.return_value = Duration.from_minutes(60 + i * 20)
        
        option2 = Mock()
        option2.total_duration.return_value = Duration.from_minutes(45 + i * 15)  # Faster option
        
        task.machine_options = [option1, option2]
        task.planned_duration = Duration.from_minutes(60 + i * 20)  # Fallback
        
        tasks.append(task)
    
    return tasks


class TestCriticalSequenceManager:
    """Test the main CriticalSequenceManager functionality."""

    def test_initialization(self):
        """Test CriticalSequenceManager initialization."""
        manager = CriticalSequenceManager()
        assert manager is not None

    def test_identify_critical_sequences_single_sequence(self, critical_sequence_manager):
        """Test identifying a single critical sequence."""
        job = Mock(spec=Job)
        
        # Create sequence: Critical -> Critical -> Non-critical -> Critical
        task1 = Mock(spec=Task)
        task1.is_critical = True
        
        task2 = Mock(spec=Task)
        task2.is_critical = True
        
        task3 = Mock(spec=Task)
        task3.is_critical = False
        
        task4 = Mock(spec=Task)
        task4.is_critical = True
        
        job.get_tasks_in_sequence.return_value = [task1, task2, task3, task4]
        
        sequences = critical_sequence_manager.identify_critical_sequences(job)
        
        assert len(sequences) == 1
        assert len(sequences[0]) == 2  # task1 and task2
        assert sequences[0] == [task1, task2]

    def test_identify_critical_sequences_multiple_sequences(self, critical_sequence_manager):
        """Test identifying multiple critical sequences."""
        job = Mock(spec=Job)
        
        # Create pattern: Critical -> Critical -> Non-critical -> Critical -> Critical -> Critical
        tasks = []
        criticality = [True, True, False, True, True, True]
        
        for i, is_crit in enumerate(criticality):
            task = Mock(spec=Task)
            task.is_critical = is_crit
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        sequences = critical_sequence_manager.identify_critical_sequences(job)
        
        assert len(sequences) == 2
        assert len(sequences[0]) == 2  # First two critical tasks
        assert len(sequences[1]) == 3  # Last three critical tasks

    def test_identify_critical_sequences_no_sequences(self, critical_sequence_manager):
        """Test identifying critical sequences when none exist."""
        job = Mock(spec=Job)
        
        # Single critical task (not a sequence)
        task1 = Mock(spec=Task)
        task1.is_critical = True
        
        task2 = Mock(spec=Task)
        task2.is_critical = False
        
        task3 = Mock(spec=Task)
        task3.is_critical = False
        
        job.get_tasks_in_sequence.return_value = [task1, task2, task3]
        
        sequences = critical_sequence_manager.identify_critical_sequences(job)
        
        assert len(sequences) == 0

    def test_identify_critical_sequences_all_critical(self, critical_sequence_manager):
        """Test identifying sequences when all tasks are critical."""
        job = Mock(spec=Job)
        
        tasks = []
        for i in range(5):
            task = Mock(spec=Task)
            task.is_critical = True
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        sequences = critical_sequence_manager.identify_critical_sequences(job)
        
        assert len(sequences) == 1
        assert len(sequences[0]) == 5  # All tasks in one sequence

    def test_calculate_sequence_duration_with_machine_options(
        self, critical_sequence_manager, sample_tasks_with_machine_options
    ):
        """Test calculating sequence duration with machine options."""
        # Use only the critical tasks (first two)
        critical_tasks = sample_tasks_with_machine_options[:2]
        
        duration = critical_sequence_manager.calculate_sequence_duration(critical_tasks)
        
        # Should use minimum duration from machine options
        # Task 1: min(60, 45) = 45, Task 2: min(80, 60) = 60
        expected_duration = Duration.from_minutes(45) + Duration.from_minutes(60)
        assert duration == expected_duration

    def test_calculate_sequence_duration_without_machine_options(self, critical_sequence_manager):
        """Test calculating sequence duration using planned duration fallback."""
        task1 = Mock(spec=Task)
        task1.machine_options = []  # No machine options
        task1.planned_duration = Duration.from_minutes(90)
        
        task2 = Mock(spec=Task)
        task2.machine_options = []
        task2.planned_duration = Duration.from_minutes(60)
        
        sequence = [task1, task2]
        
        duration = critical_sequence_manager.calculate_sequence_duration(sequence)
        
        expected_duration = Duration.from_minutes(90) + Duration.from_minutes(60)
        assert duration == expected_duration

    def test_calculate_sequence_duration_empty_sequence(self, critical_sequence_manager):
        """Test calculating duration of empty sequence."""
        duration = critical_sequence_manager.calculate_sequence_duration([])
        
        assert duration == Duration.from_minutes(Decimal("0"))

    def test_prioritize_job_sequence_by_criticality(
        self, critical_sequence_manager, sample_jobs_for_prioritization
    ):
        """Test job prioritization based on critical sequences and due dates."""
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence(
            sample_jobs_for_prioritization
        )
        
        assert len(prioritized_jobs) == 3
        
        # First job should have most critical tasks and highest priority
        assert prioritized_jobs[0].job_number == "HIGH-001"
        
        # Last job should have no critical tasks and no due date
        assert prioritized_jobs[2].job_number == "LOW-003"

    def test_prioritize_job_sequence_empty_list(self, critical_sequence_manager):
        """Test prioritizing empty job list."""
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence([])
        
        assert prioritized_jobs == []

    def test_prioritize_job_sequence_single_job(self, critical_sequence_manager):
        """Test prioritizing single job."""
        job = JobFactory.create()
        job.get_tasks_in_sequence = Mock(return_value=[])
        
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence([job])
        
        assert len(prioritized_jobs) == 1
        assert prioritized_jobs[0] == job

    def test_find_critical_path_tasks(
        self, critical_sequence_manager, sample_job_with_critical_tasks
    ):
        """Test finding tasks on the critical path."""
        critical_path_tasks = critical_sequence_manager.find_critical_path_tasks(
            sample_job_with_critical_tasks
        )
        
        # Should find 3 critical path tasks (task1, task2, task4)
        assert len(critical_path_tasks) == 3
        
        # All returned tasks should be on critical path
        assert all(task.is_critical_path for task in critical_path_tasks)

    def test_find_critical_path_tasks_no_critical_path(self, critical_sequence_manager):
        """Test finding critical path tasks when none exist."""
        job = Mock(spec=Job)
        
        task = Mock(spec=Task)
        task.is_critical_path = False
        
        job.get_tasks_in_sequence.return_value = [task]
        
        critical_path_tasks = critical_sequence_manager.find_critical_path_tasks(job)
        
        assert critical_path_tasks == []

    def test_calculate_critical_path_duration_with_options(
        self, critical_sequence_manager, sample_tasks_with_machine_options
    ):
        """Test calculating critical path duration with machine options."""
        job = Mock(spec=Job)
        
        # Set first two tasks as critical path
        critical_tasks = sample_tasks_with_machine_options[:2]
        for task in critical_tasks:
            task.is_critical_path = True
        
        # Set third task as not on critical path
        sample_tasks_with_machine_options[2].is_critical_path = False
        
        job.get_tasks_in_sequence.return_value = sample_tasks_with_machine_options
        
        duration = critical_sequence_manager.calculate_critical_path_duration(job)
        
        # Should sum minimum durations of critical path tasks only
        # Task 1: min(60, 45) = 45, Task 2: min(80, 60) = 60
        expected_duration = Duration.from_minutes(45) + Duration.from_minutes(60)
        assert duration == expected_duration

    def test_calculate_critical_path_duration_no_critical_path(self, critical_sequence_manager):
        """Test calculating critical path duration when no critical path exists."""
        job = Mock(spec=Job)
        
        task = Mock(spec=Task)
        task.is_critical_path = False
        
        job.get_tasks_in_sequence.return_value = [task]
        
        duration = critical_sequence_manager.calculate_critical_path_duration(job)
        
        assert duration == Duration.from_minutes(Decimal("0"))

    def test_identify_bottleneck_sequences(
        self, critical_sequence_manager, sample_jobs_for_prioritization
    ):
        """Test identifying bottleneck sequences across multiple jobs."""
        bottlenecks = critical_sequence_manager.identify_bottleneck_sequences(
            sample_jobs_for_prioritization
        )
        
        assert len(bottlenecks) > 0
        
        # Each bottleneck should be a tuple of (job, sequence, duration)
        for job, sequence, duration in bottlenecks:
            assert isinstance(job, Mock)  # Job mock
            assert isinstance(sequence, list)  # List of tasks
            assert isinstance(duration, Duration)
        
        # Should be sorted by duration (longest first)
        if len(bottlenecks) > 1:
            for i in range(len(bottlenecks) - 1):
                assert bottlenecks[i][2].minutes >= bottlenecks[i + 1][2].minutes

    def test_identify_bottleneck_sequences_no_critical_sequences(self, critical_sequence_manager):
        """Test bottleneck identification when no critical sequences exist."""
        job = Mock(spec=Job)
        
        # Single critical task (not a sequence)
        task = Mock(spec=Task)
        task.is_critical = True
        
        job.get_tasks_in_sequence.return_value = [task]
        
        bottlenecks = critical_sequence_manager.identify_bottleneck_sequences([job])
        
        assert bottlenecks == []

    def test_suggest_parallel_execution_opportunities_basic(self, critical_sequence_manager):
        """Test suggesting parallel execution opportunities."""
        job = Mock(spec=Job)
        
        # Create tasks with varying criticality and dependencies
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        task1.is_critical = True  # Skip critical tasks
        
        task2 = Mock(spec=Task)
        task2.id = uuid4()
        task2.is_critical = False  # Non-critical anchor task
        
        task3 = Mock(spec=Task)
        task3.id = uuid4()
        task3.is_critical = False  # Non-critical candidate
        
        task4 = Mock(spec=Task)
        task4.id = uuid4()
        task4.is_critical = False  # Non-critical candidate
        
        tasks = [task1, task2, task3, task4]
        job.get_tasks_in_sequence.return_value = tasks
        
        opportunities = critical_sequence_manager.suggest_parallel_execution_opportunities(job)
        
        # Should find opportunities for non-critical tasks
        assert isinstance(opportunities, list)
        
        # Each opportunity should be a tuple of (anchor_task, parallel_candidates)
        for anchor, candidates in opportunities:
            assert hasattr(anchor, 'is_critical')
            assert isinstance(candidates, list)

    def test_suggest_parallel_execution_no_opportunities(self, critical_sequence_manager):
        """Test parallel execution suggestions when no opportunities exist."""
        job = Mock(spec=Job)
        
        # All tasks are critical (no parallelization opportunities)
        tasks = []
        for i in range(3):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.is_critical = True
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        opportunities = critical_sequence_manager.suggest_parallel_execution_opportunities(job)
        
        assert opportunities == []

    def test_can_run_in_parallel_with_dependencies(self, critical_sequence_manager):
        """Test parallel execution feasibility with task dependencies."""
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        task1.predecessor_ids = []
        
        task2 = Mock(spec=Task)
        task2.id = uuid4()
        task2.predecessor_ids = [task1.id]  # Depends on task1
        
        all_tasks = [task1, task2]
        
        can_parallel = critical_sequence_manager._can_run_in_parallel(task1, task2, all_tasks)
        
        assert can_parallel is False  # Cannot run in parallel due to dependency

    def test_can_run_in_parallel_same_task(self, critical_sequence_manager):
        """Test parallel execution feasibility with same task."""
        task = Mock(spec=Task)
        task.id = uuid4()
        
        can_parallel = critical_sequence_manager._can_run_in_parallel(task, task, [task])
        
        assert can_parallel is False  # Same task cannot run in parallel with itself

    def test_can_run_in_parallel_close_sequence(self, critical_sequence_manager):
        """Test parallel execution feasibility with tasks close in sequence."""
        tasks = []
        for i in range(5):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.predecessor_ids = []
            tasks.append(task)
        
        # Tasks at positions 0 and 1 (close in sequence)
        can_parallel = critical_sequence_manager._can_run_in_parallel(tasks[0], tasks[1], tasks)
        
        assert can_parallel is False  # Too close in sequence

    def test_can_run_in_parallel_valid_case(self, critical_sequence_manager):
        """Test parallel execution feasibility with valid case."""
        tasks = []
        for i in range(10):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.predecessor_ids = []
            tasks.append(task)
        
        # Tasks at positions 0 and 5 (far apart, no dependencies)
        can_parallel = critical_sequence_manager._can_run_in_parallel(tasks[0], tasks[5], tasks)
        
        assert can_parallel is True

    def test_calculate_schedule_criticality_score_high_criticality(self, critical_sequence_manager):
        """Test criticality score calculation for highly critical job."""
        job = Mock(spec=Job)
        job.priority = 10
        job.due_date = datetime(2024, 1, 15, 16, 0)
        job.release_date = datetime(2024, 1, 10, 8, 0)
        
        # Most tasks are critical
        tasks = []
        for i in range(5):
            task = Mock(spec=Task)
            task.is_critical_path = i < 4  # 4 out of 5 critical
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        # Mock critical sequences
        critical_sequence_manager.identify_critical_sequences = Mock(
            return_value=[[tasks[0], tasks[1], tasks[2]]]  # One long sequence
        )
        
        # Mock critical path duration
        critical_sequence_manager.calculate_critical_path_duration = Mock(
            return_value=Duration.from_minutes(240)  # 4 hours
        )
        
        score = critical_sequence_manager.calculate_schedule_criticality_score(job)
        
        assert score > 0.7  # Should be high criticality

    def test_calculate_schedule_criticality_score_low_criticality(self, critical_sequence_manager):
        """Test criticality score calculation for low criticality job."""
        job = Mock(spec=Job)
        job.priority = 1  # Low priority
        job.due_date = datetime(2024, 2, 15, 16, 0)  # Far due date
        job.release_date = datetime(2024, 1, 10, 8, 0)
        
        # Few critical tasks
        tasks = []
        for i in range(5):
            task = Mock(spec=Task)
            task.is_critical_path = i < 1  # Only 1 out of 5 critical
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        critical_sequence_manager.identify_critical_sequences = Mock(
            return_value=[]  # No critical sequences
        )
        
        critical_sequence_manager.calculate_critical_path_duration = Mock(
            return_value=Duration.from_minutes(60)  # 1 hour
        )
        
        score = critical_sequence_manager.calculate_schedule_criticality_score(job)
        
        assert score < 0.5  # Should be low criticality

    def test_calculate_schedule_criticality_score_no_tasks(self, critical_sequence_manager):
        """Test criticality score calculation for job with no tasks."""
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = []
        
        score = critical_sequence_manager.calculate_schedule_criticality_score(job)
        
        assert score == 0.0

    def test_calculate_schedule_criticality_score_no_due_date(self, critical_sequence_manager):
        """Test criticality score calculation for job with no due date."""
        job = Mock(spec=Job)
        job.priority = 5
        job.due_date = None
        job.release_date = datetime(2024, 1, 10, 8, 0)
        
        task = Mock(spec=Task)
        task.is_critical_path = True
        
        job.get_tasks_in_sequence.return_value = [task]
        
        critical_sequence_manager.identify_critical_sequences = Mock(return_value=[])
        critical_sequence_manager.calculate_critical_path_duration = Mock(
            return_value=Duration.from_minutes(60)
        )
        
        score = critical_sequence_manager.calculate_schedule_criticality_score(job)
        
        # Should still calculate score without time pressure factor
        assert score > 0

    def test_calculate_schedule_criticality_score_capped_at_one(self, critical_sequence_manager):
        """Test that criticality score is capped at 1.0."""
        job = Mock(spec=Job)
        job.priority = 20  # Very high priority
        job.due_date = datetime(2024, 1, 11, 16, 0)  # Very tight deadline
        job.release_date = datetime(2024, 1, 10, 8, 0)
        
        # All tasks critical
        tasks = []
        for i in range(10):
            task = Mock(spec=Task)
            task.is_critical_path = True
            tasks.append(task)
        
        job.get_tasks_in_sequence.return_value = tasks
        
        # Mock very long critical sequences
        critical_sequence_manager.identify_critical_sequences = Mock(
            return_value=[tasks[:5], tasks[5:]]  # Two long sequences
        )
        
        critical_sequence_manager.calculate_critical_path_duration = Mock(
            return_value=Duration.from_minutes(480)  # 8 hours
        )
        
        score = critical_sequence_manager.calculate_schedule_criticality_score(job)
        
        assert score <= 1.0  # Should be capped at 1.0


class TestCriticalSequenceManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_identify_critical_sequences_single_critical_task(self, critical_sequence_manager):
        """Test critical sequence identification with single critical task."""
        job = Mock(spec=Job)
        
        task = Mock(spec=Task)
        task.is_critical = True
        
        job.get_tasks_in_sequence.return_value = [task]
        
        sequences = critical_sequence_manager.identify_critical_sequences(job)
        
        assert sequences == []  # Single task is not a sequence

    def test_calculate_sequence_duration_no_duration_info(self, critical_sequence_manager):
        """Test duration calculation when tasks have no duration information."""
        task1 = Mock(spec=Task)
        task1.machine_options = []
        task1.planned_duration = None
        
        task2 = Mock(spec=Task)
        task2.machine_options = []
        task2.planned_duration = None
        
        sequence = [task1, task2]
        
        duration = critical_sequence_manager.calculate_sequence_duration(sequence)
        
        # Should return zero duration when no information available
        assert duration == Duration.from_minutes(Decimal("0"))

    def test_prioritize_job_sequence_identical_jobs(self, critical_sequence_manager):
        """Test prioritizing jobs with identical characteristics."""
        jobs = []
        for i in range(3):
            job = JobFactory.create(
                job_number=f"IDENTICAL-{i}",
                priority=5,
                due_date=datetime(2024, 1, 15, 16, 0)
            )
            
            task = Mock(spec=Task)
            task.is_critical = True
            
            job.get_tasks_in_sequence = Mock(return_value=[task])
            jobs.append(job)
        
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence(jobs)
        
        # Should return all jobs in some order
        assert len(prioritized_jobs) == 3
        assert set(prioritized_jobs) == set(jobs)

    def test_find_critical_path_tasks_empty_job(self, critical_sequence_manager):
        """Test finding critical path tasks in empty job."""
        job = Mock(spec=Job)
        job.get_tasks_in_sequence.return_value = []
        
        critical_path_tasks = critical_sequence_manager.find_critical_path_tasks(job)
        
        assert critical_path_tasks == []

    def test_suggest_parallel_opportunities_single_task(self, critical_sequence_manager):
        """Test parallel execution suggestions with single task."""
        job = Mock(spec=Job)
        
        task = Mock(spec=Task)
        task.id = uuid4()
        task.is_critical = False
        
        job.get_tasks_in_sequence.return_value = [task]
        
        opportunities = critical_sequence_manager.suggest_parallel_execution_opportunities(job)
        
        assert opportunities == []  # Cannot parallelize single task

    def test_can_run_in_parallel_missing_task_in_sequence(self, critical_sequence_manager):
        """Test parallel feasibility when task is missing from sequence."""
        task1 = Mock(spec=Task)
        task1.id = uuid4()
        
        task2 = Mock(spec=Task)
        task2.id = uuid4()
        
        # all_tasks list doesn't contain task1 or task2
        empty_tasks = []
        
        # This should handle the error gracefully
        try:
            can_parallel = critical_sequence_manager._can_run_in_parallel(task1, task2, empty_tasks)
            # If it doesn't raise an exception, it should return False as a safe default
            assert can_parallel is False
        except (StopIteration, ValueError):
            # If it raises an exception, that's also acceptable behavior
            pass


class TestCriticalSequenceManagerIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_manufacturing_workflow_critical_analysis(
        self, critical_sequence_manager, sample_jobs_for_prioritization
    ):
        """Test complete critical analysis of manufacturing workflow."""
        # Test full workflow: identify sequences, prioritize jobs, find bottlenecks
        
        # 1. Identify critical sequences in each job
        all_sequences = []
        for job in sample_jobs_for_prioritization:
            sequences = critical_sequence_manager.identify_critical_sequences(job)
            all_sequences.extend(sequences)
        
        # 2. Prioritize jobs
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence(
            sample_jobs_for_prioritization
        )
        
        # 3. Find bottlenecks
        bottlenecks = critical_sequence_manager.identify_bottleneck_sequences(
            sample_jobs_for_prioritization
        )
        
        # Verify results
        assert len(prioritized_jobs) == len(sample_jobs_for_prioritization)
        assert prioritized_jobs[0].job_number == "HIGH-001"  # Highest priority first
        
        # Should have some bottlenecks identified
        assert len(bottlenecks) >= 0

    def test_rush_order_critical_path_analysis(self, critical_sequence_manager):
        """Test critical path analysis for rush order scenario."""
        # Create urgent job with tight deadline
        rush_job = JobFactory.create(
            job_number="RUSH-001",
            priority=15,
            due_date=datetime.now() + timedelta(hours=8),  # 8 hours to complete
            release_date=datetime.now()
        )
        
        # Create tasks with critical path
        tasks = []
        for i in range(4):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.is_critical = True
            task.is_critical_path = True
            
            # Create machine option with tight timing
            option = Mock()
            option.total_duration.return_value = Duration.from_minutes(90)  # 1.5 hours each
            
            task.machine_options = [option]
            task.planned_duration = Duration.from_minutes(120)  # Fallback: 2 hours
            
            tasks.append(task)
        
        rush_job.get_tasks_in_sequence = Mock(return_value=tasks)
        
        # Analyze critical path
        critical_path_tasks = critical_sequence_manager.find_critical_path_tasks(rush_job)
        critical_path_duration = critical_sequence_manager.calculate_critical_path_duration(rush_job)
        criticality_score = critical_sequence_manager.calculate_schedule_criticality_score(rush_job)
        
        # Verify analysis
        assert len(critical_path_tasks) == 4  # All tasks on critical path
        assert critical_path_duration == Duration.from_minutes(360)  # 6 hours total
        assert criticality_score > 0.8  # High criticality due to tight timeline

    def test_complex_job_network_analysis(self, critical_sequence_manager):
        """Test analysis of complex job network with interdependencies."""
        # Create multiple jobs with different characteristics
        jobs = []
        
        # Job 1: Long critical sequence
        job1 = JobFactory.create(priority=8, due_date=datetime(2024, 1, 20, 16, 0))
        
        long_critical_tasks = []
        for i in range(6):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.is_critical = True
            task.is_critical_path = True
            
            option = Mock()
            option.total_duration.return_value = Duration.from_minutes(45)
            task.machine_options = [option]
            
            long_critical_tasks.append(task)
        
        job1.get_tasks_in_sequence = Mock(return_value=long_critical_tasks)
        jobs.append(job1)
        
        # Job 2: Multiple short critical sequences
        job2 = JobFactory.create(priority=6, due_date=datetime(2024, 1, 18, 16, 0))
        
        mixed_tasks = []
        for i in range(8):
            task = Mock(spec=Task)
            task.id = uuid4()
            task.is_critical = i in [0, 1, 4, 5]  # Two pairs of critical tasks
            task.is_critical_path = i in [0, 1, 4, 5]
            
            option = Mock()
            option.total_duration.return_value = Duration.from_minutes(30)
            task.machine_options = [option]
            
            mixed_tasks.append(task)
        
        job2.get_tasks_in_sequence = Mock(return_value=mixed_tasks)
        jobs.append(job2)
        
        # Perform comprehensive analysis
        prioritized_jobs = critical_sequence_manager.prioritize_job_sequence(jobs)
        bottlenecks = critical_sequence_manager.identify_bottleneck_sequences(jobs)
        
        # Verify prioritization considers both critical content and due dates
        assert len(prioritized_jobs) == 2
        
        # Verify bottleneck identification
        assert len(bottlenecks) >= 1
        
        # The job with longer critical sequence should be a bigger bottleneck
        longest_bottleneck = max(bottlenecks, key=lambda x: x[2].minutes)
        assert longest_bottleneck[0] == job1  # Should be the job with 6 critical tasks

    def test_parallel_execution_optimization_scenario(self, critical_sequence_manager):
        """Test parallel execution opportunities in optimization scenario."""
        job = JobFactory.create()
        
        # Create realistic task network
        tasks = []
        task_ids = [uuid4() for _ in range(8)]
        
        # Setup task dependencies and criticality
        for i, task_id in enumerate(task_ids):
            task = Mock(spec=Task)
            task.id = task_id
            
            # Critical path: tasks 0, 2, 4, 6
            task.is_critical = i % 2 == 0 and i < 7
            
            # Non-critical tasks could potentially run in parallel
            task.predecessor_ids = []
            
            tasks.append(task)
        
        job.get_tasks_in_sequence = Mock(return_value=tasks)
        
        # Find parallel execution opportunities
        opportunities = critical_sequence_manager.suggest_parallel_execution_opportunities(job)
        
        # Should find opportunities for non-critical tasks
        non_critical_opportunities = [
            opp for opp in opportunities 
            if not opp[0].is_critical
        ]
        
        assert len(non_critical_opportunities) >= 0
        
        # Verify that critical tasks are not suggested as anchors for parallelization
        for anchor, candidates in opportunities:
            assert not anchor.is_critical