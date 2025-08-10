#!/usr/bin/env bash
# Reset database and seed with initial data
set -e
set -x

echo "Resetting database and seeding with initial data..."

# Drop all tables and recreate
echo "Dropping and recreating database schema..."
alembic downgrade base
alembic upgrade head

# Create initial data
echo "Seeding database with initial data..."
python app/initial_data.py

echo "Database reset and seeding completed successfully."
