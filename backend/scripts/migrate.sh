#!/usr/bin/env bash
# Safe Alembic migration runner with rollback capabilities and validation
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
AUTO_BACKUP=${AUTO_BACKUP:-true}
VALIDATE_AFTER_MIGRATION=${VALIDATE_AFTER_MIGRATION:-true}
DRY_RUN=${DRY_RUN:-false}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Change to backend directory
cd "$BACKEND_DIR"

# Usage function
show_usage() {
    echo "Usage: $0 <command> [target]"
    echo ""
    echo "Commands:"
    echo "  current             Show current revision"
    echo "  history             Show migration history"
    echo "  upgrade <target>    Upgrade to target revision (default: head)"
    echo "  downgrade <target>  Downgrade to target revision"
    echo "  revision <message>  Create new migration with message"
    echo "  autogenerate <msg>  Auto-generate migration with message"
    echo "  validate            Validate database matches current migrations"
    echo "  stamp <target>      Mark database as being at target revision"
    echo "  reset               Reset to base and upgrade to head (DESTRUCTIVE)"
    echo ""
    echo "Options (via environment variables):"
    echo "  AUTO_BACKUP=true/false      Create backup before destructive operations"
    echo "  VALIDATE_AFTER_MIGRATION=true/false  Validate after migrations"
    echo "  DRY_RUN=true/false          Show what would be done without executing"
    echo ""
    echo "Examples:"
    echo "  $0 current"
    echo "  $0 upgrade head"
    echo "  $0 downgrade -1"
    echo "  AUTO_BACKUP=false $0 upgrade head"
    echo "  DRY_RUN=true $0 downgrade base"
}

# Function to get current revision
get_current_revision() {
    alembic current --verbose 2>/dev/null | head -n 1 | grep -oE '[a-f0-9]{12}' || echo "none"
}

# Function to create backup before destructive operations
create_backup() {
    if [ "$AUTO_BACKUP" = "true" ]; then
        local backup_name="migration_backup_$(date +%Y%m%d_%H%M%S)"
        log_info "Creating backup before migration: $backup_name"

        if bash "$SCRIPT_DIR/backup_restore.sh" backup "$backup_name.sql" > /dev/null 2>&1; then
            log_success "Backup created: $backup_name.sql"
            echo "$backup_name.sql"
        else
            log_warning "Backup creation failed, continuing without backup"
            echo ""
        fi
    else
        log_info "Skipping backup (AUTO_BACKUP=false)"
        echo ""
    fi
}

# Function to validate database state
validate_database() {
    if [ "$VALIDATE_AFTER_MIGRATION" = "false" ]; then
        log_info "Skipping database validation (VALIDATE_AFTER_MIGRATION=false)"
        return 0
    fi

    log_info "Validating database state after migration..."

    # Check if database schema matches Alembic expectations
    local validation_output
    validation_output=$(alembic check 2>&1 || echo "VALIDATION_FAILED")

    if [[ "$validation_output" == *"VALIDATION_FAILED"* ]]; then
        log_error "Database validation failed"
        log_error "Alembic output: $validation_output"
        return 1
    else
        log_success "Database validation passed"
        return 0
    fi
}

# Function to show current status
show_current() {
    log_info "Current migration status:"

    local current_rev
    current_rev=$(get_current_revision)

    if [ "$current_rev" = "none" ]; then
        echo "  Current revision: None (empty database)"
    else
        echo "  Current revision: $current_rev"

        # Get revision details
        local rev_info
        rev_info=$(alembic show "$current_rev" 2>/dev/null || echo "Unable to get revision details")
        echo "  Details: $rev_info"
    fi

    # Show pending migrations
    echo ""
    log_info "Checking for pending migrations..."
    local heads
    heads=$(alembic heads 2>/dev/null || echo "unknown")

    if [ "$current_rev" = "$heads" ] || [ "$heads" = "unknown" ]; then
        log_success "Database is up to date"
    else
        log_warning "Pending migrations available"
        echo "  Latest available: $heads"
    fi
}

# Function to show migration history
show_history() {
    log_info "Migration history:"
    alembic history --verbose
}

# Function to upgrade database
upgrade_database() {
    local target=${1:-head}
    local current_rev
    current_rev=$(get_current_revision)

    log_info "Upgrading database from '$current_rev' to '$target'"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute: alembic upgrade $target"
        return 0
    fi

    # Create backup for major upgrades
    local backup_file=""
    if [ "$target" = "head" ] || [ "$current_rev" = "none" ]; then
        backup_file=$(create_backup)
    fi

    # Perform upgrade
    if alembic upgrade "$target"; then
        log_success "Database upgraded successfully to '$target'"

        # Validate after upgrade
        if ! validate_database; then
            log_warning "Migration completed but validation failed"
            if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
                log_info "Backup available for rollback: $backup_file"
            fi
            return 1
        fi

        return 0
    else
        log_error "Database upgrade failed"

        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            log_info "Backup available for rollback: $backup_file"
            log_info "To restore: bash $SCRIPT_DIR/backup_restore.sh restore $backup_file"
        fi

        return 1
    fi
}

