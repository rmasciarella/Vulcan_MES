#!/bin/bash
# Database Testing Script for Vulcan Engine Backend
#
# This script runs the comprehensive database test suite with various options
# for different testing scenarios and reporting requirements.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_PATH="app/tests/database/"
VERBOSE=false
COVERAGE=false
MARKERS=""
OUTPUT_FORMAT="text"
PARALLEL=false
BENCHMARK=false

# Function to print usage
print_usage() {
    echo "Database Test Runner for Vulcan Engine"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message"
    echo "  -v, --verbose        Enable verbose output"
    echo "  -c, --coverage       Run with coverage reporting"
    echo "  -m, --markers        Run tests with specific markers (connectivity,models,crud,integration,performance,errors)"
    echo "  -f, --format         Output format (text,html,xml) [default: text]"
    echo "  -p, --parallel       Run tests in parallel"
    echo "  -b, --benchmark      Run performance benchmarks"
    echo "  --connectivity       Run connectivity tests only"
    echo "  --models            Run model validation tests only"
    echo "  --crud              Run CRUD operation tests only"
    echo "  --integration       Run integration tests only"
    echo "  --performance       Run performance tests only"
    echo "  --errors            Run error handling tests only"
    echo "  --all               Run all database tests (default)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all database tests"
    echo "  $0 --connectivity                     # Run connectivity tests only"
    echo "  $0 --performance --benchmark          # Run performance tests with benchmarking"
    echo "  $0 --coverage --format html           # Run with HTML coverage report"
    echo "  $0 --parallel --verbose               # Run tests in parallel with verbose output"
}

# Function to log messages
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

log_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            print_usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -m|--markers)
            MARKERS="$2"
            shift 2
            ;;
        -f|--format)
            OUTPUT_FORMAT="$2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -b|--benchmark)
            BENCHMARK=true
            shift
            ;;
        --connectivity)
            TEST_PATH="app/tests/database/test_connectivity.py"
            shift
            ;;
        --models)
            TEST_PATH="app/tests/database/test_models.py"
            shift
            ;;
        --crud)
            TEST_PATH="app/tests/database/test_repositories.py"
            shift
            ;;
        --integration)
            TEST_PATH="app/tests/database/test_integration.py"
            shift
            ;;
        --performance)
            TEST_PATH="app/tests/database/test_performance.py"
            shift
            ;;
        --errors)
            TEST_PATH="app/tests/database/test_error_handling.py"
            shift
            ;;
        --all)
            TEST_PATH="app/tests/database/"
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Check if we're in the correct directory
if [ ! -f "app/main.py" ]; then
    log_error "Please run this script from the backend directory"
    exit 1
fi

# Check if test directory exists
if [ ! -d "$TEST_PATH" ] && [ ! -f "$TEST_PATH" ]; then
    log_error "Test path does not exist: $TEST_PATH"
    exit 1
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add test path
PYTEST_CMD="$PYTEST_CMD $TEST_PATH"

# Add markers if specified
if [ -n "$MARKERS" ]; then
    PYTEST_CMD="$PYTEST_CMD -m '$MARKERS'"
fi

# Add verbose flag
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add parallel execution
if [ "$PARALLEL" = true ]; then
    log "Enabling parallel test execution"
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add coverage reporting
if [ "$COVERAGE" = true ]; then
    log "Enabling coverage reporting"
    PYTEST_CMD="$PYTEST_CMD --cov=app.domain --cov=app.core.db --cov=app.tests.database"

    case $OUTPUT_FORMAT in
        html)
            PYTEST_CMD="$PYTEST_CMD --cov-report=html:htmlcov/database"
            ;;
        xml)
            PYTEST_CMD="$PYTEST_CMD --cov-report=xml:coverage-database.xml"
            ;;
        *)
            PYTEST_CMD="$PYTEST_CMD --cov-report=term-missing"
            ;;
    esac
fi

# Add benchmark flags if requested
if [ "$BENCHMARK" = true ]; then
    log "Enabling performance benchmarking"
    PYTEST_CMD="$PYTEST_CMD --benchmark-only --benchmark-sort=mean"
fi

# Set up environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

log "Starting database tests..."
log "Test path: $TEST_PATH"
log "Command: $PYTEST_CMD"

# Run the tests
if eval $PYTEST_CMD; then
    log_success "Database tests completed successfully!"

    # Show coverage report location if generated
    if [ "$COVERAGE" = true ]; then
        case $OUTPUT_FORMAT in
            html)
                log_success "HTML coverage report generated: htmlcov/database/index.html"
                ;;
            xml)
                log_success "XML coverage report generated: coverage-database.xml"
                ;;
        esac
    fi

    exit 0
else
    EXIT_CODE=$?
    log_error "Database tests failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
fi
