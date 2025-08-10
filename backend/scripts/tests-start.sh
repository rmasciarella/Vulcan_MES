#!/usr/bin/env bash
# Start tests with database preparation
set -e
set -x

echo "Preparing test environment..."
python app/tests_pre_start.py

echo "Running test suite..."
bash scripts/test.sh "$@"
