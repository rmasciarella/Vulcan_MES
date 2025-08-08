#!/bin/bash

# Comprehensive Test Execution Script
# Runs all test suites with coverage reporting and summarizes results

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COVERAGE_THRESHOLD=85
PARALLEL_WORKERS=auto
OUTPUT_DIR="test-results"

# Function to print colored output
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check dependencies
check_dependencies() {
    print_header "Checking Dependencies"

    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install it first:"
        echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    print_success "uv is available"

    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found. Please run this script from the backend directory."
        exit 1
    fi
    print_success "In correct directory (backend)"

    # Check database connection (if needed)
    if [ -n "$DATABASE_URL" ]; then
        print_success "Database URL configured: $DATABASE_URL"
    else
        print_warning "DATABASE_URL not set. Some integration tests may be skipped."
    fi
}

# Function to set up test environment
setup_test_environment() {
    print_header "Setting up Test Environment"

    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"/*
    print_success "Created output directory: $OUTPUT_DIR"

    # Install dependencies
    echo "Installing dependencies..."
    uv sync --dev
    print_success "Dependencies installed"

    # Run database migrations if needed
    if [ -n "$DATABASE_URL" ]; then
        echo "Running database migrations..."
        uv run alembic upgrade head || print_warning "Migration failed - continuing anyway"
        print_success "Database migrations completed"
    fi
}

# Function to run code quality checks
run_code_quality() {
    print_header "Running Code Quality Checks"

    local failed=0

    # Type checking
    echo "Running mypy type checking..."
    if uv run mypy app --ignore-missing-imports > "$OUTPUT_DIR/mypy.log" 2>&1; then
        print_success "Type checking passed"
    else
        print_error "Type checking failed (see $OUTPUT_DIR/mypy.log)"
        failed=1
    fi

    # Linting
    echo "Running ruff linting..."
    if uv run ruff check app > "$OUTPUT_DIR/ruff.log" 2>&1; then
        print_success "Linting passed"
    else
        print_error "Linting failed (see $OUTPUT_DIR/ruff.log)"
        failed=1
    fi

    # Format checking
    echo "Checking code formatting..."
    if uv run ruff format --check app > "$OUTPUT_DIR/format.log" 2>&1; then
        print_success "Code formatting is correct"
    else
        print_warning "Code formatting issues found (see $OUTPUT_DIR/format.log)"
    fi

    # Security scanning
    echo "Running security scan..."
    if uv pip install bandit[toml] && uv run bandit -r app -f json -o "$OUTPUT_DIR/bandit-report.json" > "$OUTPUT_DIR/bandit.log" 2>&1; then
        print_success "Security scan completed"
    else
        print_warning "Security scan had issues (see $OUTPUT_DIR/bandit.log)"
    fi

    return $failed
}

# Function to run unit tests
run_unit_tests() {
    print_header "Running Unit Tests"

    local start_time=$(date +%s)

    if uv run pytest -m "unit and not slow" \
        --cov=app \
        --cov-report=xml:"$OUTPUT_DIR/coverage-unit.xml" \
        --cov-report=html:"$OUTPUT_DIR/htmlcov-unit" \
        --cov-report=term-missing \
        --junit-xml="$OUTPUT_DIR/junit-unit.xml" \
        --tb=short \
        -v \
        -n "$PARALLEL_WORKERS" \
        > "$OUTPUT_DIR/unit-tests.log" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_success "Unit tests passed in ${duration}s"
        return 0
    else
        print_error "Unit tests failed (see $OUTPUT_DIR/unit-tests.log)"
        return 1
    fi
}

# Function to run integration tests
run_integration_tests() {
    print_header "Running Integration Tests"

    local start_time=$(date +%s)

    if uv run pytest -m "integration and not slow" \
        --cov=app \
        --cov-append \
        --cov-report=xml:"$OUTPUT_DIR/coverage-integration.xml" \
        --cov-report=html:"$OUTPUT_DIR/htmlcov-integration" \
        --junit-xml="$OUTPUT_DIR/junit-integration.xml" \
        --tb=short \
        -v \
        > "$OUTPUT_DIR/integration-tests.log" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_success "Integration tests passed in ${duration}s"
        return 0
    else
        print_error "Integration tests failed (see $OUTPUT_DIR/integration-tests.log)"
        return 1
    fi
}

