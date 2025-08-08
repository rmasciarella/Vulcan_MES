#!/usr/bin/env bash
# Comprehensive Test Execution Script for Vulcan Engine
# This script orchestrates the complete test suite including unit, integration, performance, and security tests

set -e

# Color output functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${PURPLE}[STEP]${NC} $1"; }
log_result() { echo -e "${CYAN}[RESULT]${NC} $1"; }

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"
REPORTS_DIR="$BACKEND_DIR/test_reports"
TEST_ENV_FILE="$BACKEND_DIR/.env.test"

# Test execution options
RUN_UNIT_TESTS=${RUN_UNIT_TESTS:-true}
RUN_INTEGRATION_TESTS=${RUN_INTEGRATION_TESTS:-true}
RUN_PERFORMANCE_TESTS=${RUN_PERFORMANCE_TESTS:-true}
RUN_SECURITY_TESTS=${RUN_SECURITY_TESTS:-true}
RUN_E2E_TESTS=${RUN_E2E_TESTS:-false}
GENERATE_COVERAGE=${GENERATE_COVERAGE:-true}
CLEANUP_AFTER=${CLEANUP_AFTER:-true}
PARALLEL_EXECUTION=${PARALLEL_EXECUTION:-false}
DETAILED_OUTPUT=${DETAILED_OUTPUT:-true}

# Performance thresholds
MAX_TEST_DURATION=1800  # 30 minutes
MIN_COVERAGE_THRESHOLD=85
MAX_MEMORY_USAGE_MB=2048

show_usage() {
    cat << EOF
Comprehensive Test Runner for Vulcan Engine

USAGE:
    $0 [command] [options]

COMMANDS:
    all         Run complete test suite (default)
    unit        Run only unit tests
    integration Run only integration tests
    performance Run only performance tests
    security    Run only security tests
    e2e         Run only end-to-end tests
    coverage    Generate coverage report only
    clean       Clean test artifacts and containers
    status      Show test environment status
    help        Show this help message

OPTIONS:
    --no-coverage          Skip coverage generation
    --no-cleanup          Don't cleanup containers after tests
    --parallel            Run tests in parallel where possible
    --quiet               Minimal output
    --reports-only        Generate reports without running tests
    --docker-only         Use only Docker containers (no local)
    --timeout=SECONDS     Maximum test execution time (default: 1800)

ENVIRONMENT VARIABLES:
    RUN_UNIT_TESTS=true|false        (default: true)
    RUN_INTEGRATION_TESTS=true|false (default: true)
    RUN_PERFORMANCE_TESTS=true|false (default: true)
    RUN_SECURITY_TESTS=true|false    (default: true)
    RUN_E2E_TESTS=true|false         (default: false)
    GENERATE_COVERAGE=true|false     (default: true)
    CLEANUP_AFTER=true|false         (default: true)
    PARALLEL_EXECUTION=true|false    (default: false)

EXAMPLES:
    # Run complete test suite
    $0 all

    # Run only unit and integration tests
    $0 unit integration

    # Run performance tests with detailed output
    $0 performance --detailed

    # Run tests in Docker containers only
    $0 all --docker-only

    # Generate coverage report only
    $0 coverage --reports-only

EOF
}

setup_environment() {
    log_step "Setting up test environment"

    # Create reports directory
    mkdir -p "$REPORTS_DIR"/{unit,integration,performance,security,e2e,coverage}

    # Create test environment file if not exists
    if [[ ! -f "$TEST_ENV_FILE" ]]; then
        log_info "Creating test environment file: $TEST_ENV_FILE"
        cat > "$TEST_ENV_FILE" << 'EOF'
# Test Environment Configuration
TESTING=true
DATABASE_URL=postgresql://test_user:test_password@localhost:5433/test_scheduling_db
REDIS_URL=redis://localhost:6380/0
SECRET_KEY=test-secret-key-for-testing-only-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30
FIRST_SUPERUSER=test.admin@example.com
FIRST_SUPERUSER_PASSWORD=testadminpassword
EMAIL_TEST_USER=test.user@example.com
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
LOG_LEVEL=INFO
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/app
EOF
    fi

    # Export test environment
    set -a
    source "$TEST_ENV_FILE"
    set +a

    log_success "Test environment configured"
}

