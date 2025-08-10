#!/usr/bin/env bash
# Database backup and restore procedures
set -e

# Color output functions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
BACKUP_DIR=${BACKUP_DIR:-"./backups"}
COMPRESS_BACKUPS=${COMPRESS_BACKUPS:-true}
ENCRYPT_BACKUPS=${ENCRYPT_BACKUPS:-false}
ENCRYPTION_KEY=${ENCRYPTION_KEY:-""}
BACKUP_RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

show_usage() {
    echo "Usage: $0 <command> [options]"
    echo "Commands: backup, restore, list, cleanup, verify, schedule"
}

get_db_params() {
    python3 -c "
from app.core.config import settings
from urllib.parse import urlparse
import os
try:
    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')
    parsed = urlparse(db_url)
    os.environ['PGHOST'] = parsed.hostname or 'localhost'
    os.environ['PGPORT'] = str(parsed.port or 5432)
    os.environ['PGUSER'] = parsed.username or 'postgres'
    os.environ['PGPASSWORD'] = parsed.password or ''
    os.environ['PGDATABASE'] = parsed.path.lstrip('/') or 'postgres'
    print('PGHOST=' + os.environ['PGHOST'])
    print('PGPORT=' + os.environ['PGPORT'])
    print('PGUSER=' + os.environ['PGUSER'])
    print('PGDATABASE=' + os.environ['PGDATABASE'])
except Exception as e:
    print('Error: ' + str(e))
    exit(1)
"
}

ensure_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        log_info "Creating backup directory: $BACKUP_DIR"
        mkdir -p "$BACKUP_DIR"
    fi
}

create_backup() {
    local backup_name=${1:-"database_backup_$(date +%Y%m%d_%H%M%S)"}
    local backup_path="$BACKUP_DIR/$backup_name"

    log_info "Starting database backup: $backup_name"
    ensure_backup_dir

    eval $(get_db_params)
    if [ $? -ne 0 ]; then
        log_error "Failed to get database connection parameters"
        return 1
    fi

    local backup_cmd="pg_dump --verbose --no-password --format=custom --no-owner --no-acl --create --clean --if-exists"

    if [ "$COMPRESS_BACKUPS" = "true" ] && [ "$ENCRYPT_BACKUPS" = "true" ]; then
        if [ -z "$ENCRYPTION_KEY" ]; then
            log_error "ENCRYPTION_KEY required when ENCRYPT_BACKUPS=true"
            return 1
        fi
        log_info "Creating compressed and encrypted backup..."
        $backup_cmd "$PGDATABASE" | gzip | openssl enc -aes-256-cbc -salt -k "$ENCRYPTION_KEY" > "$backup_path"
    elif [ "$COMPRESS_BACKUPS" = "true" ]; then
        log_info "Creating compressed backup..."
        $backup_cmd "$PGDATABASE" | gzip > "$backup_path"
    elif [ "$ENCRYPT_BACKUPS" = "true" ]; then
        if [ -z "$ENCRYPTION_KEY" ]; then
            log_error "ENCRYPTION_KEY required when ENCRYPT_BACKUPS=true"
            return 1
        fi
        log_info "Creating encrypted backup..."
        $backup_cmd "$PGDATABASE" | openssl enc -aes-256-cbc -salt -k "$ENCRYPTION_KEY" > "$backup_path"
    else
        log_info "Creating plain backup..."
        $backup_cmd "$PGDATABASE" -f "$backup_path"
    fi

    if [ $? -eq 0 ] && [ -f "$backup_path" ]; then
        local backup_size=$(ls -lh "$backup_path" | awk '{print $5}')
        log_success "Backup created successfully: $backup_path ($backup_size)"
        return 0
    else
        log_error "Backup failed"
        return 1
    fi
}

