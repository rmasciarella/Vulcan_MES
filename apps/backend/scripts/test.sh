#!/usr/bin/env bash
# Run tests with coverage reporting and enforce minimum coverage
set -e
set -x

echo "Running tests with coverage reporting..."

# Run tests with coverage using pytest configuration
pytest "$@"

echo ""
echo "Coverage Summary:"
echo "================"

# Show detailed coverage report
coverage report --show-missing

echo ""
echo "Checking coverage threshold (minimum 80%)..."

# Enforce minimum coverage threshold
if ! coverage report --fail-under=80 > /dev/null 2>&1; then
    echo "❌ Coverage is below 80% threshold!"
    echo "Please add more tests to improve coverage."
    exit 1
fi

echo "✅ Coverage meets minimum threshold (80%)"
echo ""
echo "HTML coverage report available at: htmlcov/index.html"
echo "Run 'open htmlcov/index.html' to view detailed coverage report."