check_dependencies() {
    log_step "Checking dependencies"

    local missing_deps=()

    # Check Python and pytest
    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    if ! python3 -c "import pytest" 2>/dev/null; then
        missing_deps+=("pytest (pip install pytest)")
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_deps+=("docker")
    fi

    if ! command -v docker-compose &> /dev/null; then
        missing_deps+=("docker-compose")
    fi

    # Check PostgreSQL client (for direct DB tests)
    if ! command -v psql &> /dev/null; then
        log_warning "psql not found - some tests may be skipped"
    fi

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        return 1
    fi

    log_success "All dependencies available"
}

start_test_containers() {
    log_step "Starting test containers"

    cd "$PROJECT_ROOT"

    # Check if containers are already running
    if docker-compose -f docker-compose.test.yml ps | grep -q "Up"; then
        log_info "Test containers already running"
        return 0
    fi

    # Start test infrastructure
    log_info "Starting PostgreSQL and Redis containers..."
    docker-compose -f docker-compose.test.yml up -d db redis

    # Wait for services to be healthy
    log_info "Waiting for services to be ready..."
    local max_wait=60
    local wait_count=0

    while [[ $wait_count -lt $max_wait ]]; do
        if docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; then
            log_success "Test containers are ready"
            return 0
        fi
        sleep 2
        wait_count=$((wait_count + 2))
        echo -n "."
    done

    log_error "Test containers failed to start within ${max_wait}s"
    docker-compose -f docker-compose.test.yml logs
    return 1
}

run_unit_tests() {
    log_step "Running unit tests"

    local pytest_args=(
        "app/tests/"
        "-m" "unit"
        "-v"
        "--tb=short"
        "--maxfail=10"
        "--durations=10"
        "--junitxml=$REPORTS_DIR/unit/junit.xml"
    )

    if [[ "$GENERATE_COVERAGE" == "true" ]]; then
        pytest_args+=(
            "--cov=app"
            "--cov-report=html:$REPORTS_DIR/unit/coverage_html"
            "--cov-report=xml:$REPORTS_DIR/unit/coverage.xml"
            "--cov-report=term-missing"
        )
    fi

    if [[ "$PARALLEL_EXECUTION" == "true" ]]; then
        pytest_args+=("-n" "auto")
    fi

    cd "$BACKEND_DIR"
    if python -m pytest "${pytest_args[@]}"; then
        log_success "Unit tests passed"
        return 0
    else
        log_error "Unit tests failed"
        return 1
    fi
}

run_integration_tests() {
    log_step "Running integration tests"

    # Ensure test containers are running
    start_test_containers || return 1

    local pytest_args=(
        "app/tests/"
        "-m" "integration"
        "-v"
        "--tb=short"
        "--maxfail=5"
        "--durations=10"
        "--junitxml=$REPORTS_DIR/integration/junit.xml"
    )

    if [[ "$GENERATE_COVERAGE" == "true" ]]; then
        pytest_args+=(
            "--cov=app"
            "--cov-report=html:$REPORTS_DIR/integration/coverage_html"
            "--cov-report=xml:$REPORTS_DIR/integration/coverage.xml"
        )
    fi

    cd "$BACKEND_DIR"
    if python -m pytest "${pytest_args[@]}"; then
        log_success "Integration tests passed"
        return 0
    else
        log_error "Integration tests failed"
        return 1
    fi
}

run_performance_tests() {
    log_step "Running performance tests"

    start_test_containers || return 1

    local pytest_args=(
        "app/tests/"
        "-m" "performance"
        "-v"
        "--tb=short"
        "--maxfail=3"
        "--durations=10"
        "--junitxml=$REPORTS_DIR/performance/junit.xml"
        "--timeout=300"
    )

    cd "$BACKEND_DIR"
    if python -m pytest "${pytest_args[@]}"; then
        log_success "Performance tests passed"
        return 0
    else
        log_error "Performance tests failed"
        return 1
    fi
}

run_security_tests() {
    log_step "Running security tests"

    start_test_containers || return 1

    local pytest_args=(
        "app/tests/"
        "-m" "security"
        "-v"
        "--tb=short"
        "--maxfail=3"
        "--durations=10"
        "--junitxml=$REPORTS_DIR/security/junit.xml"
    )

    cd "$BACKEND_DIR"
    if python -m pytest "${pytest_args[@]}"; then
        log_success "Security tests passed"
        return 0
    else
        log_error "Security tests failed"
        return 1
    fi
}

