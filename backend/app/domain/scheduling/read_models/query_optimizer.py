"""
Query optimization configuration and utilities for scheduling dashboard views.

Provides query hints, caching strategies, and performance monitoring 
for read model queries to ensure fast dashboard response times.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from functools import wraps
import hashlib
import json
import time

from sqlalchemy import text, event
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from pydantic import BaseModel, Field


class QueryHint(BaseModel):
    """Query optimization hint for specific query patterns."""
    
    query_pattern: str  # Pattern to match queries against
    hints: List[str] = Field(default_factory=list)  # SQL hints to apply
    expected_rows: Optional[int] = None  # Expected result set size
    cache_ttl_seconds: Optional[int] = None  # Cache TTL if cacheable
    index_suggestions: List[str] = Field(default_factory=list)  # Suggested indexes


class QueryPerformanceMetrics(BaseModel):
    """Performance metrics for a query execution."""
    
    query_hash: str
    execution_time_ms: float
    rows_returned: int
    execution_timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Query characteristics
    uses_index_scan: bool = False
    uses_sequential_scan: bool = False
    uses_materialized_view: bool = False
    
    # Resource usage
    shared_buffers_hit: Optional[int] = None
    shared_buffers_read: Optional[int] = None
    temp_buffers_used: Optional[int] = None


class QueryOptimizationConfig:
    """Configuration for query optimization strategies."""
    
    # Cache settings
    ENABLE_QUERY_CACHE = True
    DEFAULT_CACHE_TTL = 300  # 5 minutes
    MAX_CACHE_SIZE = 1000
    
    # Performance thresholds
    SLOW_QUERY_THRESHOLD_MS = 1000  # 1 second
    VERY_SLOW_QUERY_THRESHOLD_MS = 5000  # 5 seconds
    
    # Optimization hints by query type
    QUERY_HINTS = {
        "machine_utilization": [
            "SET enable_hashjoin = on",
            "SET enable_mergejoin = on",
            "SET work_mem = '256MB'",
        ],
        "operator_workload": [
            "SET enable_nestloop = off",
            "SET random_page_cost = 1.1",  # Assume SSD storage
        ],
        "job_flow_metrics": [
            "SET effective_cache_size = '4GB'",
            "SET shared_buffers = '256MB'",
        ],
        "dashboard_summary": [
            "SET enable_parallel_hash = on",
            "SET max_parallel_workers_per_gather = 4",
        ]
    }
    
    # Materialized view refresh strategies
    MV_REFRESH_SCHEDULES = {
        "mv_daily_machine_utilization": "0 */6 * * *",  # Every 6 hours
        "mv_daily_operator_workload": "0 */6 * * *",    # Every 6 hours  
        "mv_daily_job_flow_metrics": "0 */4 * * *",     # Every 4 hours
    }
    
    # Query routing for read replicas
    READ_ONLY_QUERIES = [
        "SELECT.*FROM mv_daily_",
        "SELECT.*utilization_rate",
        "SELECT.*completion_rate",
        "SELECT.*throughput",
        "SELECT.*COUNT.*GROUP BY"
    ]


class QueryCache:
    """In-memory cache for frequently accessed query results."""
    
    def __init__(self, max_size: int = 1000):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.max_size = max_size
    
    def get(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached query result if still valid."""
        if query_hash not in self.cache:
            return None
        
        cache_entry = self.cache[query_hash]
        ttl = cache_entry.get('ttl_seconds', QueryOptimizationConfig.DEFAULT_CACHE_TTL)
        cached_at = cache_entry.get('cached_at')
        
        if cached_at and (datetime.utcnow() - cached_at).total_seconds() > ttl:
            # Cache expired
            self._remove(query_hash)
            return None
        
        # Update access time for LRU
        self.access_times[query_hash] = datetime.utcnow()
        return cache_entry.get('data')
    
    def put(
        self, 
        query_hash: str, 
        data: Any, 
        ttl_seconds: int = QueryOptimizationConfig.DEFAULT_CACHE_TTL
    ) -> None:
        """Cache query result with TTL."""
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        self.cache[query_hash] = {
            'data': data,
            'cached_at': datetime.utcnow(),
            'ttl_seconds': ttl_seconds
        }
        self.access_times[query_hash] = datetime.utcnow()
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cached queries matching a pattern."""
        invalidated = 0
        keys_to_remove = []
        
        for key in self.cache.keys():
            if pattern in key:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self._remove(key)
            invalidated += 1
        
        return invalidated
    
    def _remove(self, query_hash: str) -> None:
        """Remove entry from cache."""
        self.cache.pop(query_hash, None)
        self.access_times.pop(query_hash, None)
    
    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        self._remove(lru_key)


class QueryPerformanceMonitor:
    """Monitor and analyze query performance for optimization."""
    
    def __init__(self):
        self.metrics: List[QueryPerformanceMetrics] = []
        self.slow_queries: Dict[str, List[QueryPerformanceMetrics]] = {}
        self.query_cache = QueryCache()
    
    def record_execution(
        self,
        query: str,
        execution_time_ms: float,
        rows_returned: int,
        **kwargs
    ) -> None:
        """Record query execution metrics."""
        query_hash = self._hash_query(query)
        
        metrics = QueryPerformanceMetrics(
            query_hash=query_hash,
            execution_time_ms=execution_time_ms,
            rows_returned=rows_returned,
            **kwargs
        )
        
        self.metrics.append(metrics)
        
        # Track slow queries
        if execution_time_ms > QueryOptimizationConfig.SLOW_QUERY_THRESHOLD_MS:
            if query_hash not in self.slow_queries:
                self.slow_queries[query_hash] = []
            self.slow_queries[query_hash].append(metrics)
        
        # Keep only recent metrics (last 1000)
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def get_slow_queries(self, threshold_ms: float = None) -> List[Dict[str, Any]]:
        """Get slow queries above threshold."""
        threshold = threshold_ms or QueryOptimizationConfig.SLOW_QUERY_THRESHOLD_MS
        
        slow_query_summary = []
        for query_hash, executions in self.slow_queries.items():
            recent_executions = [e for e in executions 
                               if (datetime.utcnow() - e.execution_timestamp).total_seconds() < 3600]
            
            if recent_executions:
                avg_time = sum(e.execution_time_ms for e in recent_executions) / len(recent_executions)
                max_time = max(e.execution_time_ms for e in recent_executions)
                
                slow_query_summary.append({
                    'query_hash': query_hash,
                    'execution_count': len(recent_executions),
                    'avg_execution_time_ms': avg_time,
                    'max_execution_time_ms': max_time,
                    'total_time_ms': sum(e.execution_time_ms for e in recent_executions)
                })
        
        return sorted(slow_query_summary, key=lambda x: x['total_time_ms'], reverse=True)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary."""
        if not self.metrics:
            return {}
        
        recent_metrics = [m for m in self.metrics 
                         if (datetime.utcnow() - m.execution_timestamp).total_seconds() < 3600]
        
        if not recent_metrics:
            return {}
        
        return {
            'total_queries': len(recent_metrics),
            'avg_execution_time_ms': sum(m.execution_time_ms for m in recent_metrics) / len(recent_metrics),
            'slow_query_count': len([m for m in recent_metrics 
                                   if m.execution_time_ms > QueryOptimizationConfig.SLOW_QUERY_THRESHOLD_MS]),
            'cache_hit_potential': len([m for m in recent_metrics if m.rows_returned > 0]) / len(recent_metrics),
            'index_scan_ratio': len([m for m in recent_metrics if m.uses_index_scan]) / len(recent_metrics),
            'sequential_scan_ratio': len([m for m in recent_metrics if m.uses_sequential_scan]) / len(recent_metrics)
        }
    
    def _hash_query(self, query: str) -> str:
        """Create hash for query normalization."""
        # Normalize query by removing specific values
        normalized = query.lower()
        # Remove specific IDs, dates, etc. for better grouping
        # This is simplified - could use proper SQL parsing
        return hashlib.md5(normalized.encode()).hexdigest()[:16]


