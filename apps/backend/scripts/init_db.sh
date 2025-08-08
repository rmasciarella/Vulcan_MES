#!/usr/bin/env bash
# Complete database initialization script for production deployment
# This script handles fresh database setup, migrations, and initial data loading
set -e
set -x

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

# Default values
FORCE_RESET=${FORCE_RESET:-false}
SKIP_SAMPLE_DATA=${SKIP_SAMPLE_DATA:-false}
BACKUP_BEFORE_INIT=${BACKUP_BEFORE_INIT:-true}
ENVIRONMENT=${ENVIRONMENT:-local}
MAX_RETRIES=${MAX_RETRIES:-5}
RETRY_DELAY=${RETRY_DELAY:-10}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Change to backend directory
cd "$BACKEND_DIR"

log_info "Starting database initialization for environment: $ENVIRONMENT"
log_info "Configuration:"
log_info "  - Force reset: $FORCE_RESET"
log_info "  - Skip sample data: $SKIP_SAMPLE_DATA"
log_info "  - Backup before init: $BACKUP_BEFORE_INIT"
log_info "  - Max retries: $MAX_RETRIES"

# Function to check if database exists and has tables
check_database_exists() {
    log_info "Checking if database exists and has content..."
    python3 -c "
import sys
from sqlalchemy import create_engine, text, inspect
from app.core.config import settings

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.connect() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f'Found {len(tables)} tables')
        if len(tables) > 0:
            print('Database has existing schema')
            sys.exit(1)
        else:
            print('Database is empty')
            sys.exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(2)
"
    return $?
}

# Function to wait for database to be ready
wait_for_database() {
    log_info "Waiting for database to be ready..."
    local retry_count=0

    while [ $retry_count -lt $MAX_RETRIES ]; do
        if python3 app/backend_pre_start.py; then
            log_success "Database is ready"
            return 0
        else
            retry_count=$((retry_count + 1))
            log_warning "Database not ready, retry $retry_count/$MAX_RETRIES"
            if [ $retry_count -lt $MAX_RETRIES ]; then
                log_info "Waiting ${RETRY_DELAY}s before retry..."
                sleep $RETRY_DELAY
            fi
        fi
    done

    log_error "Database failed to become ready after $MAX_RETRIES attempts"
    return 1
}

# Function to backup existing database
backup_database() {
    if [ "$BACKUP_BEFORE_INIT" = "true" ]; then
        log_info "Creating database backup before initialization..."
        local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"

        if bash "$SCRIPT_DIR/backup_restore.sh" backup "$backup_file"; then
            log_success "Database backed up to $backup_file"
        else
            log_warning "Backup failed, continuing with initialization..."
        fi
    fi
}

# Function to run database health check
run_health_check() {
    log_info "Running database health check..."

    if python3 -c "
from app.core.db_health import DatabaseHealthChecker
checker = DatabaseHealthChecker()
result = checker.comprehensive_health_check()
if not result['overall_health']:
    print('Health check failed')
    exit(1)
else:
    print('Health check passed')
    exit(0)
"; then
        log_success "Database health check passed"
        return 0
    else
        log_error "Database health check failed"
        return 1
    fi
}

# Function to setup database schema
setup_database_schema() {
    log_info "Setting up database schema..."

    # Check current migration status
    log_info "Checking current migration status..."
    local current_revision
    current_revision=$(alembic current 2>/dev/null || echo "none")
    log_info "Current revision: $current_revision"

    # If no migrations exist, create initial migration from schema.sql
    if [ "$current_revision" = "none" ] || [ "$current_revision" = "" ]; then
        log_info "No existing migrations found, creating initial migration..."

        # Check if we have the schema conversion script
        if [ -f "app/infrastructure/database/schema_to_migration.py" ]; then
            log_info "Converting schema.sql to Alembic migration..."
            python3 app/infrastructure/database/schema_to_migration.py
        else
            log_warning "Schema conversion script not found, using standard Alembic migration..."
        fi
    fi

    # Run migrations
    log_info "Running database migrations..."
    bash "$SCRIPT_DIR/migrate.sh" upgrade head

    if [ $? -ne 0 ]; then
        log_error "Migration failed"
        return 1
    fi

    log_success "Database schema setup completed"
}

