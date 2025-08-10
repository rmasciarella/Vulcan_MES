#!/usr/bin/env bash
# Prestart script for database setup and initialization
# Enhanced version with comprehensive database initialization
set -e

# Color output functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration
USE_COMPREHENSIVE_INIT=${USE_COMPREHENSIVE_INIT:-false}
SKIP_HEALTH_CHECK=${SKIP_HEALTH_CHECK:-false}
BACKUP_BEFORE_START=${BACKUP_BEFORE_START:-false}
LOAD_SAMPLE_DATA=${LOAD_SAMPLE_DATA:-false}
ENVIRONMENT=${ENVIRONMENT:-local}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info "=== Database Prestart Initialization Started ==="
log_info "Environment: $ENVIRONMENT"
log_info "Configuration:"
log_info "  - Use comprehensive init: $USE_COMPREHENSIVE_INIT"
log_info "  - Skip health check: $SKIP_HEALTH_CHECK"
log_info "  - Backup before start: $BACKUP_BEFORE_START"
log_info "  - Load sample data: $LOAD_SAMPLE_DATA"

# Function to run basic initialization (original behavior)
run_basic_init() {
    log_info "Running basic database initialization..."

    # Let the DB start
    log_info "Checking database connection..."
    python app/backend_pre_start.py

    # Run migrations
    log_info "Running database migrations..."
    alembic upgrade head

    # Create initial data in DB
    log_info "Creating initial data..."
    python app/initial_data.py

    log_success "Basic database setup completed successfully"
}

# Function to run comprehensive initialization
run_comprehensive_init() {
    log_info "Running comprehensive database initialization..."

    # Set environment variables for init script
    export SKIP_SAMPLE_DATA=$([ "$LOAD_SAMPLE_DATA" = "true" ] && echo "false" || echo "true")
    export BACKUP_BEFORE_INIT="$BACKUP_BEFORE_START"
    export ENVIRONMENT="$ENVIRONMENT"

    # Run comprehensive init script
    if bash "$SCRIPT_DIR/init_db.sh"; then
        log_success "Comprehensive database initialization completed"
    else
        log_error "Comprehensive database initialization failed"
        return 1
    fi
}

# Function to run health check
run_health_check() {
    if [ "$SKIP_HEALTH_CHECK" = "true" ]; then
        log_info "Skipping health check (SKIP_HEALTH_CHECK=true)"
        return 0
    fi

    log_info "Running database health check..."

    if python3 app/core/db_health.py --check connectivity; then
        log_success "Database health check passed"
        return 0
    else
        log_warning "Database health check failed"
        return 1
    fi
}

# Function to display final status
display_final_status() {
    log_info "=== Final Database Status ==="

    # Run comprehensive health check for final status
    if [ "$SKIP_HEALTH_CHECK" != "true" ]; then
        python3 app/core/db_health.py --json 2>/dev/null | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    print(f'Overall Status: {data[\"overall_status\"].upper()}')
    print(f'Overall Health: {data[\"overall_health\"]}')
    print(f'Summary: {data[\"summary\"][\"healthy\"]} healthy, {data[\"summary\"][\"warnings\"]} warnings, {data[\"summary\"][\"unhealthy\"]} unhealthy')
    print(f'Environment: {data[\"environment\"]}')

    if not data['overall_health']:
        print('\\nIssues found:')
        for check in data['checks']:
            if check['status'] != 'healthy':
                print(f'  - {check[\"test_name\"]}: {check[\"message\"]}')
except:
    print('Unable to get detailed health status')
"
    fi

    log_success "=== Database Prestart Initialization Completed ==="
}

# Main execution
main() {
    local exit_code=0

    try_initialization() {
        if [ "$USE_COMPREHENSIVE_INIT" = "true" ]; then
            run_comprehensive_init
        else
            run_basic_init
        fi
    }

    # Run initialization
    if ! try_initialization; then
        log_error "Database initialization failed"
        exit_code=1
    fi

    # Run health check (unless skipped or init failed)
    if [ $exit_code -eq 0 ] && ! run_health_check; then
        log_warning "Health check failed but continuing..."
        # Don't fail the startup for health check warnings
    fi

    # Display final status
    display_final_status

    if [ $exit_code -eq 0 ]; then
        log_success "Database is ready for application startup"
    else
        log_error "Database initialization failed - application may not function properly"
    fi

    return $exit_code
}

# Handle script termination
cleanup() {
    log_info "Cleaning up prestart script..."
    # Add any cleanup logic here
}

trap cleanup EXIT

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