class QueryOptimizer:
    """Main query optimization service for scheduling read models."""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.performance_monitor = QueryPerformanceMonitor()
        self._setup_query_monitoring()
    
    def execute_optimized_query(
        self,
        query: str,
        params: Dict[str, Any] = None,
        query_type: str = "default",
        cache_ttl: Optional[int] = None
    ) -> List[Any]:
        """Execute query with optimization hints and caching."""
        params = params or {}
        
        # Check cache first
        query_hash = self._hash_query_with_params(query, params)
        
        if QueryOptimizationConfig.ENABLE_QUERY_CACHE:
            cached_result = self.performance_monitor.query_cache.get(query_hash)
            if cached_result is not None:
                return cached_result
        
        # Apply optimization hints
        optimized_query = self._apply_optimization_hints(query, query_type)
        
        # Execute with timing
        start_time = time.time()
        try:
            result = self.db.execute(text(optimized_query), params).fetchall()
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Record performance metrics
            self.performance_monitor.record_execution(
                query=query,
                execution_time_ms=execution_time_ms,
                rows_returned=len(result),
                uses_index_scan=self._analyze_query_plan(optimized_query).get('uses_index_scan', False),
                uses_sequential_scan=self._analyze_query_plan(optimized_query).get('uses_sequential_scan', False)
            )
            
            # Cache result if appropriate
            if (QueryOptimizationConfig.ENABLE_QUERY_CACHE and 
                execution_time_ms > 100 and  # Only cache queries taking >100ms
                len(result) < 10000):  # Don't cache very large results
                
                ttl = cache_ttl or self._determine_cache_ttl(query_type, len(result))
                self.performance_monitor.query_cache.put(query_hash, result, ttl)
            
            return result
            
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.performance_monitor.record_execution(
                query=query,
                execution_time_ms=execution_time_ms,
                rows_returned=0
            )
            raise
    
    def invalidate_cache_by_pattern(self, pattern: str) -> int:
        """Invalidate cached queries matching pattern."""
        return self.performance_monitor.query_cache.invalidate_pattern(pattern)
    
    def get_query_recommendations(self) -> List[Dict[str, Any]]:
        """Get query optimization recommendations."""
        recommendations = []
        
        slow_queries = self.performance_monitor.get_slow_queries()
        
        for slow_query in slow_queries:
            query_hash = slow_query['query_hash']
            avg_time = slow_query['avg_execution_time_ms']
            
            recommendation = {
                'query_hash': query_hash,
                'issue': 'slow_execution',
                'severity': 'high' if avg_time > QueryOptimizationConfig.VERY_SLOW_QUERY_THRESHOLD_MS else 'medium',
                'suggestions': []
            }
            
            # Analyze and suggest improvements
            if avg_time > 2000:  # >2 seconds
                recommendation['suggestions'].extend([
                    "Consider adding appropriate indexes",
                    "Review query for unnecessary JOINs",
                    "Consider using materialized views for complex aggregations"
                ])
            
            if slow_query['execution_count'] > 10:  # Frequently executed
                recommendation['suggestions'].extend([
                    "Cache results if data doesn't change frequently",
                    "Consider pre-computing results in materialized views"
                ])
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def refresh_materialized_views(self, view_names: List[str] = None) -> Dict[str, bool]:
        """Refresh specified materialized views or all if none specified."""
        if not view_names:
            view_names = list(QueryOptimizationConfig.MV_REFRESH_SCHEDULES.keys())
        
        results = {}
        for view_name in view_names:
            try:
                refresh_sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"
                self.db.execute(text(refresh_sql))
                self.db.commit()
                results[view_name] = True
                
                # Invalidate related cached queries
                self.invalidate_cache_by_pattern(view_name)
                
            except Exception as e:
                results[view_name] = False
                self.db.rollback()
        
        return results
    
    def _apply_optimization_hints(self, query: str, query_type: str) -> str:
        """Apply query-specific optimization hints."""
        hints = QueryOptimizationConfig.QUERY_HINTS.get(query_type, [])
        
        if not hints:
            return query
        
        # Prepend hints to query
        hint_prefix = "; ".join(hints) + "; "
        return hint_prefix + query
    
    def _determine_cache_ttl(self, query_type: str, result_size: int) -> int:
        """Determine appropriate cache TTL based on query characteristics."""
        base_ttl = QueryOptimizationConfig.DEFAULT_CACHE_TTL
        
        # Adjust TTL based on query type
        ttl_multipliers = {
            "machine_utilization": 2.0,  # Machine data changes less frequently
            "operator_workload": 1.5,    # Operator data changes moderately
            "job_flow_metrics": 1.0,     # Job data changes frequently
            "dashboard_summary": 0.5     # Dashboard needs fresh data
        }
        
        multiplier = ttl_multipliers.get(query_type, 1.0)
        
        # Reduce TTL for smaller result sets (likely more specific/volatile)
        if result_size < 10:
            multiplier *= 0.5
        elif result_size > 1000:
            multiplier *= 1.5
        
        return int(base_ttl * multiplier)
    
    def _analyze_query_plan(self, query: str) -> Dict[str, Any]:
        """Analyze query execution plan for optimization insights."""
        try:
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
            result = self.db.execute(text(explain_query)).fetchone()
            
            if result and result[0]:
                plan_data = result[0]
                if isinstance(plan_data, str):
                    import json
                    plan_data = json.loads(plan_data)
                
                # Extract plan information
                plan = plan_data[0]['Plan']
                return {
                    'uses_index_scan': 'Index Scan' in plan.get('Node Type', ''),
                    'uses_sequential_scan': 'Seq Scan' in plan.get('Node Type', ''),
                    'total_cost': plan.get('Total Cost', 0),
                    'actual_time': plan.get('Actual Total Time', 0)
                }
        except:
            pass  # Ignore analysis errors
        
        return {}
    
    def _hash_query_with_params(self, query: str, params: Dict[str, Any]) -> str:
        """Create hash for query with parameters."""
        query_with_params = query + json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(query_with_params.encode()).hexdigest()[:16]
    
    def _setup_query_monitoring(self) -> None:
        """Setup automatic query performance monitoring."""
        
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(Engine, "after_cursor_execute")  
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                execution_time = (time.time() - context._query_start_time) * 1000
                
                # Only monitor SELECT queries for read models
                if statement.strip().upper().startswith('SELECT'):
                    self.performance_monitor.record_execution(
                        query=statement,
                        execution_time_ms=execution_time,
                        rows_returned=cursor.rowcount if cursor.rowcount > 0 else 0
                    )


