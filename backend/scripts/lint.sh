#!/usr/bin/env bash
# Run code quality checks with mypy and ruff
set -e
set -x

echo "Running code quality checks..."

echo "Running type checking with mypy..."
mypy app

echo "Running linting with ruff..."
ruff check app

echo "Checking code formatting with ruff..."
ruff format app --check

echo "All code quality checks passed successfully."
