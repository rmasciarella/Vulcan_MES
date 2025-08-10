#!/usr/bin/env bash
# Health check script for development environment
set -e

echo "Running health checks..."

# Check if database connection works
echo "Checking database connection..."
if python app/backend_pre_start.py; then
    echo "✓ Database connection successful"
else
    echo "✗ Database connection failed"
    exit 1
fi

# Check if API is responding (if running)
echo "Checking API health endpoint..."
if curl -f http://localhost:8000/api/v1/utils/health-check/ > /dev/null 2>&1; then
    echo "✓ API health check successful"
else
    echo "⚠ API not running or health check failed"
fi

echo "Health checks completed."
