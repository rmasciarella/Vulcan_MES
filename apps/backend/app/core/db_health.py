#!/usr/bin/env python3
"""
Database health check and connectivity verification script.
Provides comprehensive health monitoring for the database system.
"""

import logging
import sys
import time
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, create_engine, inspect, text
from sqlmodel import Session

from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseHealthChecker:
    """Comprehensive database health checker."""

    def __init__(self, engine: Engine | None = None):
        self.engine = engine or create_engine(
            str(settings.SQLALCHEMY_DATABASE_URI),
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.health_results = {}

    def check_connectivity(self) -> dict[str, Any]:
        """Check basic database connectivity."""
        logger.info("Checking database connectivity...")

        result = {
            "test_name": "connectivity",
            "status": "unknown",
            "message": "",
            "details": {},
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            with Session(self.engine) as session:
                # Simple connectivity test
                session.exec(text("SELECT 1 as test_connection"))

                result.update(
                    {
                        "status": "healthy",
                        "message": "Database connection successful",
                        "execution_time_ms": round(
                            (time.time() - start_time) * 1000, 2
                        ),
                    }
                )

        except Exception as e:
            result.update(
                {
                    "status": "unhealthy",
                    "message": f"Database connection failed: {str(e)}",
                    "details": {"error": str(e), "error_type": type(e).__name__},
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                }
            )

        return result

    def check_schema_integrity(self) -> dict[str, Any]:
        """Check database schema integrity."""
        logger.info("Checking schema integrity...")

        result = {
            "test_name": "schema_integrity",
            "status": "unknown",
            "message": "",
            "details": {},
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()

            # Define expected essential tables
            essential_tables = [
                "users",
                "jobs",
                "tasks",
                "operators",
                "machines",
                "operations",
                "production_zones",
                "skills",
            ]

            missing_tables = [
                table for table in essential_tables if table not in tables
            ]

            if missing_tables:
                result.update(
                    {
                        "status": "unhealthy",
                        "message": f"Missing essential tables: {missing_tables}",
                        "details": {
                            "total_tables": len(tables),
                            "missing_tables": missing_tables,
                            "existing_tables": tables,
                        },
                    }
                )
            else:
                result.update(
                    {
                        "status": "healthy",
                        "message": f"Schema integrity verified ({len(tables)} tables found)",
                        "details": {
                            "total_tables": len(tables),
                            "essential_tables_present": len(essential_tables),
                            "all_tables": tables,
                        },
                    }
                )

            result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result.update(
                {
                    "status": "unhealthy",
                    "message": f"Schema integrity check failed: {str(e)}",
                    "details": {"error": str(e), "error_type": type(e).__name__},
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                }
            )

        return result

    def check_data_consistency(self) -> dict[str, Any]:
        """Check basic data consistency."""
        logger.info("Checking data consistency...")

        result = {
            "test_name": "data_consistency",
            "status": "unknown",
            "message": "",
            "details": {},
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            with Session(self.engine) as session:
                consistency_checks = []

                # Check 1: Verify no orphaned tasks (tasks without valid jobs)
                orphaned_tasks = session.exec(
                    text("""
                    SELECT COUNT(*) as count
                    FROM tasks t
                    LEFT JOIN jobs j ON t.job_id = j.id
                    WHERE j.id IS NULL
                """)
                ).fetchone()

                consistency_checks.append(
                    {
                        "check": "orphaned_tasks",
                        "count": orphaned_tasks[0],
                        "status": "pass" if orphaned_tasks[0] == 0 else "fail",
                    }
                )

                # Check 2: Verify no invalid operator assignments
                invalid_assignments = session.exec(
                    text("""
                    SELECT COUNT(*) as count
                    FROM task_operator_assignments toa
                    LEFT JOIN operators o ON toa.operator_id = o.id
                    LEFT JOIN tasks t ON toa.task_id = t.id
                    WHERE o.id IS NULL OR t.id IS NULL
                """)
                ).fetchone()

                consistency_checks.append(
                    {
                        "check": "invalid_operator_assignments",
                        "count": invalid_assignments[0],
                        "status": "pass" if invalid_assignments[0] == 0 else "fail",
                    }
                )

                # Check 3: Verify production zones have valid WIP counts
                invalid_wip = session.exec(
                    text("""
                    SELECT COUNT(*) as count
                    FROM production_zones
                    WHERE current_wip < 0 OR current_wip > wip_limit
                """)
                ).fetchone()

                consistency_checks.append(
                    {
                        "check": "invalid_wip_counts",
                        "count": invalid_wip[0],
                        "status": "pass" if invalid_wip[0] == 0 else "fail",
                    }
                )

                # Determine overall status
                failed_checks = [
                    check for check in consistency_checks if check["status"] == "fail"
                ]

                if failed_checks:
                    result.update(
                        {
                            "status": "unhealthy",
                            "message": f"Data consistency issues found: {len(failed_checks)} checks failed",
                            "details": {
                                "total_checks": len(consistency_checks),
                                "failed_checks": len(failed_checks),
                                "checks": consistency_checks,
                            },
                        }
                    )
                else:
                    result.update(
                        {
                            "status": "healthy",
                            "message": f"Data consistency verified ({len(consistency_checks)} checks passed)",
                            "details": {
                                "total_checks": len(consistency_checks),
                                "failed_checks": 0,
                                "checks": consistency_checks,
                            },
                        }
                    )

            result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result.update(
                {
                    "status": "unhealthy",
                    "message": f"Data consistency check failed: {str(e)}",
                    "details": {"error": str(e), "error_type": type(e).__name__},
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                }
            )

        return result

    def check_performance(self) -> dict[str, Any]:
        """Check database performance metrics."""
        logger.info("Checking database performance...")

        result = {
            "test_name": "performance",
            "status": "unknown",
            "message": "",
            "details": {},
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            with Session(self.engine) as session:
                performance_metrics = {}

                # Test 1: Simple query performance
                query_start = time.time()
                user_count = session.exec(text("SELECT COUNT(*) FROM users")).fetchone()
                query_time = (time.time() - query_start) * 1000

                performance_metrics["simple_query_ms"] = round(query_time, 2)
                performance_metrics["user_count"] = user_count[0]

                # Test 2: Complex query performance (if we have data)
                if user_count[0] > 0:
                    complex_start = time.time()
                    complex_result = session.exec(
                        text("""
                        SELECT COUNT(*)
                        FROM tasks t
                        JOIN jobs j ON t.job_id = j.id
                        JOIN operations o ON t.operation_id = o.id
                        WHERE t.status IN ('ready', 'scheduled', 'in_progress')
                    """)
                    ).fetchone()
                    complex_time = (time.time() - complex_start) * 1000

                    performance_metrics["complex_query_ms"] = round(complex_time, 2)
                    performance_metrics["active_tasks"] = complex_result[0]

                # Test 3: Connection pool status (if available)
                try:
                    self.engine.pool.status()
                    performance_metrics["pool_size"] = self.engine.pool.size()
                    performance_metrics["pool_checked_in"] = (
                        self.engine.pool.checkedin()
                    )
                    performance_metrics["pool_checked_out"] = (
                        self.engine.pool.checkedout()
                    )
                except AttributeError:
                    # Pool status not available for all pool types
                    pass

                # Evaluate performance
                warnings = []
                if performance_metrics.get("simple_query_ms", 0) > 100:
                    warnings.append(
                        f"Slow simple query: {performance_metrics['simple_query_ms']}ms"
                    )

                if performance_metrics.get("complex_query_ms", 0) > 500:
                    warnings.append(
                        f"Slow complex query: {performance_metrics['complex_query_ms']}ms"
                    )

                if warnings:
                    result.update(
                        {
                            "status": "warning",
                            "message": f'Performance issues detected: {"; ".join(warnings)}',
                            "details": performance_metrics,
                        }
                    )
                else:
                    result.update(
                        {
                            "status": "healthy",
                            "message": "Database performance is acceptable",
                            "details": performance_metrics,
                        }
                    )

            result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result.update(
                {
                    "status": "unhealthy",
                    "message": f"Performance check failed: {str(e)}",
                    "details": {"error": str(e), "error_type": type(e).__name__},
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                }
            )

        return result

    def check_migrations_status(self) -> dict[str, Any]:
        """Check Alembic migrations status."""
        logger.info("Checking migrations status...")

        result = {
            "test_name": "migrations_status",
            "status": "unknown",
            "message": "",
            "details": {},
            "execution_time_ms": 0,
        }

        start_time = time.time()

        try:
            with Session(self.engine) as session:
                # Check if alembic_version table exists
                inspector = inspect(self.engine)
                tables = inspector.get_table_names()

                if "alembic_version" not in tables:
                    result.update(
                        {
                            "status": "warning",
                            "message": "Alembic version table not found - database may not be managed by Alembic",
                            "details": {"alembic_table_exists": False},
                        }
                    )
                else:
                    # Get current revision
                    current_rev = session.exec(
                        text("SELECT version_num FROM alembic_version")
                    ).fetchone()

                    if current_rev:
                        result.update(
                            {
                                "status": "healthy",
                                "message": f"Database is managed by Alembic at revision: {current_rev[0]}",
                                "details": {
                                    "alembic_table_exists": True,
                                    "current_revision": current_rev[0],
                                },
                            }
                        )
                    else:
                        result.update(
                            {
                                "status": "warning",
                                "message": "Alembic version table exists but no revision found",
                                "details": {
                                    "alembic_table_exists": True,
                                    "current_revision": None,
                                },
                            }
                        )

            result["execution_time_ms"] = round((time.time() - start_time) * 1000, 2)

        except Exception as e:
            result.update(
                {
                    "status": "unhealthy",
                    "message": f"Migrations status check failed: {str(e)}",
                    "details": {"error": str(e), "error_type": type(e).__name__},
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                }
            )

        return result

    def comprehensive_health_check(self) -> dict[str, Any]:
        """Run all health checks and return comprehensive results."""
        logger.info("Starting comprehensive database health check...")

        start_time = time.time()

        # Run all health checks
        checks = [
            self.check_connectivity(),
            self.check_schema_integrity(),
            self.check_data_consistency(),
            self.check_performance(),
            self.check_migrations_status(),
        ]

        # Calculate overall health
        healthy_checks = [check for check in checks if check["status"] == "healthy"]
        warning_checks = [check for check in checks if check["status"] == "warning"]
        unhealthy_checks = [check for check in checks if check["status"] == "unhealthy"]

        # Determine overall status
        if unhealthy_checks:
            overall_status = "unhealthy"
            overall_message = f"{len(unhealthy_checks)} critical issues found"
        elif warning_checks:
            overall_status = "warning"
            overall_message = f"{len(warning_checks)} warnings found"
        else:
            overall_status = "healthy"
            overall_message = "All health checks passed"

        total_time = round((time.time() - start_time) * 1000, 2)

        comprehensive_result = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "overall_message": overall_message,
            "overall_health": overall_status == "healthy",
            "total_execution_time_ms": total_time,
            "summary": {
                "total_checks": len(checks),
                "healthy": len(healthy_checks),
                "warnings": len(warning_checks),
                "unhealthy": len(unhealthy_checks),
            },
            "checks": checks,
            "environment": settings.ENVIRONMENT,
            "database_url": str(settings.SQLALCHEMY_DATABASE_URI).split("@")[0]
            + "@***",  # Hide sensitive info
        }

        logger.info(f"Health check completed: {overall_status} ({total_time}ms)")

        return comprehensive_result

    def print_health_report(self, results: dict[str, Any] | None = None) -> None:
        """Print a formatted health report."""
        if results is None:
            results = self.comprehensive_health_check()

        print("\n" + "=" * 80)
        print("DATABASE HEALTH CHECK REPORT")
        print("=" * 80)
        print(f"Timestamp: {results['timestamp']}")
        print(f"Environment: {results['environment']}")
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"Overall Message: {results['overall_message']}")
        print(f"Total Execution Time: {results['total_execution_time_ms']}ms")

        print("\nSUMMARY:")
        print(f"  Total Checks: {results['summary']['total_checks']}")
        print(f"  Healthy: {results['summary']['healthy']}")
        print(f"  Warnings: {results['summary']['warnings']}")
        print(f"  Unhealthy: {results['summary']['unhealthy']}")

        print("\nDETAILED RESULTS:")
        print("-" * 80)

        for check in results["checks"]:
            status_symbol = {
                "healthy": "✓",
                "warning": "⚠",
                "unhealthy": "✗",
                "unknown": "?",
            }.get(check["status"], "?")

            print(f"{status_symbol} {check['test_name'].upper()}")
            print(f"  Status: {check['status']}")
            print(f"  Message: {check['message']}")
            print(f"  Execution Time: {check['execution_time_ms']}ms")

            if check["details"] and check["status"] != "healthy":
                print("  Details:")
                for key, value in check["details"].items():
                    if key != "error":
                        print(f"    {key}: {value}")

            print()

        print("=" * 80)


def main():
    """Main function for standalone health check execution."""
    import argparse

    parser = argparse.ArgumentParser(description="Database Health Check")
    parser.add_argument(
        "--json", action="store_true", help="Output results in JSON format"
    )
    parser.add_argument(
        "--check",
        choices=["connectivity", "schema", "data", "performance", "migrations"],
        help="Run specific check only",
    )
    parser.add_argument(
        "--exit-code", action="store_true", help="Exit with non-zero code if unhealthy"
    )

    args = parser.parse_args()

    try:
        checker = DatabaseHealthChecker()

        if args.check:
            # Run specific check
            check_methods = {
                "connectivity": checker.check_connectivity,
                "schema": checker.check_schema_integrity,
                "data": checker.check_data_consistency,
                "performance": checker.check_performance,
                "migrations": checker.check_migrations_status,
            }

            result = check_methods[args.check]()

            if args.json:
                import json

                print(json.dumps(result, indent=2))
            else:
                print(f"Check: {result['test_name']}")
                print(f"Status: {result['status']}")
                print(f"Message: {result['message']}")
                print(f"Time: {result['execution_time_ms']}ms")

            exit_code = 0 if result["status"] in ["healthy", "warning"] else 1

        else:
            # Run comprehensive check
            results = checker.comprehensive_health_check()

            if args.json:
                import json

                print(json.dumps(results, indent=2))
            else:
                checker.print_health_report(results)

            exit_code = 0 if results["overall_health"] else 1

        if args.exit_code:
            sys.exit(exit_code)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Health check failed with exception: {e}")
        if args.json:
            import json

            error_result = {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }
            print(json.dumps(error_result, indent=2))
        else:
            print(f"Health check failed: {e}")

        sys.exit(1)


if __name__ == "__main__":
    main()