# Function to run E2E tests
run_e2e_tests() {
    print_header "Running End-to-End Tests"

    local start_time=$(date +%s)

    if uv run pytest -m "e2e" \
        --cov=app \
        --cov-append \
        --cov-report=xml:"$OUTPUT_DIR/coverage-e2e.xml" \
        --cov-report=html:"$OUTPUT_DIR/htmlcov-e2e" \
        --junit-xml="$OUTPUT_DIR/junit-e2e.xml" \
        --tb=short \
        -v \
        --timeout=600 \
        > "$OUTPUT_DIR/e2e-tests.log" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_success "E2E tests passed in ${duration}s"
        return 0
    else
        print_error "E2E tests failed (see $OUTPUT_DIR/e2e-tests.log)"
        return 1
    fi
}

# Function to run security tests
run_security_tests() {
    print_header "Running Security Tests"

    local start_time=$(date +%s)

    if uv run pytest -m "security" \
        --run-security \
        --junit-xml="$OUTPUT_DIR/junit-security.xml" \
        --tb=short \
        -v \
        > "$OUTPUT_DIR/security-tests.log" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_success "Security tests passed in ${duration}s"
        return 0
    else
        print_error "Security tests failed (see $OUTPUT_DIR/security-tests.log)"
        return 1
    fi
}

# Function to run performance tests
run_performance_tests() {
    print_header "Running Performance Tests"

    local start_time=$(date +%s)

    if uv run pytest -m "performance" \
        --run-performance \
        --junit-xml="$OUTPUT_DIR/junit-performance.xml" \
        --tb=short \
        -v \
        --timeout=1200 \
        > "$OUTPUT_DIR/performance-tests.log" 2>&1; then

        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        print_success "Performance tests passed in ${duration}s"
        return 0
    else
        print_warning "Performance tests had issues (see $OUTPUT_DIR/performance-tests.log)"
        return 1
    fi
}