# Function to downgrade database
downgrade_database() {
    local target=${1:-}

    if [ -z "$target" ]; then
        log_error "Downgrade target is required"
        log_info "Use: -1 (previous revision), -2 (two revisions back), or specific revision ID"
        return 1
    fi

    local current_rev
    current_rev=$(get_current_revision)

    log_warning "Downgrading database from '$current_rev' to '$target'"
    log_warning "This is a potentially destructive operation!"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute: alembic downgrade $target"
        return 0
    fi

    # Always create backup for downgrades
    local backup_file
    backup_file=$(create_backup)

    # Confirm downgrade (unless in CI/automated environment)
    if [ -t 0 ] && [ -z "$CI" ]; then
        echo -n "Are you sure you want to downgrade? [y/N]: "
        read -r confirmation
        if [[ ! "$confirmation" =~ ^[Yy]$ ]]; then
            log_info "Downgrade cancelled by user"
            return 0
        fi
    fi

    # Perform downgrade
    if alembic downgrade "$target"; then
        log_success "Database downgraded successfully to '$target'"

        # Validate after downgrade
        validate_database

        return 0
    else
        log_error "Database downgrade failed"

        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            log_info "Backup available for recovery: $backup_file"
            log_info "To restore: bash $SCRIPT_DIR/backup_restore.sh restore $backup_file"
        fi

        return 1
    fi
}

# Function to create new migration
create_revision() {
    local message=${1:-"New migration"}

    log_info "Creating new migration: '$message'"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute: alembic revision -m \"$message\""
        return 0
    fi

    if alembic revision -m "$message"; then
        log_success "New migration created successfully"

        # Show the created file
        local latest_migration
        latest_migration=$(find app/alembic/versions -name "*.py" -type f -exec stat -f "%m %N" {} \; | sort -n | tail -n 1 | cut -d' ' -f2-)

        if [ -n "$latest_migration" ]; then
            log_info "Migration file created: $latest_migration"
        fi

        return 0
    else
        log_error "Failed to create migration"
        return 1
    fi
}

# Function to auto-generate migration
autogenerate_migration() {
    local message=${1:-"Auto-generated migration"}

    log_info "Auto-generating migration: '$message'"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute: alembic revision --autogenerate -m \"$message\""
        return 0
    fi

    if alembic revision --autogenerate -m "$message"; then
        log_success "Migration auto-generated successfully"

        # Show the created file
        local latest_migration
        latest_migration=$(find app/alembic/versions -name "*.py" -type f -exec stat -f "%m %N" {} \; | sort -n | tail -n 1 | cut -d' ' -f2-)

        if [ -n "$latest_migration" ]; then
            log_info "Migration file created: $latest_migration"
            log_warning "Please review the generated migration before applying!"
        fi

        return 0
    else
        log_error "Failed to auto-generate migration"
        return 1
    fi
}

# Function to stamp database
stamp_database() {
    local target=${1:-}

    if [ -z "$target" ]; then
        log_error "Stamp target is required"
        return 1
    fi

    log_warning "Stamping database as revision '$target'"
    log_warning "This marks the database as being at the specified revision without running migrations!"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute: alembic stamp $target"
        return 0
    fi

    if alembic stamp "$target"; then
        log_success "Database stamped successfully as '$target'"
        return 0
    else
        log_error "Failed to stamp database"
        return 1
    fi
}

# Function to reset database (dangerous)
reset_database() {
    log_error "DATABASE RESET REQUESTED - THIS IS DESTRUCTIVE!"
    log_warning "This will:"
    log_warning "  1. Downgrade to base (remove all data)"
    log_warning "  2. Upgrade to head (recreate schema)"
    log_warning "  3. This will DELETE ALL DATA!"

    if [ "$DRY_RUN" = "true" ]; then
        log_warning "DRY RUN - Would execute database reset sequence"
        return 0
    fi

    # Confirm reset (unless in CI/automated environment)
    if [ -t 0 ] && [ -z "$CI" ]; then
        echo -n "Are you ABSOLUTELY sure you want to reset the database? [y/N]: "
        read -r confirmation
        if [[ ! "$confirmation" =~ ^[Yy]$ ]]; then
            log_info "Database reset cancelled by user"
            return 0
        fi
    fi

    # Create backup
    local backup_file
    backup_file=$(create_backup)

    # Reset process
    log_info "Step 1: Downgrading to base..."
    if ! alembic downgrade base; then
        log_error "Failed to downgrade to base"
        return 1
    fi

    log_info "Step 2: Upgrading to head..."
    if ! alembic upgrade head; then
        log_error "Failed to upgrade to head"
        log_info "Database may be in inconsistent state!"
        if [ -n "$backup_file" ] && [ -f "$backup_file" ]; then
            log_info "Restore from backup: bash $SCRIPT_DIR/backup_restore.sh restore $backup_file"
        fi
        return 1
    fi

    log_success "Database reset completed successfully"

    # Validate after reset
    validate_database

    return 0
}

# Main function
main() {
    local command=${1:-}
    local target=${2:-}

    case "$command" in
        "current")
            show_current
            ;;
        "history")
            show_history
            ;;
        "upgrade")
            upgrade_database "$target"
            ;;
        "downgrade")
            downgrade_database "$target"
            ;;
        "revision")
            create_revision "$target"
            ;;
        "autogenerate")
            autogenerate_migration "$target"
            ;;
        "validate")
            validate_database
            ;;
        "stamp")
            stamp_database "$target"
            ;;
        "reset")
            reset_database
            ;;
        "help"|"-h"|"--help"|"")
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
