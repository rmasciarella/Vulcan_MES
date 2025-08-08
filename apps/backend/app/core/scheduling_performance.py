"""
Performance Monitoring and Optimization for Scheduling Operations

Provides comprehensive performance monitoring, profiling, and optimization
capabilities specifically for scheduling algorithms and solver operations.
"""

import asyncio
import cProfile
import io
import pstats
import time
import tracemalloc
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
import psutil
from prometheus_client import Counter, Gauge, Histogram, Summary

from app.core.observability import get_logger

# Initialize logger
logger = get_logger(__name__)

# Prometheus metrics for scheduling operations
SCHEDULING_DURATION = Histogram(
    'scheduling_operation_duration_seconds',
    'Time spent in scheduling operations',
    ['operation_type', 'algorithm'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

SOLVER_ITERATIONS = Counter(
    'solver_iterations_total',
    'Total number of solver iterations',
    ['solver_type', 'status']
)

CONSTRAINT_VIOLATIONS = Counter(
    'constraint_violations_total',
    'Number of constraint violations detected',
    ['constraint_type', 'severity']
)

OPTIMIZATION_GAP = Gauge(
    'optimization_gap_percentage',
    'Current optimization gap percentage',
    ['schedule_id']
)

CRITICAL_PATH_LENGTH = Gauge(
    'critical_path_length_minutes',
    'Length of critical path in minutes',
    ['schedule_id']
)

RESOURCE_UTILIZATION = Gauge(
    'resource_utilization_percentage',
    'Resource utilization percentage',
    ['resource_type', 'resource_id']
)

MEMORY_USAGE = Gauge(
    'scheduling_memory_usage_mb',
    'Memory usage by scheduling operations in MB',
    ['operation_type']
)


@dataclass
class PerformanceProfile:
    """Performance profile for a scheduling operation."""
    operation_id: str
    operation_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    memory_peak_mb: float = 0.0
    cpu_percent: float = 0.0
    iterations: int = 0
    constraints_checked: int = 0
    variables_created: int = 0
    optimization_gap: float = 0.0
    status: str = "running"
    bottlenecks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SolverMetrics:
    """Detailed metrics from solver operations."""
    solver_type: str
    solve_time_seconds: float
    iterations: int
    nodes_explored: int
    constraints_generated: int
    cuts_added: int
    objective_value: float
    best_bound: float
    gap_percentage: float
    memory_usage_mb: float
    num_variables: int
    num_constraints: int
    status: str


class SchedulingPerformanceMonitor:
    """Monitor and analyze scheduling operation performance."""
    
    def __init__(self):
        self.active_profiles: Dict[str, PerformanceProfile] = {}
        self.completed_profiles: deque = deque(maxlen=1000)
        self.solver_metrics: deque = deque(maxlen=500)
        self.bottleneck_analysis: Dict[str, List[str]] = defaultdict(list)
        self.optimization_history: Dict[UUID, List[float]] = defaultdict(list)
        
        # Performance thresholds
        self.thresholds = {
            "max_solve_time_seconds": 60,
            "max_memory_mb": 1024,
            "max_optimization_gap": 0.1,
            "min_resource_utilization": 0.7,
            "max_critical_path_ratio": 1.2
        }
        
        # CPU profiler
        self.profiler: Optional[cProfile.Profile] = None
        
        # Memory tracking
        self.memory_snapshots: List[tracemalloc.Snapshot] = []
        
    def start_operation(
        self,
        operation_id: str,
        operation_type: str,
        trace_memory: bool = False
    ) -> PerformanceProfile:
        """Start monitoring a scheduling operation."""
        if trace_memory and not tracemalloc.is_tracing():
            tracemalloc.start()
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        profile = PerformanceProfile(
            operation_id=operation_id,
            operation_type=operation_type,
            start_time=datetime.now(),
            memory_start_mb=memory_info.rss / 1024 / 1024,
            cpu_percent=process.cpu_percent()
        )
        
        self.active_profiles[operation_id] = profile
        
        logger.info(
            "Started monitoring scheduling operation",
            operation_id=operation_id,
            operation_type=operation_type
        )
        
        return profile
    
    def end_operation(
        self,
        operation_id: str,
        status: str = "completed",
        solver_metrics: Optional[SolverMetrics] = None
    ) -> PerformanceProfile:
        """End monitoring a scheduling operation."""
        if operation_id not in self.active_profiles:
            logger.warning(f"Operation {operation_id} not found in active profiles")
            return PerformanceProfile(
                operation_id=operation_id,
                operation_type="unknown",
                start_time=datetime.now()
            )
        
        profile = self.active_profiles[operation_id]
        profile.end_time = datetime.now()
        profile.duration_seconds = (
            profile.end_time - profile.start_time
        ).total_seconds()
        profile.status = status
        
        # Capture final memory
        process = psutil.Process()
        memory_info = process.memory_info()
        profile.memory_end_mb = memory_info.rss / 1024 / 1024
        profile.memory_peak_mb = max(profile.memory_start_mb, profile.memory_end_mb)
        
        # Record metrics
        SCHEDULING_DURATION.labels(
            operation_type=profile.operation_type,
            algorithm="default"
        ).observe(profile.duration_seconds)
        
        MEMORY_USAGE.labels(
            operation_type=profile.operation_type
        ).set(profile.memory_peak_mb)
        
        # Add solver metrics if provided
        if solver_metrics:
            self.solver_metrics.append(solver_metrics)
            profile.iterations = solver_metrics.iterations
            profile.optimization_gap = solver_metrics.gap_percentage
            
            SOLVER_ITERATIONS.labels(
                solver_type=solver_metrics.solver_type,
                status=solver_metrics.status
            ).inc(solver_metrics.iterations)
            
            if hasattr(solver_metrics, 'schedule_id'):
                OPTIMIZATION_GAP.labels(
                    schedule_id=str(solver_metrics.schedule_id)
                ).set(solver_metrics.gap_percentage)
        
        # Analyze performance
        self._analyze_performance(profile)
        
        # Move to completed
        del self.active_profiles[operation_id]
        self.completed_profiles.append(profile)
        
        logger.info(
            "Completed monitoring scheduling operation",
            operation_id=operation_id,
            duration_seconds=profile.duration_seconds,
            memory_peak_mb=profile.memory_peak_mb,
            status=status
        )
        
        return profile
    
    def _analyze_performance(self, profile: PerformanceProfile):
        """Analyze performance and identify bottlenecks."""
        bottlenecks = []
        recommendations = []
        
        # Check duration
        if profile.duration_seconds > self.thresholds["max_solve_time_seconds"]:
            bottlenecks.append(f"Long solve time: {profile.duration_seconds:.2f}s")
            recommendations.append("Consider reducing problem size or time limit")
        
        # Check memory usage
        memory_increase = profile.memory_end_mb - profile.memory_start_mb
        if memory_increase > self.thresholds["max_memory_mb"]:
            bottlenecks.append(f"High memory usage: {memory_increase:.2f}MB")
            recommendations.append("Optimize data structures or use streaming")
        
        # Check optimization gap
        if profile.optimization_gap > self.thresholds["max_optimization_gap"]:
            bottlenecks.append(f"Large optimization gap: {profile.optimization_gap:.2%}")
            recommendations.append("Increase solver time limit or improve heuristics")
        
        # Check iteration efficiency
        if profile.iterations > 0 and profile.duration_seconds > 0:
            iterations_per_second = profile.iterations / profile.duration_seconds
            if iterations_per_second < 100:
                bottlenecks.append(f"Low iteration rate: {iterations_per_second:.1f}/s")
                recommendations.append("Simplify constraints or reduce problem complexity")
        
        profile.bottlenecks = bottlenecks
        profile.recommendations = recommendations
        
        # Track bottlenecks
        for bottleneck in bottlenecks:
            self.bottleneck_analysis[profile.operation_type].append(bottleneck)
    
    def profile_critical_path(
        self,
        schedule_id: UUID,
        tasks: List[Any],
        dependencies: Dict[UUID, List[UUID]]
    ) -> Dict[str, Any]:
        """Profile critical path calculation performance."""
        start_time = time.perf_counter()
        memory_before = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Calculate critical path (simplified algorithm)
        critical_path = self._calculate_critical_path(tasks, dependencies)
        
        end_time = time.perf_counter()
        memory_after = psutil.Process().memory_info().rss / 1024 / 1024
        
        duration = end_time - start_time
        memory_used = memory_after - memory_before
        
        # Record metrics
        CRITICAL_PATH_LENGTH.labels(
            schedule_id=str(schedule_id)
        ).set(critical_path["length_minutes"])
        
        return {
            "schedule_id": str(schedule_id),
            "critical_path_length": critical_path["length_minutes"],
            "critical_tasks": critical_path["task_ids"],
            "calculation_time_ms": duration * 1000,
            "memory_used_mb": memory_used,
            "algorithm": "forward_backward_pass",
            "complexity": f"O(V+E) where V={len(tasks)}, E={sum(len(d) for d in dependencies.values())}"
        }
    
    def _calculate_critical_path(
        self,
        tasks: List[Any],
        dependencies: Dict[UUID, List[UUID]]
    ) -> Dict[str, Any]:
        """Calculate critical path using forward-backward pass."""
        # Simplified critical path calculation
        # In production, this would use proper CPM algorithm
        
        task_durations = {task.id: task.duration for task in tasks}
        earliest_start = {}
        latest_start = {}
        
        # Forward pass
        for task in tasks:
            if task.id not in dependencies:
                earliest_start[task.id] = 0
            else:
                max_predecessor = 0
                for pred_id in dependencies.get(task.id, []):
                    if pred_id in earliest_start:
                        pred_end = earliest_start[pred_id] + task_durations.get(pred_id, 0)
                        max_predecessor = max(max_predecessor, pred_end)
                earliest_start[task.id] = max_predecessor
        
        # Calculate makespan
        makespan = max(
            earliest_start.get(t.id, 0) + task_durations.get(t.id, 0)
            for t in tasks
        )
        
        # Backward pass (simplified)
        for task in reversed(tasks):
            latest_start[task.id] = makespan - task_durations.get(task.id, 0)
        
        # Identify critical tasks
        critical_tasks = [
            task.id for task in tasks
            if earliest_start.get(task.id, 0) == latest_start.get(task.id, 0)
        ]
        
        return {
            "length_minutes": makespan,
            "task_ids": critical_tasks,
            "slack_times": {
                t.id: latest_start.get(t.id, 0) - earliest_start.get(t.id, 0)
                for t in tasks
            }
        }
    
    def analyze_resource_utilization(
        self,
        schedule_id: UUID,
        resource_assignments: Dict[UUID, List[Tuple[datetime, datetime]]]
    ) -> Dict[str, Any]:
        """Analyze resource utilization and identify inefficiencies."""
        utilization_stats = {}
        
        for resource_id, assignments in resource_assignments.items():
            if not assignments:
                utilization_stats[str(resource_id)] = {
                    "utilization_percentage": 0.0,
                    "idle_time_minutes": 0,
                    "busy_time_minutes": 0
                }
                continue
            
            # Calculate total busy time
            busy_time = sum(
                (end - start).total_seconds() / 60
                for start, end in assignments
            )
            
            # Calculate total available time
            earliest = min(start for start, _ in assignments)
            latest = max(end for _, end in assignments)
            total_time = (latest - earliest).total_seconds() / 60
            
            utilization = (busy_time / total_time * 100) if total_time > 0 else 0
            
            utilization_stats[str(resource_id)] = {
                "utilization_percentage": utilization,
                "idle_time_minutes": total_time - busy_time,
                "busy_time_minutes": busy_time,
                "fragmentation_score": self._calculate_fragmentation(assignments)
            }
            
            # Record metric
            RESOURCE_UTILIZATION.labels(
                resource_type="machine",
                resource_id=str(resource_id)
            ).set(utilization)
        
        # Calculate overall statistics
        avg_utilization = np.mean([
            stats["utilization_percentage"]
            for stats in utilization_stats.values()
        ]) if utilization_stats else 0
        
        return {
            "schedule_id": str(schedule_id),
            "average_utilization": avg_utilization,
            "resource_stats": utilization_stats,
            "underutilized_resources": [
                rid for rid, stats in utilization_stats.items()
                if stats["utilization_percentage"] < self.thresholds["min_resource_utilization"] * 100
            ],
            "recommendations": self._get_utilization_recommendations(avg_utilization)
        }
    
    def _calculate_fragmentation(
        self,
        assignments: List[Tuple[datetime, datetime]]
    ) -> float:
        """Calculate fragmentation score for resource assignments."""
        if len(assignments) <= 1:
            return 0.0
        
        # Sort assignments by start time
        sorted_assignments = sorted(assignments, key=lambda x: x[0])
        
        # Calculate gaps between assignments
        gaps = []
        for i in range(len(sorted_assignments) - 1):
            gap = (sorted_assignments[i + 1][0] - sorted_assignments[i][1]).total_seconds() / 60
            if gap > 0:
                gaps.append(gap)
        
        if not gaps:
            return 0.0
        
        # Fragmentation score based on number and size of gaps
        avg_gap = np.mean(gaps)
        gap_variance = np.var(gaps)
        fragmentation = (len(gaps) * avg_gap) / 100 + gap_variance / 1000
        
        return min(fragmentation, 1.0)  # Normalize to 0-1
    
    def _get_utilization_recommendations(self, avg_utilization: float) -> List[str]:
        """Get recommendations based on utilization analysis."""
        recommendations = []
        
        if avg_utilization < 50:
            recommendations.append("Very low utilization - consider reducing resource capacity")
        elif avg_utilization < 70:
            recommendations.append("Low utilization - review scheduling algorithm for better packing")
        elif avg_utilization > 95:
            recommendations.append("Very high utilization - may cause delays, consider adding resources")
        
        return recommendations
    
    def start_profiling(self, operation_type: str = "full"):
        """Start CPU profiling for detailed performance analysis."""
        if self.profiler:
            logger.warning("Profiler already running")
            return
        
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        
        logger.info(f"Started CPU profiling for {operation_type}")
    
    def stop_profiling(self, top_n: int = 20) -> Dict[str, Any]:
        """Stop profiling and return analysis."""
        if not self.profiler:
            return {"error": "No profiler running"}
        
        self.profiler.disable()
        
        # Analyze profile
        stream = io.StringIO()
        stats = pstats.Stats(self.profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(top_n)
        
        # Extract top functions
        stats_dict = stats.stats
        top_functions = []
        
        for func, (cc, nc, tt, ct, callers) in sorted(
            stats_dict.items(),
            key=lambda x: x[1][3],  # Sort by cumulative time
            reverse=True
        )[:top_n]:
            top_functions.append({
                "function": f"{func[0]}:{func[1]}:{func[2]}",
                "calls": nc,
                "total_time": tt,
                "cumulative_time": ct,
                "time_per_call": ct / nc if nc > 0 else 0
            })
        
        self.profiler = None
        
        return {
            "profile_output": stream.getvalue(),
            "top_functions": top_functions,
            "total_calls": sum(f["calls"] for f in top_functions),
            "total_time": sum(f["total_time"] for f in top_functions)
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        if not self.completed_profiles:
            return {"message": "No completed operations to analyze"}
        
        recent_profiles = list(self.completed_profiles)[-100:]  # Last 100 operations
        
        # Calculate statistics
        durations = [p.duration_seconds for p in recent_profiles]
        memory_peaks = [p.memory_peak_mb for p in recent_profiles]
        gaps = [p.optimization_gap for p in recent_profiles if p.optimization_gap > 0]
        
        # Identify common bottlenecks
        all_bottlenecks = []
        for profile in recent_profiles:
            all_bottlenecks.extend(profile.bottlenecks)
        
        bottleneck_counts = defaultdict(int)
        for bottleneck in all_bottlenecks:
            # Extract bottleneck type
            bottleneck_type = bottleneck.split(":")[0] if ":" in bottleneck else bottleneck
            bottleneck_counts[bottleneck_type] += 1
        
        return {
            "total_operations": len(self.completed_profiles),
            "active_operations": len(self.active_profiles),
            "average_duration_seconds": np.mean(durations) if durations else 0,
            "p95_duration_seconds": np.percentile(durations, 95) if durations else 0,
            "average_memory_mb": np.mean(memory_peaks) if memory_peaks else 0,
            "peak_memory_mb": max(memory_peaks) if memory_peaks else 0,
            "average_optimization_gap": np.mean(gaps) if gaps else 0,
            "common_bottlenecks": dict(
                sorted(bottleneck_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ),
            "recent_solver_metrics": [
                {
                    "solver_type": m.solver_type,
                    "solve_time": m.solve_time_seconds,
                    "gap": m.gap_percentage,
                    "status": m.status
                }
                for m in list(self.solver_metrics)[-10:]
            ]
        }
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get optimization recommendations based on performance analysis."""
        recommendations = []
        
        if not self.completed_profiles:
            return ["Insufficient data for recommendations"]
        
        recent_profiles = list(self.completed_profiles)[-50:]
        
        # Analyze patterns
        avg_duration = np.mean([p.duration_seconds for p in recent_profiles])
        avg_memory = np.mean([p.memory_peak_mb for p in recent_profiles])
        avg_gap = np.mean([p.optimization_gap for p in recent_profiles if p.optimization_gap > 0])
        
        if avg_duration > 30:
            recommendations.append(
                "High average solve time - Consider: "
                "1) Reducing time limits, "
                "2) Using warm starts, "
                "3) Simplifying constraints"
            )
        
        if avg_memory > 512:
            recommendations.append(
                "High memory usage - Consider: "
                "1) Batch processing, "
                "2) Constraint aggregation, "
                "3) Variable reduction"
            )
        
        if avg_gap > 0.05:
            recommendations.append(
                "Large optimization gaps - Consider: "
                "1) Increasing solver threads, "
                "2) Better initial solutions, "
                "3) Tighter bounds"
            )
        
        # Check for specific bottlenecks
        bottleneck_types = defaultdict(int)
        for profile in recent_profiles:
            for bottleneck in profile.bottlenecks:
                if "constraint" in bottleneck.lower():
                    bottleneck_types["constraints"] += 1
                elif "memory" in bottleneck.lower():
                    bottleneck_types["memory"] += 1
                elif "iteration" in bottleneck.lower():
                    bottleneck_types["iterations"] += 1
        
        if bottleneck_types["constraints"] > len(recent_profiles) * 0.3:
            recommendations.append(
                "Frequent constraint issues - Review constraint formulation and consider preprocessing"
            )
        
        if bottleneck_types["memory"] > len(recent_profiles) * 0.3:
            recommendations.append(
                "Frequent memory issues - Implement memory-efficient data structures"
            )
        
        if bottleneck_types["iterations"] > len(recent_profiles) * 0.3:
            recommendations.append(
                "Low iteration efficiency - Consider using cutting planes or column generation"
            )
        
        return recommendations if recommendations else ["System performing within normal parameters"]


# Global performance monitor instance
scheduling_performance_monitor = SchedulingPerformanceMonitor()


class PerformanceOptimizer:
    """Optimize scheduling algorithm performance based on profiling data."""
    
    def __init__(self, monitor: SchedulingPerformanceMonitor):
        self.monitor = monitor
        self.optimization_cache: Dict[str, Any] = {}
        self.parameter_tuning_history: List[Dict] = []
    
    async def auto_tune_parameters(
        self,
        test_function: Callable,
        parameter_ranges: Dict[str, Tuple[Any, Any]],
        num_iterations: int = 10
    ) -> Dict[str, Any]:
        """Automatically tune algorithm parameters for better performance."""
        best_params = {}
        best_score = float('inf')
        
        for i in range(num_iterations):
            # Generate random parameters within ranges
            test_params = {}
            for param, (min_val, max_val) in parameter_ranges.items():
                if isinstance(min_val, int):
                    test_params[param] = np.random.randint(min_val, max_val + 1)
                else:
                    test_params[param] = np.random.uniform(min_val, max_val)
            
            # Test with these parameters
            profile_id = f"tuning_{i}"
            self.monitor.start_operation(profile_id, "parameter_tuning")
            
            try:
                result = await test_function(**test_params)
                score = self._calculate_score(result)
                
                if score < best_score:
                    best_score = score
                    best_params = test_params.copy()
                
            except Exception as e:
                logger.error(f"Parameter tuning iteration {i} failed: {e}")
                score = float('inf')
            
            profile = self.monitor.end_operation(profile_id)
            
            self.parameter_tuning_history.append({
                "iteration": i,
                "parameters": test_params,
                "score": score,
                "duration": profile.duration_seconds,
                "memory": profile.memory_peak_mb
            })
        
        return {
            "best_parameters": best_params,
            "best_score": best_score,
            "iterations_tested": num_iterations,
            "improvement": (1 - best_score / self.parameter_tuning_history[0]["score"]) * 100
        }
    
    def _calculate_score(self, result: Any) -> float:
        """Calculate optimization score (lower is better)."""
        # Combine multiple objectives
        score = 0.0
        
        if hasattr(result, 'solve_time_seconds'):
            score += result.solve_time_seconds * 10  # Weight solve time
        
        if hasattr(result, 'optimization_gap'):
            score += result.optimization_gap * 100  # Weight gap heavily
        
        if hasattr(result, 'memory_usage_mb'):
            score += result.memory_usage_mb * 0.1  # Light weight for memory
        
        return score
    
    def suggest_algorithm_improvements(self) -> List[Dict[str, Any]]:
        """Suggest algorithm improvements based on performance data."""
        suggestions = []
        
        # Analyze completed profiles
        if len(self.monitor.completed_profiles) < 10:
            return [{"type": "info", "message": "Need more data for suggestions"}]
        
        recent_profiles = list(self.monitor.completed_profiles)[-50:]
        
        # Check for timeout patterns
        timeout_rate = sum(
            1 for p in recent_profiles if p.status == "timeout"
        ) / len(recent_profiles)
        
        if timeout_rate > 0.2:
            suggestions.append({
                "type": "algorithm",
                "severity": "high",
                "message": "High timeout rate detected",
                "recommendation": "Implement iterative deepening or anytime algorithms",
                "expected_improvement": "30-50% reduction in timeouts"
            })
        
        # Check for memory patterns
        memory_peaks = [p.memory_peak_mb for p in recent_profiles]
        if max(memory_peaks) > 1024:
            suggestions.append({
                "type": "memory",
                "severity": "medium",
                "message": "High memory usage detected",
                "recommendation": "Implement lazy constraint generation",
                "expected_improvement": "40-60% memory reduction"
            })
        
        # Check for convergence patterns
        avg_iterations = np.mean([
            p.iterations for p in recent_profiles if p.iterations > 0
        ])
        
        if avg_iterations > 10000:
            suggestions.append({
                "type": "convergence",
                "severity": "medium",
                "message": "Slow convergence detected",
                "recommendation": "Add valid inequalities or symmetry breaking",
                "expected_improvement": "2-3x faster convergence"
            })
        
        return suggestions


# Create global optimizer instance
performance_optimizer = PerformanceOptimizer(scheduling_performance_monitor)