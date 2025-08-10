#!/usr/bin/env bash
# Setup development and test data from schema.sql sample data
# This script loads the sample data defined in the schema.sql file
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
FORCE_RELOAD=${FORCE_RELOAD:-false}
CLEAR_EXISTING=${CLEAR_EXISTING:-false}
SKIP_VALIDATION=${SKIP_VALIDATION:-false}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="$BACKEND_DIR/app/infrastructure/database/schema.sql"

# Change to backend directory
cd "$BACKEND_DIR"

log_info "Starting development data setup"
log_info "Configuration:"
log_info "  - Force reload: $FORCE_RELOAD"
log_info "  - Clear existing: $CLEAR_EXISTING"
log_info "  - Skip validation: $SKIP_VALIDATION"
log_info "  - Schema file: $SCHEMA_FILE"

# Function to check if sample data already exists
check_existing_data() {
    log_info "Checking for existing sample data..."

    python3 -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.connect() as conn:
        # Check for sample jobs
        result = conn.execute(text(\"SELECT COUNT(*) FROM jobs WHERE job_number LIKE 'JOB-%'\"))
        job_count = result.fetchone()[0]

        # Check for sample operators
        result = conn.execute(text(\"SELECT COUNT(*) FROM operators WHERE employee_id LIKE 'EMP%'\"))
        operator_count = result.fetchone()[0]

        # Check for sample machines
        result = conn.execute(text(\"SELECT COUNT(*) FROM machines WHERE machine_code LIKE '%01' OR machine_code LIKE '%02'\"))
        machine_count = result.fetchone()[0]

        total_sample_records = job_count + operator_count + machine_count

        if total_sample_records > 0:
            print(f'Found existing sample data: {job_count} jobs, {operator_count} operators, {machine_count} machines')
            sys.exit(1)
        else:
            print('No existing sample data found')
            sys.exit(0)

except Exception as e:
    print(f'Error checking existing data: {e}')
    sys.exit(2)
"
    return $?
}

# Function to clear existing sample data
clear_existing_data() {
    log_info "Clearing existing sample data..."

    python3 -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.begin() as conn:
        # Delete in reverse order of dependencies

        # Delete task-related data
        conn.execute(text('DELETE FROM task_operator_assignments WHERE task_id IN (SELECT id FROM tasks WHERE job_id IN (SELECT id FROM jobs WHERE job_number LIKE \\'JOB-%\\'))'))
        conn.execute(text('DELETE FROM task_machine_options WHERE task_id IN (SELECT id FROM tasks WHERE job_id IN (SELECT id FROM jobs WHERE job_number LIKE \\'JOB-%\\'))'))
        conn.execute(text('DELETE FROM tasks WHERE job_id IN (SELECT id FROM jobs WHERE job_number LIKE \\'JOB-%\\')'))

        # Delete jobs
        conn.execute(text('DELETE FROM jobs WHERE job_number LIKE \\'JOB-%\\''))

        # Delete operator-related data
        conn.execute(text('DELETE FROM operator_skills WHERE operator_id IN (SELECT id FROM operators WHERE employee_id LIKE \\'EMP%\\')'))
        conn.execute(text('DELETE FROM operators WHERE employee_id LIKE \\'EMP%\\''))

        # Delete machine-related data
        conn.execute(text('DELETE FROM machine_capabilities WHERE machine_id IN (SELECT id FROM machines WHERE machine_code LIKE \\'%01\\' OR machine_code LIKE \\'%02\\')'))
        conn.execute(text('DELETE FROM machine_required_skills WHERE machine_id IN (SELECT id FROM machines WHERE machine_code LIKE \\'%01\\' OR machine_code LIKE \\'%02\\')'))
        conn.execute(text('DELETE FROM machines WHERE machine_code LIKE \\'%01\\' OR machine_code LIKE \\'%02\\''))

        # Delete sample skills, operations, and zones
        conn.execute(text('DELETE FROM skills WHERE skill_code IN (\\'LASER_OP\\', \\'CNC_PROG\\', \\'QUALITY\\', \\'ASSEMBLY\\', \\'MAINT\\')'))
        conn.execute(text('DELETE FROM operations WHERE operation_code LIKE \\'OP%\\''))
        conn.execute(text('DELETE FROM production_zones WHERE zone_code LIKE \\'ZONE_%\\''))

        # Delete business calendar sample data (keep working days, remove sample holiday)
        conn.execute(text('DELETE FROM business_calendar WHERE holiday_name = \\'Sample Holiday\\''))

        print('Sample data cleared successfully')

except Exception as e:
    print(f'Error clearing sample data: {e}')
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
        log_success "Existing sample data cleared"
    else
        log_error "Failed to clear existing sample data"
        return 1
    fi
}

# Function to extract and execute sample data from schema.sql
load_sample_data() {
    log_info "Loading sample data from schema.sql..."

    if [ ! -f "$SCHEMA_FILE" ]; then
        log_error "Schema file not found: $SCHEMA_FILE"
        return 1
    fi

    # Extract sample data section from schema.sql
    local temp_sample_file="/tmp/sample_data.sql"

    log_info "Extracting sample data from schema file..."
    sed -n '/-- SAMPLE DATA/,/-- HELPER FUNCTIONS FOR SCHEDULING/p' "$SCHEMA_FILE" | \
    sed '1d;$d' | \
    grep -v '^-- .*' | \
    grep -v '^$' > "$temp_sample_file"

    if [ ! -s "$temp_sample_file" ]; then
        log_error "No sample data found in schema file"
        return 1
    fi

    log_info "Executing sample data SQL..."

    # Execute the sample data using Python to ensure proper connection handling
    python3 -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

try:
    with open('$temp_sample_file', 'r') as f:
        sql_content = f.read()

    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    # Split by statements (simple approach for this specific case)
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

    with engine.begin() as conn:
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    print(f'Executing statement {i}/{len(statements)}')
                    conn.execute(text(statement))
                except Exception as e:
                    print(f'Error in statement {i}: {e}')
                    print(f'Statement: {statement[:100]}...')
                    raise

    print(f'Successfully executed {len(statements)} SQL statements')

except Exception as e:
    print(f'Error loading sample data: {e}')
    sys.exit(1)
finally:
    import os
    if os.path.exists('$temp_sample_file'):
        os.remove('$temp_sample_file')
"

    local result=$?

    # Clean up temp file
    rm -f "$temp_sample_file"

    if [ $result -eq 0 ]; then
        log_success "Sample data loaded successfully"
        return 0
    else
        log_error "Failed to load sample data"
        return 1
    fi
}

# Function to validate loaded data
validate_sample_data() {
    if [ "$SKIP_VALIDATION" = "true" ]; then
        log_info "Skipping data validation (SKIP_VALIDATION=true)"
        return 0
    fi

    log_info "Validating loaded sample data..."

    python3 -c "
from sqlalchemy import create_engine, text
from app.core.config import settings
import sys

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.connect() as conn:
        # Validate production zones
        result = conn.execute(text('SELECT COUNT(*) FROM production_zones'))
        zone_count = result.fetchone()[0]
        if zone_count == 0:
            raise Exception('No production zones found')
        print(f'✓ Production zones: {zone_count}')

        # Validate skills
        result = conn.execute(text('SELECT COUNT(*) FROM skills'))
        skill_count = result.fetchone()[0]
        if skill_count == 0:
            raise Exception('No skills found')
        print(f'✓ Skills: {skill_count}')

        # Validate operations
        result = conn.execute(text('SELECT COUNT(*) FROM operations'))
        operation_count = result.fetchone()[0]
        if operation_count == 0:
            raise Exception('No operations found')
        print(f'✓ Operations: {operation_count}')

        # Validate machines
        result = conn.execute(text('SELECT COUNT(*) FROM machines'))
        machine_count = result.fetchone()[0]
        if machine_count == 0:
            raise Exception('No machines found')
        print(f'✓ Machines: {machine_count}')

        # Validate operators
        result = conn.execute(text('SELECT COUNT(*) FROM operators'))
        operator_count = result.fetchone()[0]
        if operator_count == 0:
            raise Exception('No operators found')
        print(f'✓ Operators: {operator_count}')

        # Validate jobs
        result = conn.execute(text('SELECT COUNT(*) FROM jobs'))
        job_count = result.fetchone()[0]
        if job_count == 0:
            raise Exception('No jobs found')
        print(f'✓ Jobs: {job_count}')

        # Validate tasks
        result = conn.execute(text('SELECT COUNT(*) FROM tasks'))
        task_count = result.fetchone()[0]
        if task_count == 0:
            raise Exception('No tasks found')
        print(f'✓ Tasks: {task_count}')

        # Validate business calendar
        result = conn.execute(text('SELECT COUNT(*) FROM business_calendar'))
        calendar_count = result.fetchone()[0]
        if calendar_count == 0:
            raise Exception('No business calendar entries found')
        print(f'✓ Business calendar entries: {calendar_count}')

        # Validate relationships
        result = conn.execute(text('SELECT COUNT(*) FROM machine_capabilities'))
        capability_count = result.fetchone()[0]
        print(f'✓ Machine capabilities: {capability_count}')

        result = conn.execute(text('SELECT COUNT(*) FROM operator_skills'))
        op_skill_count = result.fetchone()[0]
        print(f'✓ Operator skills: {op_skill_count}')

        print('\\nAll validation checks passed!')

except Exception as e:
    print(f'Validation failed: {e}')
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
        log_success "Sample data validation passed"
        return 0
    else
        log_error "Sample data validation failed"
        return 1
    fi
}

# Function to display data summary
show_data_summary() {
    log_info "Sample data summary:"

    python3 -c "
from sqlalchemy import create_engine, text
from app.core.config import settings

try:
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    with engine.connect() as conn:
        # Get counts for each main entity
        entities = [
            ('Production Zones', 'production_zones'),
            ('Skills', 'skills'),
            ('Operations', 'operations'),
            ('Machines', 'machines'),
            ('Operators', 'operators'),
            ('Jobs', 'jobs'),
            ('Tasks', 'tasks'),
            ('Business Calendar', 'business_calendar')
        ]

        for name, table in entities:
            result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
            count = result.fetchone()[0]
            print(f'  - {name}: {count}')

except Exception as e:
    print(f'Error getting summary: {e}')
"
}

# Main execution
main() {
    log_info "=== Development Data Setup Started ==="

    # Check if sample data already exists
    if check_existing_data; then
        existing_status=$?
        if [ $existing_status -eq 1 ] && [ "$FORCE_RELOAD" != "true" ]; then
            log_warning "Sample data already exists"
            log_warning "Use FORCE_RELOAD=true to reload or CLEAR_EXISTING=true to clear first"
            show_data_summary
            exit 0
        elif [ $existing_status -eq 1 ] && [ "$CLEAR_EXISTING" = "true" ]; then
            if ! clear_existing_data; then
                log_error "Failed to clear existing data"
                exit 1
            fi
        fi
    fi

    # Load sample data
    if ! load_sample_data; then
        log_error "Development data setup failed"
        exit 1
    fi

    # Validate loaded data
    if ! validate_sample_data; then
        log_error "Sample data validation failed"
        exit 1
    fi

    # Show summary
    show_data_summary

    log_success "=== Development Data Setup Completed Successfully ==="
    return 0
}

# Handle script termination
cleanup() {
    # Clean up any temporary files
    rm -f /tmp/sample_data.sql
}

trap cleanup EXIT

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
