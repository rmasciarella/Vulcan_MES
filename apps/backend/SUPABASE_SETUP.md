# Supabase PostgreSQL Integration Guide

This guide explains how to configure the FastAPI application to connect to Supabase PostgreSQL database instead of local PostgreSQL.

## Overview

The application has been configured to support both local PostgreSQL and Supabase PostgreSQL connections with production-ready settings including:

- Connection pooling with automatic reconnection
- SSL support for secure connections
- Database health monitoring endpoints
- Flexible configuration via environment variables

## Configuration Options

The application supports two ways to configure database connections:

### Option 1: Direct DATABASE_URL (Recommended for Supabase)

Set a single environment variable with the complete connection string:

```bash
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres
```

### Option 2: Individual Components (Traditional)

Set individual database connection parameters:

```bash
POSTGRES_SERVER=db.[project-ref].supabase.co
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-supabase-password
POSTGRES_DB=postgres
```

## Supabase Setup Instructions

### 1. Get Your Supabase Database Credentials

1. Login to your [Supabase Dashboard](https://app.supabase.com)
2. Navigate to your project
3. Go to **Settings** → **Database**
4. In the **Connection string** section, find the connection string:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
   ```

### 2. Update Environment Configuration

Update your `.env` file with Supabase settings:

```bash
# Supabase Configuration (Production/Staging)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_KEY=your-supabase-anon-key-here
USE_SSL=true

# Set environment to production for proper SSL handling
ENVIRONMENT=production
```

**Important**: Replace `[YOUR-PASSWORD]` and `[PROJECT-REF]` with your actual Supabase credentials.

### 3. Database Connection Features

The application includes several production-ready database features:

#### Connection Pooling
- **Pool Size**: 10 base connections
- **Max Overflow**: 20 additional connections
- **Pool Recycle**: Connections recycled every hour
- **Pre-ping**: Connections verified before use

#### SSL Configuration
- Automatically enabled for non-local environments
- Required for Supabase connections
- Configurable via `USE_SSL` environment variable

#### Health Monitoring
- Basic health check: `GET /api/v1/utils/health-check/`
- Detailed database status: `GET /api/v1/utils/db-status/` (requires admin)

## Testing the Connection

### 1. Health Check Endpoint

Test basic connectivity:
```bash
curl http://localhost:8000/api/v1/utils/health-check/
```

Expected response:
```json
{
  "status": "healthy",
  "database": {
    "connected": true,
    "version": "PostgreSQL 15.1 on x86_64-pc-linux-gnu...",
    "pool_info": {
      "pool_size": 10,
      "checked_in": 9,
      "checked_out": 1,
      "overflow": 0
    },
    "connection_url": "db.[project-ref].supabase.co:5432/postgres"
  },
  "version": "1.0.0"
}
```

### 2. Detailed Database Status

For administrators, get detailed database information:
```bash
curl -H "Authorization: Bearer <admin-token>" http://localhost:8000/api/v1/utils/db-status/
```

### 3. Application Startup

Start the FastAPI application:
```bash
# From backend directory
uv run fastapi dev app/main.py
```

Check the logs for successful database connection.

## Migration from Local to Supabase

### 1. Export Local Data (Optional)

If you have existing data to migrate:
```bash
pg_dump postgresql://postgres:password@localhost:5432/app > backup.sql
```

### 2. Run Migrations on Supabase

Apply database migrations to your Supabase database:
```bash
# Make sure DATABASE_URL points to Supabase
alembic upgrade head
```

### 3. Import Data (Optional)

If you exported data:
```bash
psql "postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres" < backup.sql
```

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | None | Complete database connection string (preferred for Supabase) |
| `POSTGRES_SERVER` | Yes* | localhost | Database server hostname |
| `POSTGRES_PORT` | No | 5432 | Database server port |
| `POSTGRES_USER` | Yes* | postgres | Database username |
| `POSTGRES_PASSWORD` | Yes* | | Database password |
| `POSTGRES_DB` | Yes* | app | Database name |
| `SUPABASE_URL` | No | None | Supabase project URL |
| `SUPABASE_KEY` | No | None | Supabase anon/service key |
| `USE_SSL` | No | false | Force SSL connections |
| `ENVIRONMENT` | No | local | Application environment (local/staging/production) |

*Required only if `DATABASE_URL` is not provided.

### Connection Pool Settings

The following pool settings are automatically configured:

```python
engine_kwargs = {
    "pool_pre_ping": True,      # Verify connections before use
    "pool_recycle": 3600,       # Recycle connections every hour
    "pool_size": 10,            # Base connection pool size
    "max_overflow": 20,         # Additional connections beyond pool_size
}
```

For Supabase/production environments, SSL settings are added:

```python
connect_args = {
    "sslmode": "require",       # Require SSL connection
    "connect_timeout": 10,      # Connection timeout in seconds
    "application_name": "Vulcan Engine API",  # Application identifier
}
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Verify your Supabase credentials
   - Check if your IP is allowed in Supabase settings
   - Ensure `USE_SSL=true` for Supabase connections

2. **SSL Required**
   ```
   FATAL: connection requires SSL
   ```
   - Set `USE_SSL=true` in your environment
   - Or set `ENVIRONMENT=production`

3. **Authentication Failed**
   ```
   FATAL: password authentication failed
   ```
   - Double-check your password in the connection string
   - Verify your Supabase project credentials

4. **Pool Timeout**
   - Monitor connection usage via `/db-status/` endpoint
   - Consider adjusting pool settings if needed

### Health Check Failures

If health checks fail:

1. Check application logs for detailed error messages
2. Verify environment variables are loaded correctly
3. Test direct connection with psql:
   ```bash
   psql "postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres"
   ```

### Environment Loading Issues

If configuration isn't loading properly:

1. Verify `.env` file location (should be in project root)
2. Check file permissions
3. Ensure no syntax errors in `.env` file
4. Use absolute paths in production deployments

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for all sensitive configuration
3. **Enable SSL** for all production connections
4. **Rotate passwords** regularly
5. **Monitor connection usage** via health check endpoints
6. **Use service roles** appropriately in Supabase
7. **Configure row-level security** in Supabase for additional protection

## Production Deployment

For production deployments:

1. Set `ENVIRONMENT=production`
2. Use strong passwords
3. Enable SSL with `USE_SSL=true`
4. Configure monitoring alerts on health check endpoints
5. Set up log aggregation for database connection monitoring
6. Consider using Supabase connection pooling (PgBouncer)

This configuration provides a robust, production-ready connection to Supabase PostgreSQL with proper error handling, monitoring, and security features.