run_e2e_tests() {
    log_step "Running end-to-end tests"

    start_test_containers || return 1

    local pytest_args=(
        "app/tests/e2e"
        "-c" "pytest-e2e.ini"
        "-v"
        "--tb=short"
        "--maxfail=2"
        "--durations=10"
        "--junitxml=$REPORTS_DIR/e2e/junit.xml"
        "--timeout=600"
    )

    cd "$BACKEND_DIR"
    if python -m pytest "${pytest_args[@]}"; then
        log_success "End-to-end tests passed"
        return 0
    else
        log_error "End-to-end tests failed"
        return 1
    fi
}

generate_coverage_report() {
    log_step "Generating comprehensive coverage report"

    cd "$BACKEND_DIR"

    # Combine coverage from all test runs
    if command -v coverage &> /dev/null; then
        coverage combine .coverage*
        coverage html -d "$REPORTS_DIR/coverage/combined_html"
        coverage xml -o "$REPORTS_DIR/coverage/combined.xml"
        coverage report --fail-under=$MIN_COVERAGE_THRESHOLD

        local coverage_pct=$(coverage report | tail -1 | awk '{print $4}' | sed 's/%//')
        log_result "Total coverage: ${coverage_pct}%"

        if (( $(echo "$coverage_pct < $MIN_COVERAGE_THRESHOLD" | bc -l) )); then
            log_warning "Coverage below threshold: ${coverage_pct}% < ${MIN_COVERAGE_THRESHOLD}%"
            return 1
        fi
    else
        log_warning "Coverage tool not available, skipping coverage report"
    fi

    log_success "Coverage report generated"
}

cleanup_test_environment() {
    if [[ "$CLEANUP_AFTER" == "true" ]]; then
        log_step "Cleaning up test environment"

        cd "$PROJECT_ROOT"

        # Stop and remove test containers
        docker-compose -f docker-compose.test.yml down --volumes --remove-orphans || true

        # Clean up temporary files
        cd "$BACKEND_DIR"
        find . -name "*.pyc" -delete 2>/dev/null || true
        find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
        find . -name ".coverage*" -delete 2>/dev/null || true
        rm -f .pytest_cache 2>/dev/null || true

        log_success "Test environment cleaned up"
    fi
}

show_test_status() {
    log_step "Test Environment Status"

    echo ""
    echo "=== Configuration ==="
    echo "Reports Directory: $REPORTS_DIR"
    echo "Backend Directory: $BACKEND_DIR"
    echo "Unit Tests: $RUN_UNIT_TESTS"
    echo "Integration Tests: $RUN_INTEGRATION_TESTS"
    echo "Performance Tests: $RUN_PERFORMANCE_TESTS"
    echo "Security Tests: $RUN_SECURITY_TESTS"
    echo "E2E Tests: $RUN_E2E_TESTS"
    echo "Generate Coverage: $GENERATE_COVERAGE"
    echo "Parallel Execution: $PARALLEL_EXECUTION"
    echo ""

    echo "=== Docker Containers ==="
    cd "$PROJECT_ROOT"
    if docker-compose -f docker-compose.test.yml ps 2>/dev/null; then
        echo ""
    else
        echo "No test containers running"
        echo ""
    fi

    echo "=== Test Reports ==="
    if [[ -d "$REPORTS_DIR" ]]; then
        find "$REPORTS_DIR" -name "*.xml" -o -name "*.html" | head -10
    else
        echo "No reports directory found"
    fi
    echo ""
}

