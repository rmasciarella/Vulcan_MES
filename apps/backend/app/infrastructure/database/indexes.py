"""
Database index definitions and query optimization strategies.

This module defines strategic indexes for optimizing scheduling queries,
including composite indexes for complex joins and filtered queries.
"""

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages database indexes for performance optimization."""

    # Define strategic indexes for scheduling domain
    INDEXES = [
        # Job indexes
        {
            "name": "idx_jobs_status_due_date",
            "table": "jobs",
            "columns": ["status", "due_date"],
            "where": "status NOT IN ('COMPLETED', 'CANCELLED')",
            "description": "Optimize active job queries by status and due date",
        },
        {
            "name": "idx_jobs_customer_status",
            "table": "jobs",
            "columns": ["customer_name", "status"],
            "description": "Optimize customer job lookups",
        },
        {
            "name": "idx_jobs_priority_status_due",
            "table": "jobs",
            "columns": ["priority", "status", "due_date"],
            "where": "status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')",
            "description": "Optimize priority scheduling queries",
        },
        {
            "name": "idx_jobs_created_by_created_at",
            "table": "jobs",
            "columns": ["created_by", "created_at DESC"],
            "description": "Optimize user job history queries",
        },
        # Task indexes
        {
            "name": "idx_tasks_job_sequence",
            "table": "tasks",
            "columns": ["job_id", "sequence_in_job"],
            "unique": True,
            "description": "Ensure unique task sequence and optimize job task lookups",
        },
        {
            "name": "idx_tasks_status_planned_start",
            "table": "tasks",
            "columns": ["status", "planned_start_time"],
            "where": "status IN ('PENDING', 'READY')",
            "description": "Optimize task scheduling queries",
        },
        {
            "name": "idx_tasks_machine_time_range",
            "table": "tasks",
            "columns": [
                "assigned_machine_id",
                "planned_start_time",
                "planned_end_time",
            ],
            "where": "assigned_machine_id IS NOT NULL",
            "description": "Optimize machine utilization queries",
        },
        {
            "name": "idx_tasks_critical_path",
            "table": "tasks",
            "columns": ["job_id", "is_critical_path"],
            "where": "is_critical_path = true",
            "description": "Optimize critical path queries",
        },
        {
            "name": "idx_tasks_operation_status",
            "table": "tasks",
            "columns": ["operation_id", "status"],
            "description": "Optimize operation-based queries",
        },
        # Machine indexes
        {
            "name": "idx_machines_zone_status",
            "table": "machines",
            "columns": ["zone", "status"],
            "description": "Optimize zone-based machine queries",
        },
        {
            "name": "idx_machines_type_status",
            "table": "machines",
            "columns": ["machine_type", "status"],
            "where": "status = 'AVAILABLE'",
            "description": "Optimize available machine type queries",
        },
        {
            "name": "idx_machines_maintenance_date",
            "table": "machines",
            "columns": ["next_maintenance_date"],
            "where": "next_maintenance_date IS NOT NULL",
            "description": "Optimize maintenance scheduling queries",
        },
        # Operator indexes
        {
            "name": "idx_operators_zone_shift_status",
            "table": "operators",
            "columns": ["zone", "shift_pattern", "status"],
            "description": "Optimize operator availability queries by zone and shift",
        },
        {
            "name": "idx_operators_employee_id",
            "table": "operators",
            "columns": ["employee_id"],
            "unique": True,
            "description": "Ensure unique employee IDs with fast lookup",
        },
        # Operator assignment indexes
        {
            "name": "idx_operator_assignments_task_operator",
            "table": "operator_assignments",
            "columns": ["task_id", "operator_id"],
            "unique": True,
            "description": "Prevent duplicate assignments and optimize lookups",
        },
        {
            "name": "idx_operator_assignments_operator_time",
            "table": "operator_assignments",
            "columns": ["operator_id", "planned_start_time", "planned_end_time"],
            "description": "Optimize operator schedule queries",
        },
        {
            "name": "idx_operator_assignments_type",
            "table": "operator_assignments",
            "columns": ["assignment_type"],
            "description": "Optimize assignment type filtering",
        },
        # Skill indexes
        {
            "name": "idx_operator_skills_operator_skill",
            "table": "operator_skills",
            "columns": ["operator_id", "skill_type_id"],
            "unique": True,
            "description": "Unique operator-skill pairs with fast lookup",
        },
        {
            "name": "idx_operator_skills_level",
            "table": "operator_skills",
            "columns": ["skill_type_id", "level"],
            "description": "Optimize skill level queries",
        },
        {
            "name": "idx_machine_skill_requirements",
            "table": "machine_skill_requirements",
            "columns": ["machine_id", "skill_type_id"],
            "unique": True,
            "description": "Unique machine-skill requirements",
        },
        # Covering indexes for common query patterns
        {
            "name": "idx_jobs_covering_dashboard",
            "table": "jobs",
            "columns": [
                "status",
                "priority",
                "due_date",
                "job_number",
                "customer_name",
                "completion_percentage",
            ],
            "include": ["id", "created_at"],
            "description": "Covering index for dashboard queries",
        },
        {
            "name": "idx_tasks_covering_schedule",
            "table": "tasks",
            "columns": ["planned_start_time", "planned_end_time", "status"],
            "include": ["job_id", "assigned_machine_id", "operation_id"],
            "where": "planned_start_time IS NOT NULL",
            "description": "Covering index for schedule views",
        },
    ]

    @staticmethod
    def create_index_sql(index_def: dict[str, Any]) -> str:
        """Generate SQL for creating an index."""
        unique = "UNIQUE " if index_def.get("unique") else ""
        name = index_def["name"]
        table = index_def["table"]
        columns = ", ".join(index_def["columns"])

        sql = f"CREATE {unique}INDEX IF NOT EXISTS {name} ON {table} ({columns})"

        # Add INCLUDE clause for covering indexes (PostgreSQL 11+)
        if "include" in index_def:
            include_cols = ", ".join(index_def["include"])
            sql += f" INCLUDE ({include_cols})"

        # Add WHERE clause for partial indexes
        if "where" in index_def:
            sql += f" WHERE {index_def['where']}"

        return sql

    @staticmethod
    def drop_index_sql(index_name: str) -> str:
        """Generate SQL for dropping an index."""
        return f"DROP INDEX IF EXISTS {index_name}"

    @classmethod
    def create_all_indexes(cls, session: Session) -> dict[str, bool]:
        """
        Create all defined indexes.

        Returns:
            Dictionary mapping index names to creation success status
        """
        results = {}

        for index_def in cls.INDEXES:
            try:
                sql = cls.create_index_sql(index_def)
                session.execute(text(sql))
                session.commit()
                results[index_def["name"]] = True
                logger.info(f"Created index: {index_def['name']}")
            except Exception as e:
                session.rollback()
                results[index_def["name"]] = False
                logger.error(f"Failed to create index {index_def['name']}: {e}")

        return results

    @classmethod
    def analyze_tables(cls, session: Session) -> None:
        """Update table statistics for query optimization."""
        tables = [
            "jobs",
            "tasks",
            "machines",
            "operators",
            "operator_assignments",
            "operator_skills",
            "machine_skill_requirements",
            "skill_types",
        ]

        for table in tables:
            try:
                session.execute(text(f"ANALYZE {table}"))
                session.commit()
                logger.info(f"Analyzed table: {table}")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to analyze table {table}: {e}")

    @classmethod
    def get_index_usage_stats(cls, session: Session) -> list[dict[str, Any]]:
        """Get index usage statistics."""
        query = text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as index_scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                CASE
                    WHEN idx_scan = 0 THEN 'UNUSED'
                    WHEN idx_scan < 100 THEN 'RARELY_USED'
                    WHEN idx_scan < 1000 THEN 'MODERATELY_USED'
                    ELSE 'FREQUENTLY_USED'
                END as usage_category
            FROM pg_stat_user_indexes
            WHERE schemaname = 'public'
            ORDER BY idx_scan DESC
        """)

        result = session.execute(query)
        return [dict(row._mapping) for row in result]

    @classmethod
    def get_missing_indexes_suggestions(cls, session: Session) -> list[dict[str, Any]]:
        """
        Analyze query patterns and suggest missing indexes.

        Uses pg_stat_statements if available to analyze slow queries.
        """
        suggestions = []

        # Check for missing foreign key indexes
        fk_query = text("""
            SELECT
                c.conname AS constraint_name,
                t.relname AS table_name,
                a.attname AS column_name,
                'FOREIGN_KEY' as suggestion_type,
                'Missing index on foreign key column' as reason
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(c.conkey)
            LEFT JOIN pg_index i ON i.indrelid = t.oid AND a.attnum = ANY(i.indkey)
            WHERE c.contype = 'f'
            AND i.indexrelid IS NULL
            AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """)

        try:
            result = session.execute(fk_query)
            for row in result:
                suggestions.append(
                    {
                        "table": row.table_name,
                        "column": row.column_name,
                        "type": row.suggestion_type,
                        "reason": row.reason,
                        "suggested_index": f"CREATE INDEX idx_{row.table_name}_{row.column_name} ON {row.table_name} ({row.column_name})",
                    }
                )
        except Exception as e:
            logger.error(f"Failed to analyze missing foreign key indexes: {e}")

        # Check for frequently filtered columns without indexes
        filter_query = text("""
            SELECT
                tablename,
                attname as column_name,
                n_distinct,
                null_frac,
                avg_width,
                'FILTER_COLUMN' as suggestion_type,
                'High cardinality column frequently used in WHERE clauses' as reason
            FROM pg_stats
            WHERE schemaname = 'public'
            AND n_distinct > 100
            AND null_frac < 0.5
            AND tablename IN ('jobs', 'tasks', 'machines', 'operators')
            AND attname NOT IN (
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = (tablename)::regclass
            )
        """)

        try:
            result = session.execute(filter_query)
            for row in result:
                suggestions.append(
                    {
                        "table": row.tablename,
                        "column": row.column_name,
                        "type": row.suggestion_type,
                        "reason": row.reason,
                        "cardinality": row.n_distinct,
                        "suggested_index": f"CREATE INDEX idx_{row.tablename}_{row.column_name} ON {row.tablename} ({row.column_name})",
                    }
                )
        except Exception as e:
            logger.error(f"Failed to analyze filter column indexes: {e}")

        return suggestions

    @classmethod
    def get_index_bloat(cls, session: Session) -> list[dict[str, Any]]:
        """Identify bloated indexes that need rebuilding."""
        query = text("""
            SELECT
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(real_size) as index_size,
                pg_size_pretty(extra_size) as bloat_size,
                round(100 * (extra_size::numeric / real_size::numeric), 2) as bloat_percentage
            FROM (
                SELECT
                    schemaname, tablename, indexname,
                    pg_relation_size(indexrelid) as real_size,
                    pg_relation_size(indexrelid) -
                    (pg_stat_get_live_tuples(indrelid) *
                     (SELECT avg_width FROM pg_stats WHERE tablename = t.tablename LIMIT 1)) as extra_size,
                    indexrelid, indrelid
                FROM pg_stat_user_indexes
                JOIN pg_stat_user_tables t USING (schemaname, tablename)
                WHERE schemaname = 'public'
            ) AS index_bloat
            WHERE extra_size > 0
            AND real_size > 10485760  -- Only indexes larger than 10MB
            ORDER BY extra_size DESC
        """)

        try:
            result = session.execute(query)
            return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error(f"Failed to analyze index bloat: {e}")
            return []

    @classmethod
    def rebuild_index(cls, session: Session, index_name: str) -> bool:
        """Rebuild an index (REINDEX) to reduce bloat."""
        try:
            session.execute(text(f"REINDEX INDEX {index_name}"))
            session.commit()
            logger.info(f"Successfully rebuilt index: {index_name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to rebuild index {index_name}: {e}")
            return False


