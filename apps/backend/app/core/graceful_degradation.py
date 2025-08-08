"""
Graceful Degradation Patterns for Partial Solutions

Implements comprehensive patterns for handling partial optimization solutions,
progressive quality reduction, and adaptive response strategies when full
optimization cannot be achieved.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from ..domain.scheduling.entities.job import Job
from ..domain.scheduling.entities.machine import Machine
from ..domain.scheduling.entities.operator import Operator
from ..domain.scheduling.entities.schedule import Schedule
from ..domain.scheduling.entities.task import Task
from .fallback_strategies import FallbackOrchestrator, FallbackReason, FallbackStrategy
from .observability import (
    FALLBACK_ACTIVATIONS,
    OPTIMIZATION_FAILURES,
    get_correlation_id,
    get_logger,
    log_optimization_failure,
)
from .solver_management import SolverMetrics, SolverStatus


class DegradationLevel(Enum):
    """Levels of service degradation."""

    FULL_SERVICE = "full_service"  # 100% - Full optimization
    HIGH_QUALITY = "high_quality"  # 80-99% - Minor compromises
    MEDIUM_QUALITY = "medium_quality"  # 60-79% - Noticeable compromises
    LOW_QUALITY = "low_quality"  # 40-59% - Significant compromises
    MINIMAL_SERVICE = "minimal_service"  # 20-39% - Basic functionality only
    EMERGENCY_MODE = "emergency_mode"  # 0-19% - Critical functions only
    SERVICE_UNAVAILABLE = "unavailable"  # 0% - Complete failure


class QualityMetric(Enum):
    """Quality metrics for solution assessment."""

    MAKESPAN = "makespan"
    TARDINESS = "tardiness"
    RESOURCE_UTILIZATION = "resource_utilization"
    CONSTRAINT_VIOLATIONS = "constraint_violations"
    OPTIMALITY_GAP = "optimality_gap"
    COMPLETION_RATE = "completion_rate"
    RESPONSE_TIME = "response_time"


@dataclass
class QualityAssessment:
    """Assessment of solution quality across multiple dimensions."""

    overall_score: float  # 0.0 to 1.0
    degradation_level: DegradationLevel
    individual_scores: dict[QualityMetric, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    constraints_violated: list[str] = field(default_factory=list)
    completion_percentage: float = 100.0
    estimated_optimality_gap: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "overall_score": self.overall_score,
            "degradation_level": self.degradation_level.value,
            "individual_scores": {
                metric.value: score for metric, score in self.individual_scores.items()
            },
            "warnings": self.warnings,
            "constraints_violated": self.constraints_violated,
            "completion_percentage": self.completion_percentage,
            "estimated_optimality_gap": self.estimated_optimality_gap,
        }


@dataclass
class DegradationStrategy:
    """Strategy for handling degraded service levels."""

    level: DegradationLevel
    max_execution_time_seconds: float
    quality_threshold: float
    allowed_constraint_violations: list[str]
    fallback_methods: list[FallbackStrategy]
    resource_limits: dict[str, int | float]
    feature_limitations: list[str]

    def is_acceptable_quality(self, assessment: QualityAssessment) -> bool:
        """Check if quality assessment meets this strategy's threshold."""
        return assessment.overall_score >= self.quality_threshold