generate_test_summary() {
    log_step "Generating test execution summary"

    local summary_file="$REPORTS_DIR/test_summary.md"
    local execution_time=$((SECONDS))

    cat > "$summary_file" << EOF
# Test Execution Summary

**Date**: $(date)
**Duration**: ${execution_time}s
**Environment**: Test

## Test Results

| Test Suite | Status | Duration | Coverage |
|------------|--------|----------|----------|
| Unit Tests | $([[ "$RUN_UNIT_TESTS" == "true" ]] && echo "✅ Passed" || echo "⏭️ Skipped") | - | - |
| Integration Tests | $([[ "$RUN_INTEGRATION_TESTS" == "true" ]] && echo "✅ Passed" || echo "⏭️ Skipped") | - | - |
| Performance Tests | $([[ "$RUN_PERFORMANCE_TESTS" == "true" ]] && echo "✅ Passed" || echo "⏭️ Skipped") | - | - |
| Security Tests | $([[ "$RUN_SECURITY_TESTS" == "true" ]] && echo "✅ Passed" || echo "⏭️ Skipped") | - | - |
| E2E Tests | $([[ "$RUN_E2E_TESTS" == "true" ]] && echo "✅ Passed" || echo "⏭️ Skipped") | - | - |

## Reports Generated

- JUnit XML reports in \`test_reports/*/junit.xml\`
- Coverage reports in \`test_reports/coverage/\`
- HTML reports in \`test_reports/*/coverage_html/\`

## System Information

- Python Version: $(python3 --version)
- Pytest Version: $(python3 -c "import pytest; print(pytest.__version__)" 2>/dev/null || echo "Unknown")
- Docker Version: $(docker --version 2>/dev/null || echo "Unknown")

EOF

    log_success "Test summary generated: $summary_file"
}

main() {
    local command=${1:-"all"}
    local exit_code=0

    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-coverage)
                GENERATE_COVERAGE=false
                shift
                ;;
            --no-cleanup)
                CLEANUP_AFTER=false
                shift
                ;;
            --parallel)
                PARALLEL_EXECUTION=true
                shift
                ;;
            --quiet)
                DETAILED_OUTPUT=false
                shift
                ;;
            --reports-only)
                RUN_UNIT_TESTS=false
                RUN_INTEGRATION_TESTS=false
                RUN_PERFORMANCE_TESTS=false
                RUN_SECURITY_TESTS=false
                RUN_E2E_TESTS=false
                GENERATE_COVERAGE=true
                shift
                ;;
            --docker-only)
                # All tests will use Docker containers
                shift
                ;;
            --timeout=*)
                MAX_TEST_DURATION="${1#*=}"
                shift
                ;;
            --help|-h|help)
                show_usage
                exit 0
                ;;
            all|unit|integration|performance|security|e2e|coverage|clean|status)
                command=$1
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Set timeout for entire script
    timeout $MAX_TEST_DURATION bash -c '
        trap "echo \"Test execution timed out after $MAX_TEST_DURATION seconds\"" SIGTERM

        case "$1" in
            "clean")
                cleanup_test_environment
                ;;
            "status")
                show_test_status
                ;;
            "coverage")
                setup_environment
                generate_coverage_report
                ;;
            "unit")
                setup_environment
                check_dependencies
                run_unit_tests || exit_code=1
                ;;
            "integration")
                setup_environment
                check_dependencies
                run_integration_tests || exit_code=1
                ;;
            "performance")
                setup_environment
                check_dependencies
                run_performance_tests || exit_code=1
                ;;
            "security")
                setup_environment
                check_dependencies
                run_security_tests || exit_code=1
                ;;
            "e2e")
                setup_environment
                check_dependencies
                run_e2e_tests || exit_code=1
                ;;
            "all"|*)
                setup_environment
                check_dependencies

                if [[ "$RUN_UNIT_TESTS" == "true" ]]; then
                    run_unit_tests || exit_code=1
                fi

                if [[ "$RUN_INTEGRATION_TESTS" == "true" ]]; then
                    run_integration_tests || exit_code=1
                fi

                if [[ "$RUN_PERFORMANCE_TESTS" == "true" ]]; then
                    run_performance_tests || exit_code=1
                fi

                if [[ "$RUN_SECURITY_TESTS" == "true" ]]; then
                    run_security_tests || exit_code=1
                fi

                if [[ "$RUN_E2E_TESTS" == "true" ]]; then
                    run_e2e_tests || exit_code=1
                fi

                if [[ "$GENERATE_COVERAGE" == "true" ]]; then
                    generate_coverage_report || exit_code=1
                fi

                generate_test_summary
                ;;
        esac

        cleanup_test_environment

        if [[ $exit_code -eq 0 ]]; then
            log_success "All tests completed successfully!"
        else
            log_error "Some tests failed. Check reports in $REPORTS_DIR"
        fi

        exit $exit_code
    ' -- "$command" || exit_code=$?

    exit $exit_code
}

# Make script executable from any directory
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