# Function to generate coverage report
generate_coverage_report() {
    print_header "Generating Coverage Report"

    # Combine all coverage data
    if uv run coverage combine > "$OUTPUT_DIR/coverage-combine.log" 2>&1; then
        print_success "Coverage data combined"
    else
        print_warning "Coverage combination had issues"
    fi

    # Generate final coverage report
    if uv run coverage report --show-missing > "$OUTPUT_DIR/coverage-report.txt" 2>&1; then
        # Check coverage threshold
        local coverage_pct=$(uv run coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//')

        if [ "${coverage_pct%.*}" -ge "$COVERAGE_THRESHOLD" ]; then
            print_success "Coverage: ${coverage_pct}% (meets ${COVERAGE_THRESHOLD}% threshold)"
        else
            print_warning "Coverage: ${coverage_pct}% (below ${COVERAGE_THRESHOLD}% threshold)"
        fi

        # Generate HTML report
        uv run coverage html -d "$OUTPUT_DIR/htmlcov-combined" > /dev/null 2>&1
        print_success "Combined HTML coverage report generated"

    else
        print_error "Failed to generate coverage report"
    fi
}

# Function to generate test summary
generate_test_summary() {
    print_header "Test Execution Summary"

    local summary_file="$OUTPUT_DIR/test-summary.txt"
    local total_tests=0
    local total_failures=0
    local total_errors=0

    echo "Vulcan Engine - Test Execution Summary" > "$summary_file"
    echo "Generated: $(date)" >> "$summary_file"
    echo "========================================" >> "$summary_file"
    echo "" >> "$summary_file"

    # Parse JUnit XML files for statistics
    for junit_file in "$OUTPUT_DIR"/junit-*.xml; do
        if [ -f "$junit_file" ]; then
            local test_type=$(basename "$junit_file" .xml | sed 's/junit-//')
            echo "Parsing $junit_file for $test_type tests..."

            # Extract test statistics (basic parsing - could be enhanced)
            local tests=$(grep -o 'tests="[0-9]*"' "$junit_file" 2>/dev/null | head -1 | sed 's/tests="//;s/"//' || echo "0")
            local failures=$(grep -o 'failures="[0-9]*"' "$junit_file" 2>/dev/null | head -1 | sed 's/failures="//;s/"//' || echo "0")
            local errors=$(grep -o 'errors="[0-9]*"' "$junit_file" 2>/dev/null | head -1 | sed 's/errors="//;s/"//' || echo "0")

            echo "$test_type Tests: $tests tests, $failures failures, $errors errors" >> "$summary_file"

            total_tests=$((total_tests + tests))
            total_failures=$((total_failures + failures))
            total_errors=$((total_errors + errors))
        fi
    done

    echo "" >> "$summary_file"
    echo "Total: $total_tests tests, $total_failures failures, $total_errors errors" >> "$summary_file"

    # Add coverage information
    if [ -f "$OUTPUT_DIR/coverage-report.txt" ]; then
        echo "" >> "$summary_file"
        echo "Coverage Summary:" >> "$summary_file"
        tail -5 "$OUTPUT_DIR/coverage-report.txt" >> "$summary_file"
    fi

    # Display summary
    cat "$summary_file"

    # Return exit code based on results
    if [ "$total_failures" -eq 0 ] && [ "$total_errors" -eq 0 ]; then
        print_success "All tests passed!"
        return 0
    else
        print_error "Tests failed: $total_failures failures, $total_errors errors"
        return 1
    fi
}

# Function to clean up
cleanup() {
    print_header "Cleaning Up"

    # Keep test results but clean up temporary files
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

    print_success "Cleanup completed"
}

# Main execution function
main() {
    local start_time=$(date +%s)
    local failed_suites=0

    echo "Vulcan Engine - Comprehensive Test Suite"
    echo "========================================"
    echo "Starting test execution at $(date)"
    echo ""

    # Parse command line arguments
    local test_type="all"
    local skip_quality=false
    local skip_performance=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --type)
                test_type="$2"
                shift 2
                ;;
            --skip-quality)
                skip_quality=true
                shift
                ;;
            --skip-performance)
                skip_performance=true
                shift
                ;;
            --help)
                echo "Usage: $0 [--type TYPE] [--skip-quality] [--skip-performance]"
                echo "  --type TYPE: Run specific test type (all|unit|integration|e2e|security|performance)"
                echo "  --skip-quality: Skip code quality checks"
                echo "  --skip-performance: Skip performance tests"
                exit 0
                ;;
            *)
                print_error "Unknown argument: $1"
                exit 1
                ;;
        esac
    done

    # Set up environment
    check_dependencies
    setup_test_environment

    # Run code quality checks
    if [ "$skip_quality" = false ] && { [ "$test_type" = "all" ] || [ "$test_type" = "quality" ]; }; then
        if ! run_code_quality; then
            failed_suites=$((failed_suites + 1))
        fi
    fi

    # Run test suites based on type
    if [ "$test_type" = "all" ] || [ "$test_type" = "unit" ]; then
        if ! run_unit_tests; then
            failed_suites=$((failed_suites + 1))
        fi
    fi

    if [ "$test_type" = "all" ] || [ "$test_type" = "integration" ]; then
        if ! run_integration_tests; then
            failed_suites=$((failed_suites + 1))
        fi
    fi

    if [ "$test_type" = "all" ] || [ "$test_type" = "e2e" ]; then
        if ! run_e2e_tests; then
            failed_suites=$((failed_suites + 1))
        fi
    fi

    if [ "$test_type" = "all" ] || [ "$test_type" = "security" ]; then
        if ! run_security_tests; then
            failed_suites=$((failed_suites + 1))
        fi
    fi

    if [ "$skip_performance" = false ] && { [ "$test_type" = "all" ] || [ "$test_type" = "performance" ]; }; then
        if ! run_performance_tests; then
            # Performance test failures are warnings, not critical failures
            print_warning "Performance tests had issues but not counting as critical failure"
        fi
    fi

    # Generate reports
    generate_coverage_report
    local summary_result=0
    if ! generate_test_summary; then
        summary_result=1
    fi

    # Cleanup
    cleanup

    # Final summary
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))

    print_header "Final Results"
    echo "Total execution time: ${total_duration}s"
    echo "Test results available in: $OUTPUT_DIR/"
    echo ""

    if [ "$failed_suites" -eq 0 ] && [ "$summary_result" -eq 0 ]; then
        print_success "All test suites completed successfully!"
        echo ""
        echo "📊 View detailed results:"
        echo "  - Combined coverage: $OUTPUT_DIR/htmlcov-combined/index.html"
        echo "  - Test summary: $OUTPUT_DIR/test-summary.txt"
        echo "  - Individual logs: $OUTPUT_DIR/*.log"
        exit 0
    else
        print_error "Some test suites failed ($failed_suites failed suites)"
        echo ""
        echo "🔍 Check failed results:"
        echo "  - Test summary: $OUTPUT_DIR/test-summary.txt"
        echo "  - Error logs: $OUTPUT_DIR/*.log"
        exit 1
    fi
}

# Execute main function with all arguments
main "$@"
