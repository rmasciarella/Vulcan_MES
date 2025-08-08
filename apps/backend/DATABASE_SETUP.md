# Database Setup and Initialization Guide

This guide covers the comprehensive database initialization and setup scripts for the Vulcan Engine project.

## Overview

The database setup system provides a complete solution for:
- Database initialization for different environments
- Schema migration management with Alembic
- Backup and restore procedures
- Health monitoring and verification
- Sample data loading for development

## Quick Start

### Development Environment
```bash
# Load development configuration
source scripts/env/dev.sh

# Setup development database with sample data
source scripts/env/dev.sh setup

# Or run directly
./scripts/init_db.sh
```

### Staging Environment
```bash
# Load staging configuration
source scripts/env/staging.sh

# Validate environment
source scripts/env/staging.sh validate

# Deploy to staging
source scripts/env/staging.sh deploy
```

### Production Environment
```bash
# Load production configuration (with strict validation)
source scripts/env/production.sh

# Validate production environment (MANDATORY)
source scripts/env/production.sh validate

# Deploy to production (requires confirmation)
source scripts/env/production.sh deploy
```

## Core Scripts

### 1. `init_db.sh` - Master Database Initialization

Complete database setup script that handles:
- Database connectivity verification
- Schema initialization via Alembic migrations
- Initial data loading
- Sample data loading (configurable)
- Health verification

**Usage:**
```bash
./scripts/init_db.sh

# With configuration
FORCE_RESET=true LOAD_SAMPLE_DATA=true ./scripts/init_db.sh
```

**Configuration Options:**
- `FORCE_RESET=true/false` - Force reset existing database
- `SKIP_SAMPLE_DATA=true/false` - Skip loading sample data
- `BACKUP_BEFORE_INIT=true/false` - Create backup before initialization
- `ENVIRONMENT=local/staging/production` - Target environment

### 2. `migrate.sh` - Safe Migration Management

Alembic migration wrapper with backup and validation:

```bash
# Show current migration status
./scripts/migrate.sh current

# Upgrade to latest
./scripts/migrate.sh upgrade head

# Downgrade (with backup)
./scripts/migrate.sh downgrade -1

# Create new migration
./scripts/migrate.sh revision "Add new table"

# Auto-generate migration
./scripts/migrate.sh autogenerate "Auto migration"

# Validate database state
./scripts/migrate.sh validate

# Reset database (DESTRUCTIVE)
./scripts/migrate.sh reset
```

### 3. `setup_dev_data.sh` - Development Data Management

Loads sample data from schema.sql:

```bash
# Load sample data
./scripts/setup_dev_data.sh

# Force reload
FORCE_RELOAD=true ./scripts/setup_dev_data.sh

# Clear existing data first
CLEAR_EXISTING=true ./scripts/setup_dev_data.sh
```

### 4. `backup_restore.sh` - Backup Management

Comprehensive backup and restore system:

```bash
# Create backup
./scripts/backup_restore.sh backup production_backup_20241201

# List backups
./scripts/backup_restore.sh list

# Restore backup
./scripts/backup_restore.sh restore production_backup_20241201

# Verify backup integrity
./scripts/backup_restore.sh verify production_backup_20241201

# Cleanup old backups
./scripts/backup_restore.sh cleanup

# Setup automated backups
./scripts/backup_restore.sh schedule
```

**Backup Configuration:**
- `BACKUP_DIR=./backups` - Backup directory
- `COMPRESS_BACKUPS=true/false` - Enable compression
- `ENCRYPT_BACKUPS=true/false` - Enable encryption
- `ENCRYPTION_KEY=key` - Encryption key (required if encryption enabled)
- `BACKUP_RETENTION_DAYS=30` - Days to keep backups
- `REMOTE_BACKUP_ENABLED=true/false` - Enable remote backup

### 5. Database Health Check

Monitor database health and performance:

```bash
# Full health check
python3 app/core/db_health.py

# Specific check
python3 app/core/db_health.py --check connectivity

# JSON output
python3 app/core/db_health.py --json

# Exit with status code
python3 app/core/db_health.py --exit-code
```

## Environment-Specific Scripts

### Development (`scripts/env/dev.sh`)

Optimized for local development:
- Sample data loading enabled
- Fast setup and reset
- Minimal backup requirements
- Health checks enabled

**Commands:**
```bash
source scripts/env/dev.sh setup      # Setup dev database
source scripts/env/dev.sh reset      # Reset dev database
source scripts/env/dev.sh reload-data # Reload sample data
source scripts/env/dev.sh start      # Start database (Docker)
source scripts/env/dev.sh status     # Show status
source scripts/env/dev.sh test       # Run tests
```

### Staging (`scripts/env/staging.sh`)

Balanced configuration for staging:
- Sample data for testing
- Backup before operations
- Encrypted backups
- Remote backup support
- Health monitoring

**Commands:**
```bash
source scripts/env/staging.sh validate  # Validate environment
source scripts/env/staging.sh deploy    # Deploy to staging
source scripts/env/staging.sh monitor   # Start monitoring
source scripts/env/staging.sh backup    # Create backup
source scripts/env/staging.sh migrate   # Run migrations
source scripts/env/staging.sh cleanup   # Clean up resources
```

### Production (`scripts/env/production.sh`)

Maximum security and safety:
- No sample data
- Mandatory backups
- Encrypted backups
- Remote backup required
- Operation confirmations
- Audit logging
- Strict validation

**Commands:**
```bash
source scripts/env/production.sh validate  # Validate environment
source scripts/env/production.sh deploy    # Deploy (requires confirmation)
source scripts/env/production.sh migrate   # Migrate (requires confirmation)
source scripts/env/production.sh backup    # Emergency backup
source scripts/env/production.sh monitor   # Start monitoring
source scripts/env/production.sh status    # Show status with audit logs
```

## Schema Management

### Converting Existing Schema

The system can convert the existing `schema.sql` to Alembic migrations:

```bash
# Convert schema.sql to migration
python3 app/infrastructure/database/schema_to_migration.py
```

This creates an initial migration that recreates the entire schema including:
- Custom types (enums)
- Tables with constraints
- Indexes
- Functions and triggers
- Views

### Migration Workflow

1. **Development:**
   ```bash
   # Make model changes
   # Generate migration
   ./scripts/migrate.sh autogenerate "Add user roles"

   # Review generated migration file
   # Apply migration
   ./scripts/migrate.sh upgrade head
   ```

2. **Staging:**
   ```bash
   # Deploy migrations to staging
   source scripts/env/staging.sh
   source scripts/env/staging.sh migrate
   ```

3. **Production:**
   ```bash
   # Deploy migrations to production (with confirmations)
   source scripts/env/production.sh
   source scripts/env/production.sh validate
   source scripts/env/production.sh migrate
   ```

## Docker Integration

The database setup integrates with the existing Docker Compose setup:

### Development with Docker Compose
```bash
# Start database service
docker-compose up -d db

# Run initialization
docker-compose exec backend ./scripts/init_db.sh

# Or use the prestart service
docker-compose up prestart
```

### Environment Variables in Docker

Add to your `.env` file:
```env
# Database setup configuration
USE_COMPREHENSIVE_INIT=true
LOAD_SAMPLE_DATA=true
SKIP_HEALTH_CHECK=false
BACKUP_BEFORE_START=false

# Backup configuration
BACKUP_DIR=/app/backups
COMPRESS_BACKUPS=true
ENCRYPT_BACKUPS=true
ENCRYPTION_KEY=your-encryption-key-here
BACKUP_RETENTION_DAYS=30
```

## Monitoring and Health Checks

### Continuous Monitoring