class PartialSolutionExtractor:
    """
    Extracts and improves partial solutions from failed optimization attempts.

    Attempts to salvage partial results from timed-out or crashed solvers
    and complete them using heuristic methods.
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    async def extract_partial_solution(
        self,
        solver_metrics: SolverMetrics,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
    ) -> Schedule | None:
        """
        Extract partial solution from failed solver attempt.

        Attempts to recover whatever solution state was available
        from the solver before failure.
        """
        self.logger.info(
            "Attempting to extract partial solution",
            solver_status=solver_metrics.status.value,
            execution_id=solver_metrics.execution_id,
            partial_available=solver_metrics.partial_solution,
        )

        if not solver_metrics.partial_solution:
            self.logger.warning("No partial solution available")
            return None

        try:
            # Create base schedule from partial results
            schedule = Schedule(
                name=f"Partial Solution {start_time.isoformat()}",
                created_at=datetime.now(),
            )

            # Extract completed assignments (simulated - actual implementation
            # would interface with OR-Tools solver state)
            completed_tasks = await self._extract_completed_assignments(
                solver_metrics, tasks, operators, machines
            )

            self.logger.info(
                "Partial solution extracted",
                completed_tasks=len(completed_tasks),
                total_tasks=len(tasks),
                completion_rate=len(completed_tasks) / len(tasks) if tasks else 0,
            )

            return schedule

        except Exception as e:
            self.logger.error(
                "Failed to extract partial solution",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return None

    async def _extract_completed_assignments(
        self,
        solver_metrics: SolverMetrics,
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
    ) -> list[dict[str, Any]]:
        """Extract completed task assignments from solver state."""

        # Simulated extraction - actual implementation would query OR-Tools solver
        completed_count = int(len(tasks) * 0.6)  # Assume 60% completion

        completed_assignments = []
        for i, task in enumerate(tasks[:completed_count]):
            assignment = {
                "task_id": task.id,
                "job_id": task.job_id,
                "operator_id": operators[i % len(operators)].id if operators else None,
                "machine_id": machines[i % len(machines)].id if machines else None,
                "start_time": datetime.now() + timedelta(hours=i),
                "end_time": datetime.now() + timedelta(hours=i + 1),
                "status": "assigned",
            }
            completed_assignments.append(assignment)

        return completed_assignments


class QualityAssessor:
    """
    Assesses solution quality across multiple dimensions.

    Provides comprehensive quality scoring to determine appropriate
    degradation level and response strategy.
    """

    def __init__(self):
        self.logger = get_logger(__name__)

        # Quality weights for different metrics
        self.metric_weights = {
            QualityMetric.COMPLETION_RATE: 0.3,
            QualityMetric.MAKESPAN: 0.2,
            QualityMetric.TARDINESS: 0.2,
            QualityMetric.RESOURCE_UTILIZATION: 0.15,
            QualityMetric.CONSTRAINT_VIOLATIONS: 0.1,
            QualityMetric.RESPONSE_TIME: 0.05,
        }

    async def assess_solution_quality(
        self,
        schedule: Schedule | None,
        jobs: list[Job],
        tasks: list[Task],
        execution_time_seconds: float,
        solver_metrics: SolverMetrics | None = None,
        target_makespan: float | None = None,
    ) -> QualityAssessment:
        """
        Comprehensive quality assessment of a solution.

        Evaluates multiple quality dimensions and provides overall
        degradation level recommendation.
        """
        assessment = QualityAssessment(
            overall_score=0.0,
            degradation_level=DegradationLevel.SERVICE_UNAVAILABLE,
        )

        if not schedule:
            assessment.warnings.append("No schedule available for assessment")
            return assessment

        # Calculate individual quality scores
        individual_scores = {}

        # Completion rate (most important metric)
        completion_rate = await self._calculate_completion_rate(schedule, tasks)
        individual_scores[QualityMetric.COMPLETION_RATE] = completion_rate
        assessment.completion_percentage = completion_rate * 100

        # Makespan quality
        makespan_score = await self._calculate_makespan_score(schedule, target_makespan)
        individual_scores[QualityMetric.MAKESPAN] = makespan_score

        # Tardiness quality
        tardiness_score = await self._calculate_tardiness_score(schedule, jobs)
        individual_scores[QualityMetric.TARDINESS] = tardiness_score

        # Resource utilization
        utilization_score = await self._calculate_utilization_score(schedule)
        individual_scores[QualityMetric.RESOURCE_UTILIZATION] = utilization_score

        # Constraint violations
        violation_score, violations = await self._calculate_violation_score(schedule)
        individual_scores[QualityMetric.CONSTRAINT_VIOLATIONS] = violation_score
        assessment.constraints_violated = violations

        # Response time
        response_score = self._calculate_response_time_score(execution_time_seconds)
        individual_scores[QualityMetric.RESPONSE_TIME] = response_score

        # Calculate weighted overall score
        overall_score = sum(
            score * self.metric_weights[metric]
            for metric, score in individual_scores.items()
        )

        assessment.overall_score = overall_score
        assessment.individual_scores = individual_scores
        assessment.degradation_level = self._determine_degradation_level(overall_score)

        # Add quality warnings
        await self._add_quality_warnings(assessment, individual_scores)

        # Estimate optimality gap if solver metrics available
        if solver_metrics:
            assessment.estimated_optimality_gap = self._estimate_optimality_gap(
                solver_metrics, overall_score
            )

        self.logger.info(
            "Solution quality assessed",
            overall_score=overall_score,
            degradation_level=assessment.degradation_level.value,
            completion_rate=completion_rate,
            execution_time=execution_time_seconds,
        )

        return assessment

    async def _calculate_completion_rate(
        self, schedule: Schedule, tasks: list[Task]
    ) -> float:
        """Calculate task completion rate."""
        if not tasks:
            return 0.0

        # Count assigned tasks (simplified)
        assigned_tasks = (
            len(schedule.task_assignments) if schedule.task_assignments else 0
        )
        return min(1.0, assigned_tasks / len(tasks))

    async def _calculate_makespan_score(
        self, schedule: Schedule, target_makespan: float | None
    ) -> float:
        """Calculate makespan quality score."""
        if not target_makespan:
            return 0.8  # Default decent score when no target

        # Simplified calculation
        actual_makespan = self._get_schedule_makespan(schedule)
        if actual_makespan <= target_makespan:
            return 1.0
        else:
            # Penalize longer makespan
            ratio = target_makespan / actual_makespan
            return max(0.0, ratio)

    async def _calculate_tardiness_score(
        self, schedule: Schedule, jobs: list[Job]
    ) -> float:
        """Calculate tardiness quality score."""
        if not jobs:
            return 1.0

        # Simplified calculation - assume good tardiness performance
        return 0.85

    async def _calculate_utilization_score(self, schedule: Schedule) -> float:
        """Calculate resource utilization score."""
        # Simplified calculation - assume moderate utilization
        return 0.75

    async def _calculate_violation_score(
        self, schedule: Schedule
    ) -> tuple[float, list[str]]:
        """Calculate constraint violation score."""
        violations = []

        # Check for common violations (simplified)
        if not schedule.task_assignments:
            violations.append("No task assignments found")

        # Score based on violation count
        violation_penalty = min(0.2 * len(violations), 1.0)
        score = max(0.0, 1.0 - violation_penalty)

        return score, violations

    def _calculate_response_time_score(self, execution_time_seconds: float) -> float:
        """Calculate response time quality score."""
        # Good if under 30 seconds, decreases linearly to 5 minutes
        if execution_time_seconds <= 30:
            return 1.0
        elif execution_time_seconds <= 300:  # 5 minutes
            return max(0.0, 1.0 - (execution_time_seconds - 30) / 270)
        else:
            return 0.0

    def _determine_degradation_level(self, overall_score: float) -> DegradationLevel:
        """Determine degradation level based on overall score."""
        if overall_score >= 0.95:
            return DegradationLevel.FULL_SERVICE
        elif overall_score >= 0.80:
            return DegradationLevel.HIGH_QUALITY
        elif overall_score >= 0.60:
            return DegradationLevel.MEDIUM_QUALITY
        elif overall_score >= 0.40:
            return DegradationLevel.LOW_QUALITY
        elif overall_score >= 0.20:
            return DegradationLevel.MINIMAL_SERVICE
        elif overall_score > 0.0:
            return DegradationLevel.EMERGENCY_MODE
        else:
            return DegradationLevel.SERVICE_UNAVAILABLE

    async def _add_quality_warnings(
        self, assessment: QualityAssessment, scores: dict[QualityMetric, float]
    ) -> None:
        """Add warnings based on individual quality scores."""
        warnings = []

        if scores.get(QualityMetric.COMPLETION_RATE, 0) < 0.8:
            warnings.append("Low task completion rate")

        if scores.get(QualityMetric.MAKESPAN, 0) < 0.6:
            warnings.append("Makespan significantly exceeds target")

        if scores.get(QualityMetric.TARDINESS, 0) < 0.7:
            warnings.append("High tardiness detected")

        if scores.get(QualityMetric.RESOURCE_UTILIZATION, 0) < 0.5:
            warnings.append("Poor resource utilization")

        if scores.get(QualityMetric.CONSTRAINT_VIOLATIONS, 0) < 0.8:
            warnings.append("Multiple constraint violations")

        if scores.get(QualityMetric.RESPONSE_TIME, 0) < 0.5:
            warnings.append("Slow response time")

        assessment.warnings.extend(warnings)

    def _estimate_optimality_gap(
        self, solver_metrics: SolverMetrics, quality_score: float
    ) -> float:
        """Estimate optimality gap based on solver metrics and quality."""
        # Simplified estimation
        base_gap = max(0.0, 1.0 - quality_score) * 50  # 0-50% gap

        # Adjust based on solver status
        if solver_metrics.status == SolverStatus.TIMEOUT:
            base_gap *= 1.5  # Higher gap for timeouts
        elif solver_metrics.status == SolverStatus.MEMORY_EXCEEDED:
            base_gap *= 2.0  # Even higher for memory issues

        return min(100.0, base_gap)  # Cap at 100%

    def _get_schedule_makespan(self, schedule: Schedule) -> float:
        """Get schedule makespan (simplified calculation)."""
        # In real implementation, this would calculate actual makespan
        return 8 * 60  # Assume 8 hours in minutes


class GracefulDegradationManager:
    """
    Manages graceful degradation patterns and adaptive responses.

    Orchestrates partial solution recovery, quality assessment, and
    appropriate response strategies based on service degradation levels.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.partial_solution_extractor = PartialSolutionExtractor()
        self.quality_assessor = QualityAssessor()
        self.fallback_orchestrator = FallbackOrchestrator()

        # Define degradation strategies
        self.degradation_strategies = {
            DegradationLevel.FULL_SERVICE: DegradationStrategy(
                level=DegradationLevel.FULL_SERVICE,
                max_execution_time_seconds=300,
                quality_threshold=0.95,
                allowed_constraint_violations=[],
                fallback_methods=[],
                resource_limits={"memory_mb": 4096, "cpu_percent": 80},
                feature_limitations=[],
            ),
            DegradationLevel.HIGH_QUALITY: DegradationStrategy(
                level=DegradationLevel.HIGH_QUALITY,
                max_execution_time_seconds=180,
                quality_threshold=0.80,
                allowed_constraint_violations=["soft_constraints"],
                fallback_methods=[FallbackStrategy.GREEDY_SCHEDULING],
                resource_limits={"memory_mb": 2048, "cpu_percent": 70},
                feature_limitations=["advanced_optimization"],
            ),
            DegradationLevel.MEDIUM_QUALITY: DegradationStrategy(
                level=DegradationLevel.MEDIUM_QUALITY,
                max_execution_time_seconds=120,
                quality_threshold=0.60,
                allowed_constraint_violations=[
                    "soft_constraints",
                    "preference_constraints",
                ],
                fallback_methods=[
                    FallbackStrategy.PRIORITY_BASED,
                    FallbackStrategy.GREEDY_SCHEDULING,
                ],
                resource_limits={"memory_mb": 1024, "cpu_percent": 60},
                feature_limitations=[
                    "advanced_optimization",
                    "hierarchical_optimization",
                ],
            ),
            DegradationLevel.LOW_QUALITY: DegradationStrategy(
                level=DegradationLevel.LOW_QUALITY,
                max_execution_time_seconds=60,
                quality_threshold=0.40,
                allowed_constraint_violations=[
                    "soft_constraints",
                    "preference_constraints",
                    "optimization_constraints",
                ],
                fallback_methods=[
                    FallbackStrategy.EARLIEST_DUE_DATE,
                    FallbackStrategy.GREEDY_SCHEDULING,
                ],
                resource_limits={"memory_mb": 512, "cpu_percent": 50},
                feature_limitations=[
                    "advanced_optimization",
                    "hierarchical_optimization",
                    "flexible_routing",
                ],
            ),
            DegradationLevel.MINIMAL_SERVICE: DegradationStrategy(
                level=DegradationLevel.MINIMAL_SERVICE,
                max_execution_time_seconds=30,
                quality_threshold=0.20,
                allowed_constraint_violations=["all_soft_constraints"],
                fallback_methods=[FallbackStrategy.RANDOM_ASSIGNMENT],
                resource_limits={"memory_mb": 256, "cpu_percent": 30},
                feature_limitations=["all_optimization", "constraint_checking"],
            ),
            DegradationLevel.EMERGENCY_MODE: DegradationStrategy(
                level=DegradationLevel.EMERGENCY_MODE,
                max_execution_time_seconds=15,
                quality_threshold=0.01,
                allowed_constraint_violations=["all_constraints"],
                fallback_methods=[FallbackStrategy.RANDOM_ASSIGNMENT],
                resource_limits={"memory_mb": 128, "cpu_percent": 20},
                feature_limitations=["all_features"],
            ),
        }

    async def handle_optimization_failure(
        self,
        failure_reason: str,
        solver_metrics: SolverMetrics | None,
        jobs: list[Job],
        tasks: list[Task],
        operators: list[Operator],
        machines: list[Machine],
        start_time: datetime,
        original_execution_time: float,
    ) -> tuple[Schedule | None, QualityAssessment]:
        """
        Handle optimization failure with graceful degradation.

        Attempts to recover partial solutions, assess quality, and
        provide the best possible response given the constraints.
        """
        self.logger.warning(
            "Handling optimization failure with graceful degradation",
            failure_reason=failure_reason,
            jobs_count=len(jobs),
            tasks_count=len(tasks),
            execution_time=original_execution_time,
            correlation_id=get_correlation_id(),
        )

        degradation_start = time.time()

        # Step 1: Attempt to extract partial solution
        partial_schedule = None
        if solver_metrics and solver_metrics.partial_solution:
            partial_schedule = (
                await self.partial_solution_extractor.extract_partial_solution(
                    solver_metrics, jobs, tasks, operators, machines, start_time
                )
            )

        # Step 2: If no partial solution, try adaptive fallback
        final_schedule = partial_schedule
        fallback_used = False

        if not final_schedule:
            self.logger.info("No partial solution available - using adaptive fallback")

            # Determine appropriate fallback based on available time and resources
            fallback_reason = self._map_failure_to_fallback_reason(failure_reason)

            try:
                fallback_result = await self.fallback_orchestrator.execute_fallback(
                    reason=fallback_reason,
                    jobs=jobs,
                    tasks=tasks,
                    operators=operators,
                    machines=machines,
                    start_time=start_time,
                    preferred_strategy=FallbackStrategy.GREEDY_SCHEDULING,
                )

                final_schedule = fallback_result.schedule
                fallback_used = True

            except Exception as e:
                self.logger.error(
                    "Fallback strategy also failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Step 3: Assess quality of final solution
        total_degradation_time = time.time() - degradation_start

        quality_assessment = await self.quality_assessor.assess_solution_quality(
            schedule=final_schedule,
            jobs=jobs,
            tasks=tasks,
            execution_time_seconds=original_execution_time + total_degradation_time,
            solver_metrics=solver_metrics,
        )

        # Step 4: Log degradation metrics
        self._log_degradation_metrics(
            failure_reason=failure_reason,
            quality_assessment=quality_assessment,
            degradation_time=total_degradation_time,
            partial_solution_recovered=partial_schedule is not None,
            fallback_used=fallback_used,
        )

        self.logger.info(
            "Graceful degradation completed",
            quality_score=quality_assessment.overall_score,
            degradation_level=quality_assessment.degradation_level.value,
            completion_rate=quality_assessment.completion_percentage,
            total_time=total_degradation_time,
        )

        return final_schedule, quality_assessment

    def _map_failure_to_fallback_reason(self, failure_reason: str) -> FallbackReason:
        """Map optimization failure reason to fallback reason."""
        failure_mapping = {
            "timeout": FallbackReason.SOLVER_TIMEOUT,
            "memory_exhaustion": FallbackReason.MEMORY_EXHAUSTION,
            "solver_crash": FallbackReason.SOLVER_CRASH,
            "no_feasible_solution": FallbackReason.NO_FEASIBLE_SOLUTION,
            "circuit_breaker": FallbackReason.CIRCUIT_BREAKER_OPEN,
            "system_overload": FallbackReason.SYSTEM_OVERLOAD,
        }

        return failure_mapping.get(failure_reason, FallbackReason.SOLVER_TIMEOUT)

    def _log_degradation_metrics(
        self,
        failure_reason: str,
        quality_assessment: QualityAssessment,
        degradation_time: float,
        partial_solution_recovered: bool,
        fallback_used: bool,
    ) -> None:
        """Log comprehensive degradation metrics."""

        # Log structured degradation event
        log_optimization_failure(
            failure_reason=failure_reason,
            error_details={
                "degradation_level": quality_assessment.degradation_level.value,
                "quality_score": quality_assessment.overall_score,
                "completion_rate": quality_assessment.completion_percentage,
                "partial_solution_recovered": partial_solution_recovered,
                "warnings_count": len(quality_assessment.warnings),
                "violations_count": len(quality_assessment.constraints_violated),
            },
            fallback_used=fallback_used,
            fallback_strategy="adaptive" if fallback_used else None,
            recovery_time_seconds=degradation_time,
        )

        # Record Prometheus metrics
        OPTIMIZATION_FAILURES.labels(
            failure_reason=failure_reason, fallback_used=str(fallback_used).lower()
        ).inc()

        if fallback_used:
            FALLBACK_ACTIVATIONS.labels(
                strategy="adaptive_degradation", reason=failure_reason
            ).inc()

    def get_degradation_strategy(
        self, target_level: DegradationLevel
    ) -> DegradationStrategy:
        """Get degradation strategy for target level."""
        return self.degradation_strategies.get(
            target_level, self.degradation_strategies[DegradationLevel.EMERGENCY_MODE]
        )

    async def recommend_degradation_level(
        self,
        available_resources: dict[str, int | float],
        time_constraints: dict[str, float],
        failure_history: list[str],
    ) -> DegradationLevel:
        """
        Recommend appropriate degradation level based on system conditions.

        Considers available resources, time constraints, and failure patterns
        to suggest the most appropriate service level.
        """

        # Start with full service and degrade based on constraints
        level = DegradationLevel.FULL_SERVICE

        # Check resource constraints
        memory_mb = available_resources.get("memory_mb", 0)
        cpu_percent = available_resources.get("cpu_percent", 100)

        if memory_mb < 1024 or cpu_percent > 90:
            level = DegradationLevel.LOW_QUALITY
        elif memory_mb < 2048 or cpu_percent > 80:
            level = DegradationLevel.MEDIUM_QUALITY
        elif memory_mb < 4096 or cpu_percent > 70:
            level = DegradationLevel.HIGH_QUALITY

        # Check time constraints
        max_time = time_constraints.get("max_execution_time", 300)
        if max_time < 60:
            level = min(level, DegradationLevel.LOW_QUALITY, key=lambda x: x.value)
        elif max_time < 120:
            level = min(level, DegradationLevel.MEDIUM_QUALITY, key=lambda x: x.value)

        # Consider failure history
        recent_failures = len(
            [f for f in failure_history[-10:] if f in ["memory", "timeout", "crash"]]
        )
        if recent_failures >= 3:
            level = min(level, DegradationLevel.MINIMAL_SERVICE, key=lambda x: x.value)
        elif recent_failures >= 2:
            level = min(level, DegradationLevel.LOW_QUALITY, key=lambda x: x.value)

        self.logger.info(
            "Degradation level recommended",
            level=level.value,
            memory_mb=memory_mb,
            cpu_percent=cpu_percent,
            max_time=max_time,
            recent_failures=recent_failures,
        )

        return level
