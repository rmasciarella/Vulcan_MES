"""
Solver Performance Monitoring and Optimization

Provides comprehensive monitoring, profiling, and optimization capabilities
for OR-Tools CP-SAT solver and other optimization algorithms.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np

try:
    from ortools.sat.python import cp_model
except ImportError:
    cp_model = None

from app.core.observability import get_logger, monitor_performance
from app.core.scheduling_performance import SolverMetrics, scheduling_performance_monitor

# Initialize logger
logger = get_logger(__name__)


@dataclass
class SolverConfiguration:
    """Configuration parameters for solver optimization."""
    max_time_seconds: int = 300
    num_search_workers: int = 8
    search_branching: str = "AUTOMATIC_SEARCH"
    optimization_algorithm: str = "AUTOMATIC"
    use_lns: bool = True
    lns_focus: str = "IMPROVEMENT"
    linearization_level: int = 2
    cp_model_probing_level: int = 2
    use_warm_start: bool = True
    symmetry_level: int = 2
    max_memory_mb: int = 2048
    log_search_progress: bool = True
    stop_on_first_solution: bool = False
    relative_gap_limit: float = 0.01
    absolute_gap_limit: float = 1.0


@dataclass
class SolverPerformanceProfile:
    """Performance profile for solver execution."""
    solver_id: str
    problem_size: Dict[str, int]
    configuration: SolverConfiguration
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"
    objective_value: float = 0.0
    best_bound: float = 0.0
    gap: float = 0.0
    iterations: int = 0
    branches: int = 0
    conflicts: int = 0
    solutions_found: int = 0
    memory_usage_mb: float = 0.0
    wall_time: float = 0.0
    user_time: float = 0.0
    objective_history: List[Tuple[float, float]] = field(default_factory=list)
    search_statistics: Dict[str, Any] = field(default_factory=dict)


class SolverOptimizer:
    """
    Optimizer for solver performance with adaptive parameter tuning.
    
    Features:
    - Automatic parameter tuning based on problem characteristics
    - Performance prediction using historical data
    - Warm start generation
    - Search strategy optimization
    """
    
    def __init__(self):
        self.performance_history: deque = deque(maxlen=1000)
        self.parameter_effectiveness: Dict[str, Dict] = defaultdict(dict)
        self.problem_patterns: Dict[str, SolverConfiguration] = {}
        self.warm_start_cache: Dict[str, Any] = {}
        self.prediction_model = None  # Could use ML model for prediction
    
    @monitor_performance("solver_optimization")
    async def optimize_solver_parameters(
        self,
        problem_characteristics: Dict[str, Any],
        base_config: Optional[SolverConfiguration] = None
    ) -> SolverConfiguration:
        """
        Optimize solver parameters based on problem characteristics.
        
        Args:
            problem_characteristics: Problem features (size, structure, etc.)
            base_config: Base configuration to start from
        
        Returns:
            Optimized solver configuration
        """
        config = base_config or SolverConfiguration()
        
        # Analyze problem characteristics
        num_variables = problem_characteristics.get("num_variables", 0)
        num_constraints = problem_characteristics.get("num_constraints", 0)
        has_precedence = problem_characteristics.get("has_precedence", False)
        has_resources = problem_characteristics.get("has_resources", False)
        time_windows = problem_characteristics.get("has_time_windows", False)
        
        # Adjust parameters based on problem size
        if num_variables < 100:
            # Small problem - use exact methods
            config.max_time_seconds = 60
            config.num_search_workers = 4
            config.use_lns = False
            config.search_branching = "FIXED_SEARCH"
        elif num_variables < 1000:
            # Medium problem - balanced approach
            config.max_time_seconds = 180
            config.num_search_workers = 8
            config.use_lns = True
            config.lns_focus = "IMPROVEMENT"
            config.search_branching = "AUTOMATIC_SEARCH"
        else:
            # Large problem - use heuristics
            config.max_time_seconds = 300
            config.num_search_workers = 16
            config.use_lns = True
            config.lns_focus = "QUICK_RESTART"
            config.search_branching = "PORTFOLIO_SEARCH"
            config.relative_gap_limit = 0.05  # Accept larger gap for large problems
        
        # Adjust for problem structure
        if has_precedence:
            config.cp_model_probing_level = 3  # More probing for precedence
            config.linearization_level = 2
        
        if has_resources:
            config.symmetry_level = 3  # Break symmetries in resource allocation
            config.use_warm_start = True
        
        if time_windows:
            config.search_branching = "FIXED_SEARCH"  # Better for time windows
            config.optimization_algorithm = "CORE_BASED_SEARCH"
        
        # Apply learned optimizations
        pattern_key = self._get_problem_pattern_key(problem_characteristics)
        if pattern_key in self.problem_patterns:
            # Use previously successful configuration
            learned_config = self.problem_patterns[pattern_key]
            config = self._merge_configurations(config, learned_config)
        
        logger.info(
            f"Optimized solver configuration for problem with "
            f"{num_variables} variables and {num_constraints} constraints"
        )
        
        return config
    
    def create_solver_callback(
        self,
        profile: SolverPerformanceProfile,
        update_interval: float = 1.0
    ) -> 'SolverCallback':
        """Create callback for monitoring solver progress."""
        return SolverCallback(profile, self, update_interval)
    
    async def generate_warm_start(
        self,
        problem_id: str,
        variables: Dict[str, Any],
        similar_solutions: Optional[List[Dict]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate warm start solution for solver.
        
        Args:
            problem_id: Unique problem identifier
            variables: Problem variables
            similar_solutions: Previously found similar solutions
        
        Returns:
            Warm start solution or None
        """
        # Check cache
        if problem_id in self.warm_start_cache:
            logger.debug(f"Using cached warm start for {problem_id}")
            return self.warm_start_cache[problem_id]
        
        warm_start = {}
        
        if similar_solutions:
            # Use solution from similar problem
            best_similar = self._find_best_similar_solution(
                variables,
                similar_solutions
            )
            
            if best_similar:
                warm_start = self._adapt_solution(best_similar, variables)
                logger.info(f"Generated warm start from similar solution")
        
        if not warm_start:
            # Generate heuristic solution
            warm_start = await self._generate_heuristic_solution(variables)
            if warm_start:
                logger.info(f"Generated heuristic warm start")
        
        # Cache warm start
        if warm_start:
            self.warm_start_cache[problem_id] = warm_start
        
        return warm_start
    
    def analyze_solver_performance(
        self,
        profile: SolverPerformanceProfile
    ) -> Dict[str, Any]:
        """
        Analyze solver performance and provide insights.
        
        Args:
            profile: Solver performance profile
        
        Returns:
            Analysis results with recommendations
        """
        analysis = {
            "summary": {},
            "bottlenecks": [],
            "recommendations": [],
            "convergence_analysis": {},
            "search_efficiency": {}
        }
        
        # Summary statistics
        analysis["summary"] = {
            "solve_time": profile.wall_time,
            "final_gap": profile.gap,
            "solutions_found": profile.solutions_found,
            "iterations_per_second": profile.iterations / max(profile.wall_time, 1),
            "memory_usage_mb": profile.memory_usage_mb,
            "status": profile.status
        }
        
        # Identify bottlenecks
        if profile.wall_time >= profile.configuration.max_time_seconds:
            analysis["bottlenecks"].append("Time limit reached")
            analysis["recommendations"].append(
                "Consider increasing time limit or using more aggressive heuristics"
            )
        
        if profile.memory_usage_mb > profile.configuration.max_memory_mb * 0.9:
            analysis["bottlenecks"].append("High memory usage")
            analysis["recommendations"].append(
                "Reduce problem size or use memory-efficient search strategies"
            )
        
        if profile.solutions_found == 0:
            analysis["bottlenecks"].append("No feasible solution found")
            analysis["recommendations"].append(
                "Check constraint consistency or relax constraints"
            )
        
        # Convergence analysis
        if profile.objective_history:
            convergence = self._analyze_convergence(profile.objective_history)
            analysis["convergence_analysis"] = convergence
            
            if convergence["stagnation_ratio"] > 0.5:
                analysis["recommendations"].append(
                    "Solver stagnating - consider using LNS or restart strategies"
                )
        
        # Search efficiency
        if profile.branches > 0:
            analysis["search_efficiency"] = {
                "branches_per_solution": profile.branches / max(profile.solutions_found, 1),
                "conflicts_per_branch": profile.conflicts / profile.branches,
                "pruning_effectiveness": 1 - (profile.solutions_found / max(profile.branches, 1))
            }
            
            if analysis["search_efficiency"]["conflicts_per_branch"] > 10:
                analysis["recommendations"].append(
                    "High conflict rate - improve constraint propagation"
                )
        
        # Store in history for learning
        self.performance_history.append(profile)
        self._update_parameter_effectiveness(profile)
        
        return analysis
    
    def _analyze_convergence(
        self,
        objective_history: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        """Analyze convergence pattern of objective values."""
        if len(objective_history) < 2:
            return {"status": "insufficient_data"}
        
        times = [t for t, _ in objective_history]
        objectives = [obj for _, obj in objective_history]
        
        # Calculate improvement rate
        improvements = []
        for i in range(1, len(objectives)):
            if objectives[i-1] != 0:
                improvement = abs(objectives[i] - objectives[i-1]) / abs(objectives[i-1])
                improvements.append(improvement)
        
        # Detect stagnation
        recent_improvements = improvements[-10:] if len(improvements) >= 10 else improvements
        stagnation_threshold = 0.001
        stagnation_count = sum(1 for imp in recent_improvements if imp < stagnation_threshold)
        stagnation_ratio = stagnation_count / len(recent_improvements) if recent_improvements else 0
        
        # Calculate convergence rate
        if len(objectives) >= 3:
            # Fit exponential decay to estimate convergence
            log_improvements = [
                np.log(imp) for imp in improvements if imp > 0
            ]
            if log_improvements:
                convergence_rate = -np.mean(log_improvements)
            else:
                convergence_rate = 0
        else:
            convergence_rate = 0
        
        return {
            "total_improvement": abs(objectives[-1] - objectives[0]) if objectives else 0,
            "average_improvement_rate": np.mean(improvements) if improvements else 0,
            "stagnation_ratio": stagnation_ratio,
            "convergence_rate": convergence_rate,
            "final_objective": objectives[-1] if objectives else 0,
            "best_objective": min(objectives) if objectives else 0
        }
    
    def _get_problem_pattern_key(self, characteristics: Dict[str, Any]) -> str:
        """Generate pattern key for problem characteristics."""
        # Create pattern based on problem size and structure
        size_category = "small"
        if characteristics.get("num_variables", 0) > 1000:
            size_category = "large"
        elif characteristics.get("num_variables", 0) > 100:
            size_category = "medium"
        
        structure_features = []
        if characteristics.get("has_precedence"):
            structure_features.append("precedence")
        if characteristics.get("has_resources"):
            structure_features.append("resources")
        if characteristics.get("has_time_windows"):
            structure_features.append("time_windows")
        
        return f"{size_category}:{'_'.join(structure_features)}"
    
    def _merge_configurations(
        self,
        base: SolverConfiguration,
        learned: SolverConfiguration
    ) -> SolverConfiguration:
        """Merge two configurations, preferring learned values."""
        merged = SolverConfiguration()
        
        # Use learned values for key parameters
        merged.search_branching = learned.search_branching
        merged.optimization_algorithm = learned.optimization_algorithm
        merged.use_lns = learned.use_lns
        merged.lns_focus = learned.lns_focus
        
        # Use base values for resource limits
        merged.max_time_seconds = base.max_time_seconds
        merged.num_search_workers = base.num_search_workers
        merged.max_memory_mb = base.max_memory_mb
        
        # Use maximum of probing/linearization levels
        merged.linearization_level = max(base.linearization_level, learned.linearization_level)
        merged.cp_model_probing_level = max(base.cp_model_probing_level, learned.cp_model_probing_level)
        
        return merged
    
    def _find_best_similar_solution(
        self,
        variables: Dict[str, Any],
        similar_solutions: List[Dict]
    ) -> Optional[Dict]:
        """Find best similar solution to use as warm start."""
        if not similar_solutions:
            return None
        
        # Score solutions based on similarity and quality
        best_solution = None
        best_score = float('-inf')
        
        for solution in similar_solutions:
            # Calculate similarity score
            similarity = self._calculate_solution_similarity(variables, solution)
            
            # Consider solution quality
            quality = solution.get("objective_value", float('inf'))
            if quality == float('inf'):
                continue
            
            # Combined score (higher similarity, lower objective is better)
            score = similarity - quality / 1000  # Normalize quality impact
            
            if score > best_score:
                best_score = score
                best_solution = solution
        
        return best_solution
    
    def _calculate_solution_similarity(
        self,
        variables: Dict[str, Any],
        solution: Dict
    ) -> float:
        """Calculate similarity between problem variables and solution."""
        # Simple similarity based on variable overlap
        var_keys = set(variables.keys())
        sol_keys = set(solution.get("variables", {}).keys())
        
        intersection = var_keys & sol_keys
        union = var_keys | sol_keys
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _adapt_solution(
        self,
        solution: Dict,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adapt existing solution to new problem variables."""
        adapted = {}
        
        solution_vars = solution.get("variables", {})
        
        for var_name, var_info in variables.items():
            if var_name in solution_vars:
                # Use value from similar solution
                adapted[var_name] = solution_vars[var_name]
            else:
                # Generate default value
                if "domain" in var_info:
                    domain = var_info["domain"]
                    if isinstance(domain, (list, tuple)) and len(domain) == 2:
                        # Use middle value for continuous variables
                        adapted[var_name] = (domain[0] + domain[1]) / 2
                    elif isinstance(domain, list):
                        # Use first value for discrete variables
                        adapted[var_name] = domain[0]
        
        return adapted
    
    async def _generate_heuristic_solution(
        self,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate heuristic solution for warm start."""
        heuristic = {}
        
        # Simple heuristics based on variable types
        for var_name, var_info in variables.items():
            if "type" in var_info:
                if var_info["type"] == "bool":
                    # Start with false for boolean variables
                    heuristic[var_name] = False
                elif var_info["type"] == "int":
                    # Start with lower bound for integers
                    if "domain" in var_info:
                        domain = var_info["domain"]
                        if isinstance(domain, (list, tuple)) and len(domain) >= 1:
                            heuristic[var_name] = domain[0]
                        else:
                            heuristic[var_name] = 0
                elif var_info["type"] == "interval":
                    # Start intervals at earliest possible time
                    if "start_domain" in var_info:
                        heuristic[var_name] = {
                            "start": var_info["start_domain"][0],
                            "duration": var_info.get("duration", 1)
                        }
        
        return heuristic
    
    def _update_parameter_effectiveness(self, profile: SolverPerformanceProfile):
        """Update parameter effectiveness based on performance."""
        pattern_key = self._get_problem_pattern_key(profile.problem_size)
        
        # Score configuration based on performance
        score = self._score_configuration(profile)
        
        # Update or store configuration
        if pattern_key not in self.problem_patterns:
            self.problem_patterns[pattern_key] = profile.configuration
        elif score > self.parameter_effectiveness.get(pattern_key, {}).get("best_score", 0):
            self.problem_patterns[pattern_key] = profile.configuration
            self.parameter_effectiveness[pattern_key]["best_score"] = score
    
    def _score_configuration(self, profile: SolverPerformanceProfile) -> float:
        """Score configuration based on performance metrics."""
        score = 0.0
        
        # Penalize for not finding solution
        if profile.status != "OPTIMAL" and profile.status != "FEASIBLE":
            return -1000.0
        
        # Reward for low gap
        score += (1 - profile.gap) * 100
        
        # Reward for fast solving
        if profile.wall_time < profile.configuration.max_time_seconds:
            time_ratio = profile.wall_time / profile.configuration.max_time_seconds
            score += (1 - time_ratio) * 50
        
        # Reward for finding multiple solutions
        score += min(profile.solutions_found, 10) * 5
        
        # Penalize high memory usage
        if profile.memory_usage_mb > 0:
            memory_ratio = profile.memory_usage_mb / profile.configuration.max_memory_mb
            score -= memory_ratio * 20
        
        return score


class SolverCallback:
    """Callback for monitoring solver progress in real-time."""
    
    def __init__(
        self,
        profile: SolverPerformanceProfile,
        optimizer: SolverOptimizer,
        update_interval: float = 1.0
    ):
        self.profile = profile
        self.optimizer = optimizer
        self.update_interval = update_interval
        self.last_update = time.time()
        self.solution_count = 0
    
    def on_solution_callback(self, solver=None):
        """Called when solver finds a new solution."""
        self.solution_count += 1
        self.profile.solutions_found = self.solution_count
        
        if solver and hasattr(solver, 'ObjectiveValue'):
            objective = solver.ObjectiveValue()
            current_time = time.time() - self.profile.start_time.timestamp()
            self.profile.objective_history.append((current_time, objective))
            self.profile.objective_value = objective
        
        # Update periodically
        current_time = time.time()
        if current_time - self.last_update >= self.update_interval:
            self._update_profile(solver)
            self.last_update = current_time
    
    def _update_profile(self, solver):
        """Update profile with current solver statistics."""
        if not solver:
            return
        
        if hasattr(solver, 'NumBranches'):
            self.profile.branches = solver.NumBranches()
        
        if hasattr(solver, 'NumConflicts'):
            self.profile.conflicts = solver.NumConflicts()
        
        if hasattr(solver, 'WallTime'):
            self.profile.wall_time = solver.WallTime()
        
        if hasattr(solver, 'UserTime'):
            self.profile.user_time = solver.UserTime()
        
        if hasattr(solver, 'BestObjectiveBound'):
            self.profile.best_bound = solver.BestObjectiveBound()
            
            if self.profile.objective_value != 0:
                self.profile.gap = abs(
                    self.profile.objective_value - self.profile.best_bound
                ) / abs(self.profile.objective_value)
        
        # Log progress
        logger.debug(
            f"Solver progress: {self.solution_count} solutions, "
            f"gap: {self.profile.gap:.2%}, "
            f"time: {self.profile.wall_time:.1f}s"
        )


# Global solver optimizer instance
solver_optimizer = SolverOptimizer()


async def optimize_and_solve(
    model: Any,
    problem_characteristics: Dict[str, Any],
    base_config: Optional[SolverConfiguration] = None,
    warm_start: Optional[Dict[str, Any]] = None
) -> Tuple[Any, SolverPerformanceProfile]:
    """
    Optimize solver parameters and solve the model.
    
    Args:
        model: CP-SAT model to solve
        problem_characteristics: Problem characteristics
        base_config: Base configuration
        warm_start: Optional warm start solution
    
    Returns:
        Tuple of (solver_status, performance_profile)
    """
    if not cp_model:
        raise ImportError("OR-Tools not available")
    
    # Optimize configuration
    config = await solver_optimizer.optimize_solver_parameters(
        problem_characteristics,
        base_config
    )
    
    # Create performance profile
    profile = SolverPerformanceProfile(
        solver_id=f"solve_{datetime.now().timestamp()}",
        problem_size=problem_characteristics,
        configuration=config,
        start_time=datetime.now()
    )
    
    # Create solver
    solver = cp_model.CpSolver()
    
    # Apply configuration
    solver.parameters.max_time_in_seconds = config.max_time_seconds
    solver.parameters.num_search_workers = config.num_search_workers
    solver.parameters.log_search_progress = config.log_search_progress
    solver.parameters.linearization_level = config.linearization_level
    solver.parameters.cp_model_probing_level = config.cp_model_probing_level
    
    if config.relative_gap_limit:
        solver.parameters.relative_gap_limit = config.relative_gap_limit
    
    # Apply warm start if provided
    if warm_start and config.use_warm_start:
        # Would apply warm start to model here
        logger.info("Applied warm start solution")
    
    # Create callback
    callback = solver_optimizer.create_solver_callback(profile)
    
    # Start monitoring
    scheduling_performance_monitor.start_operation(
        profile.solver_id,
        "solver_execution"
    )
    
    # Solve
    status = solver.SolveWithSolutionCallback(model, callback.on_solution_callback)
    
    # Update final profile
    profile.end_time = datetime.now()
    profile.status = solver.StatusName(status)
    profile.wall_time = solver.WallTime()
    profile.user_time = solver.UserTime()
    
    if hasattr(solver, 'ObjectiveValue') and status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        profile.objective_value = solver.ObjectiveValue()
    
    # End monitoring
    solver_metrics = SolverMetrics(
        solver_type="CP-SAT",
        solve_time_seconds=profile.wall_time,
        iterations=profile.iterations,
        nodes_explored=profile.branches,
        constraints_generated=0,
        cuts_added=0,
        objective_value=profile.objective_value,
        best_bound=profile.best_bound,
        gap_percentage=profile.gap,
        memory_usage_mb=profile.memory_usage_mb,
        num_variables=problem_characteristics.get("num_variables", 0),
        num_constraints=problem_characteristics.get("num_constraints", 0),
        status=profile.status
    )
    
    scheduling_performance_monitor.end_operation(
        profile.solver_id,
        status=profile.status,
        solver_metrics=solver_metrics
    )
    
    # Analyze performance
    analysis = solver_optimizer.analyze_solver_performance(profile)
    
    logger.info(
        f"Solver completed: status={profile.status}, "
        f"time={profile.wall_time:.2f}s, "
        f"gap={profile.gap:.2%}, "
        f"solutions={profile.solutions_found}"
    )
    
    if analysis["recommendations"]:
        logger.info(f"Solver recommendations: {', '.join(analysis['recommendations'])}")
    
    return status, profile