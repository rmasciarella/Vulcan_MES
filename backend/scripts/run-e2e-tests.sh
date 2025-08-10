#!/bin/bash
set -e

# End-to-End Test Runner Script
# Executes comprehensive E2E workflow integration tests

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TEST_DIR="app/tests/e2e"
COVERAGE_MIN=80
REPORTS_DIR="test-reports/e2e"
LOG_FILE="$REPORTS_DIR/e2e-test.log"

# Ensure reports directory exists
mkdir -p "$REPORTS_DIR"

echo -e "${BLUE}=== End-to-End Workflow Integration Tests ===${NC}"
echo "Starting comprehensive E2E test suite..."
echo "Reports will be saved to: $REPORTS_DIR"
echo

# Function to run test with error handling
run_test_suite() {
    local test_name="$1"
    local test_pattern="$2"
    local description="$3"
    local allow_failures="${4:-false}"

    echo -e "${YELLOW}Running $test_name...${NC}"
    echo "Description: $description"
    echo

    local start_time=$(date +%s)
    local test_result=0

    if [ "$allow_failures" = "true" ]; then
        # Run with continue-on-error for optional tests
        pytest "$test_pattern" -v --tb=short --junitxml="$REPORTS_DIR/${test_name}-results.xml" 2>&1 | tee -a "$LOG_FILE" || test_result=$?
    else
        # Run with strict failure handling
        pytest "$test_pattern" -v --tb=short --junitxml="$REPORTS_DIR/${test_name}-results.xml" 2>&1 | tee -a "$LOG_FILE"
    fi

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [ $test_result -eq 0 ]; then
        echo -e "${GREEN}✓ $test_name completed successfully (${duration}s)${NC}"
    else
        if [ "$allow_failures" = "true" ]; then
            echo -e "${YELLOW}⚠ $test_name completed with warnings (${duration}s)${NC}"
        else
            echo -e "${RED}✗ $test_name failed (${duration}s)${NC}"
            return $test_result
        fi
    fi
    echo
}

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}Checking prerequisites...${NC}"

    # Check if pytest is installed
    if ! command -v pytest &> /dev/null; then
        echo -e "${RED}Error: pytest is not installed${NC}"
        echo "Install with: pip install pytest"
        exit 1
    fi

    # Check if test directory exists
    if [ ! -d "$TEST_DIR" ]; then
        echo -e "${RED}Error: Test directory $TEST_DIR does not exist${NC}"
        exit 1
    fi

    # Check database connection
    if ! python -c "from app.core.db_test import test_engine; print('Database connection OK')" 2>/dev/null; then
        echo -e "${YELLOW}Warning: Test database connection could not be verified${NC}"
    fi

    echo -e "${GREEN}✓ Prerequisites check passed${NC}"
    echo
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  --quick          Run only fast E2E tests (skip performance tests)"
    echo "  --performance    Run only performance tests"
    echo "  --security       Run only security tests"
    echo "  --websocket      Run only WebSocket tests (requires WebSocket server)"
    echo "  --audit          Run only audit and compliance tests"
    echo "  --with-coverage  Run with code coverage analysis"
    echo "  --parallel       Run tests in parallel (faster but uses more resources)"
    echo "  --debug          Run with detailed debug output"
    echo "  --help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0                     # Run all E2E tests"
    echo "  $0 --quick            # Run fast tests only"
    echo "  $0 --with-coverage    # Run with coverage report"
    echo "  $0 --performance      # Run performance tests only"
}