```bash
# Start monitoring (development)
source scripts/env/dev.sh
# Background monitoring available in dev environment

# Start monitoring (staging)
source scripts/env/staging.sh monitor

# Start monitoring (production)
source scripts/env/production.sh monitor
```

### Health Check Endpoints

The health check system provides:
- **Connectivity**: Database connection test
- **Schema Integrity**: Table existence and structure
- **Data Consistency**: Referential integrity checks
- **Performance**: Query performance metrics
- **Migration Status**: Alembic migration state

### Automated Backups

Set up automated daily backups:

```bash
# Generate cron entry
./scripts/backup_restore.sh schedule

# Example cron entry (daily at 2 AM)
0 2 * * * cd /app/backend && ./scripts/backup_restore.sh backup auto_backup_$(date +\%Y\%m\%d) && ./scripts/backup_restore.sh cleanup
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed:**
   ```bash
   # Check database status
   python3 app/backend_pre_start.py

   # Verify configuration
   python3 -c "from app.core.config import settings; print(settings.SQLALCHEMY_DATABASE_URI)"
   ```

2. **Migration Conflicts:**
   ```bash
   # Check current status
   ./scripts/migrate.sh current

   # Show migration history
   ./scripts/migrate.sh history

   # Manual resolution may be needed
   ```

3. **Backup/Restore Issues:**
   ```bash
   # Verify backup integrity
   ./scripts/backup_restore.sh verify backup_name

   # Check available space
   df -h ./backups
   ```

4. **Health Check Failures:**
   ```bash
   # Run specific health check
   python3 app/core/db_health.py --check connectivity

   # Get detailed JSON output
   python3 app/core/db_health.py --json
   ```

### Recovery Procedures

1. **Development Database Reset:**
   ```bash
   source scripts/env/dev.sh reset
   ```

2. **Staging Recovery:**
   ```bash
   source scripts/env/staging.sh
   # Find latest backup
   ./scripts/backup_restore.sh list
   # Restore
   ./scripts/backup_restore.sh restore backup_name
   ```

3. **Production Emergency Recovery:**
   ```bash
   source scripts/env/production.sh
   # Create emergency backup first
   source scripts/env/production.sh backup
   # Restore from known good backup
   ./scripts/backup_restore.sh restore backup_name
   ```

## Security Considerations

### Development
- No encryption required
- Sample data includes test credentials
- Local database connections

### Staging
- Encrypted backups recommended
- Remote backup storage
- Limited sample data

### Production
- **MANDATORY** encrypted backups
- **MANDATORY** remote backup storage
- **NO** sample data
- Operation confirmations required
- Full audit logging
- Strict environment validation

## File Structure

```
backend/
├── scripts/
│   ├── init_db.sh              # Master initialization script
│   ├── migrate.sh              # Migration management
│   ├── setup_dev_data.sh       # Development data loader
│   ├── backup_restore.sh       # Backup management
│   ├── prestart.sh             # Enhanced prestart script
│   └── env/                    # Environment-specific configurations
│       ├── dev.sh              # Development environment
│       ├── staging.sh          # Staging environment
│       └── production.sh       # Production environment
├── app/
│   ├── core/
│   │   └── db_health.py        # Health monitoring system
│   └── infrastructure/
│       └── database/
│           ├── schema.sql      # Original schema definition
│           └── schema_to_migration.py  # Schema converter
└── DATABASE_SETUP.md          # This documentation
```

## Best Practices

1. **Always validate environment before operations**
2. **Create backups before destructive operations**
3. **Test migrations in development first**
4. **Monitor health after deployments**
5. **Use environment-specific scripts**
6. **Keep audit logs in production**
7. **Verify backups regularly**
8. **Use encrypted backups for sensitive environments**

## Support

For issues or questions:
1. Check the troubleshooting section
2. Run health checks for diagnostics
3. Review audit logs (production)
4. Check backup integrity
5. Validate environment configuration