class QueryOptimizationHints:
    """Provides query optimization hints and best practices."""

    # Common query patterns and their optimizations
    OPTIMIZATION_PATTERNS = {
        "job_dashboard": {
            "description": "Dashboard job listing with counts",
            "original": """
                SELECT j.*,
                       COUNT(t.id) as task_count,
                       COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) as completed_tasks
                FROM jobs j
                LEFT JOIN tasks t ON j.id = t.job_id
                WHERE j.status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')
                GROUP BY j.id
            """,
            "optimized": """
                SELECT j.*,
                       COALESCE(tc.task_count, 0) as task_count,
                       COALESCE(tc.completed_count, 0) as completed_tasks
                FROM jobs j
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) as task_count,
                        COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed_count
                    FROM tasks
                    WHERE job_id = j.id
                ) tc ON true
                WHERE j.status IN ('PLANNED', 'RELEASED', 'IN_PROGRESS')
            """,
            "hints": [
                "Use LATERAL JOIN for correlated subqueries",
                "Use COUNT(*) FILTER for conditional counting",
                "Ensure index on (status, due_date) for jobs table",
            ],
        },
        "machine_utilization": {
            "description": "Machine utilization calculation",
            "original": """
                SELECT m.*,
                       COUNT(t.id) as assigned_tasks,
                       SUM(t.planned_duration_minutes) as total_minutes
                FROM machines m
                LEFT JOIN tasks t ON m.id = t.assigned_machine_id
                WHERE t.planned_start_time >= NOW()
                GROUP BY m.id
            """,
            "optimized": """
                WITH future_tasks AS (
                    SELECT
                        assigned_machine_id,
                        COUNT(*) as task_count,
                        SUM(planned_duration_minutes) as total_minutes
                    FROM tasks
                    WHERE planned_start_time >= NOW()
                    AND assigned_machine_id IS NOT NULL
                    GROUP BY assigned_machine_id
                )
                SELECT m.*,
                       COALESCE(ft.task_count, 0) as assigned_tasks,
                       COALESCE(ft.total_minutes, 0) as total_minutes
                FROM machines m
                LEFT JOIN future_tasks ft ON m.id = ft.assigned_machine_id
            """,
            "hints": [
                "Use CTE to pre-aggregate data",
                "Filter early in the CTE",
                "Ensure index on (assigned_machine_id, planned_start_time)",
            ],
        },
        "skill_matching": {
            "description": "Find operators with required skills",
            "original": """
                SELECT DISTINCT o.*
                FROM operators o
                JOIN operator_skills os ON o.id = os.operator_id
                JOIN machine_skill_requirements msr ON os.skill_type_id = msr.skill_type_id
                WHERE msr.machine_id = :machine_id
                AND os.level >= msr.minimum_level
            """,
            "optimized": """
                SELECT o.*
                FROM operators o
                WHERE EXISTS (
                    SELECT 1
                    FROM machine_skill_requirements msr
                    JOIN operator_skills os ON (
                        os.skill_type_id = msr.skill_type_id
                        AND os.operator_id = o.id
                        AND os.level >= msr.minimum_level
                    )
                    WHERE msr.machine_id = :machine_id
                    AND msr.is_required = true
                )
            """,
            "hints": [
                "Use EXISTS instead of DISTINCT with JOIN",
                "Ensure composite index on (operator_id, skill_type_id, level)",
                "Filter on is_required early",
            ],
        },
    }

    @classmethod
    def get_optimization_hints(cls, query_pattern: str) -> dict[str, Any]:
        """Get optimization hints for a specific query pattern."""
        return cls.OPTIMIZATION_PATTERNS.get(query_pattern, {})

    @classmethod
    def analyze_query_plan(cls, session: Session, query: str) -> dict[str, Any]:
        """Analyze query execution plan and provide recommendations."""
        try:
            # Get execution plan
            explain_result = session.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
            )
            plan = explain_result.scalar()

            # Extract key metrics
            total_cost = plan[0]["Plan"]["Total Cost"]
            execution_time = plan[0]["Execution Time"]

            # Analyze for common issues
            recommendations = []

            # Check for sequential scans on large tables
            if "Seq Scan" in str(plan):
                recommendations.append(
                    "Consider adding indexes to avoid sequential scans"
                )

            # Check for nested loops with high iterations
            if "Nested Loop" in str(plan) and total_cost > 1000:
                recommendations.append(
                    "High cost nested loop detected - consider using hash joins"
                )

            # Check for sorting operations
            if "Sort" in str(plan):
                recommendations.append(
                    "Sorting detected - ensure indexes support ORDER BY clauses"
                )

            return {
                "total_cost": total_cost,
                "execution_time": execution_time,
                "recommendations": recommendations,
                "plan": plan,
            }

        except Exception as e:
            logger.error(f"Failed to analyze query plan: {e}")
            return {"error": str(e)}


# Export components
__all__ = [
    "IndexManager",
    "QueryOptimizationHints",
]