# Parse command line arguments
QUICK_MODE=false
PERFORMANCE_ONLY=false
SECURITY_ONLY=false
WEBSOCKET_ONLY=false
AUDIT_ONLY=false
WITH_COVERAGE=false
PARALLEL_MODE=false
DEBUG_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --performance)
            PERFORMANCE_ONLY=true
            shift
            ;;
        --security)
            SECURITY_ONLY=true
            shift
            ;;
        --websocket)
            WEBSOCKET_ONLY=true
            shift
            ;;
        --audit)
            AUDIT_ONLY=true
            shift
            ;;
        --with-coverage)
            WITH_COVERAGE=true
            shift
            ;;
        --parallel)
            PARALLEL_MODE=true
            shift
            ;;
        --debug)
            DEBUG_MODE=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    local start_time=$(date +%s)

    # Initialize log file
    echo "E2E Test Execution Log - $(date)" > "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"

    # Check prerequisites
    check_prerequisites

    # Set up pytest arguments
    PYTEST_ARGS="-v --tb=short"

    if [ "$WITH_COVERAGE" = true ]; then
        PYTEST_ARGS="$PYTEST_ARGS --cov=app --cov-report=html:$REPORTS_DIR/coverage --cov-report=xml:$REPORTS_DIR/coverage.xml"
    fi

    if [ "$PARALLEL_MODE" = true ]; then
        PYTEST_ARGS="$PYTEST_ARGS -n auto"
    fi

    if [ "$DEBUG_MODE" = true ]; then
        PYTEST_ARGS="$PYTEST_ARGS -s --tb=long"
    fi

    # Execute test suites based on mode
    if [ "$QUICK_MODE" = true ]; then
        echo -e "${BLUE}Running in QUICK mode (skipping slow tests)${NC}"
        echo

        run_test_suite "quick-workflow" "$TEST_DIR -m 'e2e and not slow and not performance'" \
            "Fast E2E workflow tests"

    elif [ "$PERFORMANCE_ONLY" = true ]; then
        echo -e "${BLUE}Running PERFORMANCE tests only${NC}"
        echo

        run_test_suite "performance" "$TEST_DIR/test_performance_integration_e2e.py" \
            "Large-scale performance and load tests" true

    elif [ "$SECURITY_ONLY" = true ]; then
        echo -e "${BLUE}Running SECURITY tests only${NC}"
        echo

        run_test_suite "security" "$TEST_DIR/test_security_integration_e2e.py" \
            "Authentication, authorization, and security tests"

    elif [ "$WEBSOCKET_ONLY" = true ]; then
        echo -e "${BLUE}Running WEBSOCKET tests only${NC}"
        echo -e "${YELLOW}Note: WebSocket server must be running${NC}"
        echo

        run_test_suite "websocket" "$TEST_DIR/test_websocket_integration_e2e.py" \
            "Real-time WebSocket integration tests" true

    elif [ "$AUDIT_ONLY" = true ]; then
        echo -e "${BLUE}Running AUDIT & COMPLIANCE tests only${NC}"
        echo

        run_test_suite "audit-compliance" "$TEST_DIR/test_audit_compliance_e2e.py" \
            "Audit trail and regulatory compliance tests"

    else
        echo -e "${BLUE}Running COMPLETE E2E test suite${NC}"
        echo

        # Run all test suites in recommended order
        run_test_suite "workflow-integration" "$TEST_DIR/test_scheduling_workflow_e2e.py" \
            "Complete workflow integration from job creation to execution"

        run_test_suite "multi-user-workflows" "$TEST_DIR/test_multi_user_workflow_e2e.py" \
            "Multi-user collaboration and role-based workflows"

        run_test_suite "error-recovery" "$TEST_DIR/test_error_recovery_workflow_e2e.py" \
            "Error handling and system recovery scenarios"

        run_test_suite "data-integrity" "$TEST_DIR/test_data_integrity_e2e.py" \
            "Data consistency and transaction integrity"

        run_test_suite "security-integration" "$TEST_DIR/test_security_integration_e2e.py" \
            "Security, authentication, and authorization workflows"

        run_test_suite "audit-compliance" "$TEST_DIR/test_audit_compliance_e2e.py" \
            "Audit trail and regulatory compliance verification"

        # Optional tests (allow failures)
        run_test_suite "websocket-integration" "$TEST_DIR/test_websocket_integration_e2e.py" \
            "Real-time WebSocket updates (requires WebSocket server)" true

        run_test_suite "performance-integration" "$TEST_DIR/test_performance_integration_e2e.py" \
            "Large-scale performance and load testing" true
    fi

    # Generate summary report
    generate_summary_report

    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))

    echo -e "${GREEN}=== E2E Test Execution Complete ===${NC}"
    echo "Total execution time: ${total_duration} seconds"
    echo "Reports saved to: $REPORTS_DIR"
    echo "Log file: $LOG_FILE"

    # Show coverage summary if enabled
    if [ "$WITH_COVERAGE" = true ]; then
        echo
        echo -e "${BLUE}Coverage Report:${NC}"
        echo "HTML report: $REPORTS_DIR/coverage/index.html"
        echo "XML report: $REPORTS_DIR/coverage.xml"
    fi

    echo
}

# Function to generate summary report
generate_summary_report() {
    local summary_file="$REPORTS_DIR/e2e-summary.txt"

    echo "E2E Test Execution Summary" > "$summary_file"
    echo "=========================" >> "$summary_file"
    echo "Execution Date: $(date)" >> "$summary_file"
    echo "Test Directory: $TEST_DIR" >> "$summary_file"
    echo >> "$summary_file"

    # Count test results from XML files
    if command -v xmllint &> /dev/null; then
        local total_tests=0
        local passed_tests=0
        local failed_tests=0
        local skipped_tests=0

        for xml_file in "$REPORTS_DIR"/*-results.xml; do
            if [ -f "$xml_file" ]; then
                local file_tests=$(xmllint --xpath "count(//testcase)" "$xml_file" 2>/dev/null || echo "0")
                local file_failures=$(xmllint --xpath "count(//testcase/failure)" "$xml_file" 2>/dev/null || echo "0")
                local file_errors=$(xmllint --xpath "count(//testcase/error)" "$xml_file" 2>/dev/null || echo "0")
                local file_skipped=$(xmllint --xpath "count(//testcase/skipped)" "$xml_file" 2>/dev/null || echo "0")

                total_tests=$((total_tests + file_tests))
                failed_tests=$((failed_tests + file_failures + file_errors))
                skipped_tests=$((skipped_tests + file_skipped))
            fi
        done

        passed_tests=$((total_tests - failed_tests - skipped_tests))

        echo "Test Results:" >> "$summary_file"
        echo "  Total Tests: $total_tests" >> "$summary_file"
        echo "  Passed: $passed_tests" >> "$summary_file"
        echo "  Failed: $failed_tests" >> "$summary_file"
        echo "  Skipped: $skipped_tests" >> "$summary_file"

        if [ $total_tests -gt 0 ]; then
            local pass_rate=$((passed_tests * 100 / total_tests))
            echo "  Pass Rate: ${pass_rate}%" >> "$summary_file"
        fi
    fi

    echo >> "$summary_file"
    echo "Report Files:" >> "$summary_file"
    ls -la "$REPORTS_DIR" >> "$summary_file"

    echo -e "${BLUE}Summary report generated: $summary_file${NC}"
}

# Handle script interruption
trap 'echo -e "${RED}Test execution interrupted${NC}"; exit 130' INT

# Execute main function
main "$@"