def cached_query(ttl_seconds: int = 300, cache_key_func: Optional[Callable] = None):
    """Decorator for caching query results."""
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if cache_key_func:
                cache_key = cache_key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}_{hash(str(args) + str(kwargs))}"
            
            # Check cache (simplified - would use proper cache implementation)
            # For now, just execute the function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def query_hint(hints: List[str]):
    """Decorator for adding query optimization hints."""
    
    def decorator(func):
        func._query_hints = hints
        return func
    
    return decorator


# Query optimization utilities
def create_optimized_indexes():
    """SQL script generator for creating optimized indexes."""
    return """
    -- Performance monitoring queries
    SELECT 
        schemaname,
        tablename,
        attname,
        n_distinct,
        correlation,
        most_common_freqs
    FROM pg_stats 
    WHERE schemaname = 'public' 
        AND tablename IN ('tasks', 'machines', 'operators', 'jobs')
        AND n_distinct > 100
    ORDER BY schemaname, tablename, n_distinct DESC;
    
    -- Index usage analysis
    SELECT 
        schemaname,
        tablename,
        indexname,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch,
        idx_tup_read / NULLIF(idx_scan, 0) as avg_tuples_per_scan
    FROM pg_stat_user_indexes 
    WHERE schemaname = 'public'
    ORDER BY idx_scan DESC;
    
    -- Table size analysis
    SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
    FROM pg_tables 
    WHERE schemaname = 'public' 
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
    """