# Function to load initial data
load_initial_data() {
    log_info "Loading initial application data..."

    if python3 app/initial_data.py; then
        log_success "Initial application data loaded successfully"
    else
        log_error "Failed to load initial application data"
        return 1
    fi
}

# Function to load sample data
load_sample_data() {
    if [ "$SKIP_SAMPLE_DATA" = "false" ]; then
        log_info "Loading sample/development data..."

        if bash "$SCRIPT_DIR/setup_dev_data.sh"; then
            log_success "Sample data loaded successfully"
        else
            log_error "Failed to load sample data"
            return 1
        fi
    else
        log_info "Skipping sample data loading (SKIP_SAMPLE_DATA=true)"
    fi
}

# Function to verify installation
verify_installation() {
    log_info "Verifying database installation..."

    # Check that we can connect and basic tables exist
    python3 -c "
from sqlalchemy import create_engine, text, inspect
from app.core.config import settings
import sys

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.connect() as conn:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        # Check for essential tables
        essential_tables = ['users', 'jobs', 'tasks', 'operators', 'machines', 'operations']
        missing_tables = []

        for table in essential_tables:
            if table not in tables:
                missing_tables.append(table)

        if missing_tables:
            print(f'Missing essential tables: {missing_tables}')
            sys.exit(1)

        print(f'Database verification passed: {len(tables)} tables found')

        # Check if we can run a simple query
        result = conn.execute(text('SELECT COUNT(*) as user_count FROM users'))
        user_count = result.fetchone()[0]
        print(f'Found {user_count} users in database')

except Exception as e:
    print(f'Database verification failed: {e}')
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
        log_success "Database verification completed successfully"
        return 0
    else
        log_error "Database verification failed"
        return 1
    fi
}

# Main execution
main() {
    log_info "=== Database Initialization Started ==="

    # Step 1: Wait for database to be available
    if ! wait_for_database; then
        log_error "Database initialization failed - database not available"
        exit 1
    fi

    # Step 2: Check if database already exists with data
    if check_database_exists; then
        database_status=$?
        if [ $database_status -eq 1 ] && [ "$FORCE_RESET" != "true" ]; then
            log_warning "Database already contains data"
            log_warning "Use FORCE_RESET=true to reset existing database"
            log_info "Attempting to run migrations on existing database..."

            # Try to upgrade existing database
            if bash "$SCRIPT_DIR/migrate.sh" upgrade head; then
                log_success "Existing database updated successfully"
                run_health_check
                exit 0
            else
                log_error "Failed to update existing database"
                exit 1
            fi
        elif [ $database_status -eq 1 ] && [ "$FORCE_RESET" = "true" ]; then
            log_warning "Force reset enabled - backing up and resetting database"
            backup_database
        fi
    fi

    # Step 3: Setup database schema
    if ! setup_database_schema; then
        log_error "Database initialization failed during schema setup"
        exit 1
    fi

    # Step 4: Load initial data
    if ! load_initial_data; then
        log_error "Database initialization failed during initial data loading"
        exit 1
    fi

    # Step 5: Load sample data (if requested)
    if ! load_sample_data; then
        log_error "Database initialization failed during sample data loading"
        exit 1
    fi

    # Step 6: Verify installation
    if ! verify_installation; then
        log_error "Database initialization failed verification"
        exit 1
    fi

    # Step 7: Run final health check
    if ! run_health_check; then
        log_warning "Database initialization completed but health check failed"
        exit 1
    fi

    log_success "=== Database Initialization Completed Successfully ==="
    log_info "Database is ready for use"

    # Print summary
    log_info "Summary:"
    log_info "  - Environment: $ENVIRONMENT"
    log_info "  - Schema: Initialized with migrations"
    log_info "  - Initial data: Loaded"
    log_info "  - Sample data: $([ "$SKIP_SAMPLE_DATA" = "true" ] && echo "Skipped" || echo "Loaded")"
    log_info "  - Health check: Passed"

    return 0
}

# Handle script termination
cleanup() {
    log_info "Cleaning up..."
    # Add any cleanup logic here
}

trap cleanup EXIT

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