restore_backup() {
    local backup_name=${1:-""}
    if [ -z "$backup_name" ]; then
        log_error "Backup filename is required"
        return 1
    fi

    local backup_path="$BACKUP_DIR/$backup_name"
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file not found: $backup_path"
        return 1
    fi

    log_warning "Starting database restore from: $backup_name"
    log_warning "This will OVERWRITE the current database!"

    if [ -t 0 ] && [ -z "$CI" ]; then
        echo -n "Are you sure you want to restore? [y/N]: "
        read -r confirmation
        if [[ ! "$confirmation" =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled by user"
            return 0
        fi
    fi

    eval $(get_db_params)

    local restore_cmd=""
    if [[ "$backup_name" == *.enc ]]; then
        if [ -z "$ENCRYPTION_KEY" ]; then
            log_error "ENCRYPTION_KEY required to restore encrypted backup"
            return 1
        fi
        if [[ "$backup_name" == *.gz.enc ]]; then
            restore_cmd="openssl enc -aes-256-cbc -d -k '$ENCRYPTION_KEY' < '$backup_path' | gunzip | psql --quiet"
        else
            restore_cmd="openssl enc -aes-256-cbc -d -k '$ENCRYPTION_KEY' < '$backup_path' | psql --quiet"
        fi
    elif [[ "$backup_name" == *.gz ]]; then
        restore_cmd="gunzip -c '$backup_path' | psql --quiet"
    else
        restore_cmd="psql --quiet -f '$backup_path'"
    fi

    if eval "$restore_cmd"; then
        log_success "Database restore completed successfully"
        return 0
    else
        log_error "Database restore failed"
        return 1
    fi
}

list_backups() {
    ensure_backup_dir
    log_info "Available backups in $BACKUP_DIR:"

    if [ ! "$(ls -A "$BACKUP_DIR")" ]; then
        echo "No backups found"
        return 0
    fi

    echo ""
    echo "Name                                    Size        Date                 Type"
    echo "------------------------------------------------------------------------"

    for backup in "$BACKUP_DIR"/*.sql* "$BACKUP_DIR"/*.enc; do
        if [ -f "$backup" ]; then
            local basename=$(basename "$backup")
            local size=$(ls -lh "$backup" | awk '{print $5}')
            local date=$(ls -l "$backup" | awk '{print $6, $7, $8}')
            local type="plain"

            if [[ "$basename" == *.gz* ]]; then
                type="compressed"
            fi
            if [[ "$basename" == *.enc ]]; then
                type="${type}+encrypted"
            fi

            printf "%-40s %-10s %-18s %s\n" "$basename" "$size" "$date" "$type"
        fi
    done
    echo ""
}

cleanup_backups() {
    ensure_backup_dir
    log_info "Cleaning up backups older than $BACKUP_RETENTION_DAYS days..."

    local deleted_count=0
    while IFS= read -r -d '' backup; do
        local basename=$(basename "$backup")
        log_info "Removing old backup: $basename"
        rm -f "$backup"
        deleted_count=$((deleted_count + 1))
    done < <(find "$BACKUP_DIR" -name "*.sql*" -o -name "*.enc" -type f -mtime +$BACKUP_RETENTION_DAYS -print0)

    if [ $deleted_count -gt 0 ]; then
        log_success "Cleaned up $deleted_count old backups"
    else
        log_info "No old backups to clean up"
    fi
}

verify_backup() {
    local backup_name=${1:-""}
    if [ -z "$backup_name" ]; then
        log_error "Backup filename is required"
        return 1
    fi

    local backup_path="$BACKUP_DIR/$backup_name"
    if [ ! -f "$backup_path" ]; then
        log_error "Backup file not found: $backup_path"
        return 1
    fi

    log_info "Verifying backup integrity: $backup_name"

    if [ ! -s "$backup_path" ]; then
        log_error "Backup file is empty"
        return 1
    fi

    if [[ "$backup_name" == *.gz* ]]; then
        log_info "Verifying gzip compression..."
        if ! gunzip -t "$backup_path" 2>/dev/null; then
            log_error "Backup file is corrupted - gzip test failed"
            return 1
        fi
    fi

    log_success "Backup integrity verification passed"
    return 0
}

setup_backup_schedule() {
    log_info "Setting up automated backup schedule..."
    log_info "Suggested cron entry for daily 2AM backups:"
    echo "0 2 * * * cd /path/to/backend && ./scripts/backup_restore.sh backup && ./scripts/backup_restore.sh cleanup"
    echo ""
    log_info "To install, add this line to crontab manually"
}

main() {
    local command=${1:-}
    local arg=${2:-}

    case "$command" in
        "backup") create_backup "$arg" ;;
        "restore") restore_backup "$arg" ;;
        "list") list_backups ;;
        "cleanup") cleanup_backups ;;
        "verify") verify_backup "$arg" ;;
        "schedule") setup_backup_schedule ;;
        "help"|"-h"|"--help"|"") show_usage; exit 0 ;;
        *) log_error "Unknown command: $command"; show_usage; exit 1 ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
