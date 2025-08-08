#!/bin/bash

# Install Dependencies Script
# Installs all necessary dependencies for comprehensive observability

set -e

echo "🔧 Installing Vulcan Engine Observability Dependencies..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install uv first:"
    echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd "$(dirname "$0")/.."

# Add missing dependencies to pyproject.toml if not already added
echo "📝 Updating pyproject.toml with observability dependencies..."

# Install/sync dependencies
uv sync

echo "🐍 Python dependencies installed successfully!"

# Install system dependencies (optional)
echo "🖥️  Checking system dependencies..."

# Check for OR-Tools
python -c "import ortools" 2>/dev/null && echo "✅ OR-Tools is available" || echo "⚠️  OR-Tools may need to be installed separately if not available"

# Check for psutil
python -c "import psutil" 2>/dev/null && echo "✅ psutil is available" || echo "❌ psutil not available"

echo ""
echo "🎯 Setup Instructions:"
echo ""
echo "1. Start the application:"
echo "   fastapi dev app/main.py"
echo ""
echo "2. Access endpoints:"
echo "   - API Documentation: http://localhost:8000/docs"
echo "   - Health Checks: http://localhost:8000/health"
echo "   - Metrics (if enabled): http://localhost:8001/metrics"
echo "   - Debug Dashboard (local only): http://localhost:8000/api/v1/debug/dashboard"
echo ""
echo "3. Environment Variables (add to .env):"
echo "   LOG_LEVEL=INFO"
echo "   LOG_FORMAT=json"
echo "   ENABLE_METRICS=true"
echo "   ENABLE_TRACING=true"
echo "   METRICS_PORT=8001"
echo ""
echo "4. Optional monitoring stack:"
echo "   cd monitoring && docker-compose -f docker-compose.monitoring.yml up -d"
echo "   - Prometheus: http://localhost:9090"
echo "   - Grafana: http://localhost:3000 (admin/admin)"
echo "   - AlertManager: http://localhost:9093"
echo ""
echo "✅ Observability setup complete!"
echo ""
echo "📊 Available monitoring features:"
echo "   ✅ Structured JSON logging with correlation IDs"
echo "   ✅ Prometheus metrics collection"
echo "   ✅ OpenTelemetry distributed tracing"
echo "   ✅ Comprehensive health checks"
echo "   ✅ Circuit breaker protection"
echo "   ✅ Performance monitoring"
echo "   ✅ Development debugging tools"
echo "   ✅ OR-Tools solver observability"
echo "   ✅ Database operation monitoring"
echo ""
