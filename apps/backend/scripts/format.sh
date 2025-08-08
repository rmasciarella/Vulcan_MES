#!/usr/bin/env bash
# Format code using ruff
set -e
set -x

echo "Formatting code with ruff..."
ruff check app scripts --fix
ruff format app scripts
echo "Code formatting completed successfully."
