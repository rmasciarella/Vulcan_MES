#!/usr/bin/env python3
"""
Import jobs from CSV data into the database.

This script reads the jobs.csv file and imports the data into the jobs table,
mapping the CSV columns to the appropriate database fields.
"""

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, create_engine

# Load environment variables from .env file
from dotenv import load_dotenv

# Find and load .env file from monorepo root
env_path = Path(__file__).parents[4] / ".env"  # Go up 4 levels to monorepo root
load_dotenv(env_path)

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from core.config import settings
from infrastructure.database.sqlmodel_entities import Job, JobStatusEnum, PriorityLevelEnum


def parse_datetime_with_timezone(dt_str: str) -> datetime:
    """Parse ISO datetime string with timezone offset to UTC datetime."""
    if not dt_str:
        return datetime.utcnow()
    
    # Handle timezone offset format like "2025-08-01T09:00:00-0500"
    if dt_str.endswith(('-0500', '-05:00')):
        # Remove timezone for parsing and treat as UTC for simplicity
        dt_str = dt_str.rsplit('-', 1)[0] if dt_str.endswith('-0500') else dt_str.rsplit('-', 1)[0]
        return datetime.fromisoformat(dt_str)
    elif dt_str.endswith(('+0500', '+05:00')):
        dt_str = dt_str.rsplit('+', 1)[0] if dt_str.endswith('+0500') else dt_str.rsplit('+', 1)[0] 
        return datetime.fromisoformat(dt_str)
    
    return datetime.fromisoformat(dt_str)


def import_jobs_from_csv(csv_file_path: str, engine):
    """Import jobs from CSV file into the database."""
    
    with Session(engine) as session:
        # Read and process CSV
        with open(csv_file_path, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            imported_count = 0
            skipped_count = 0
            
            for row_num, row in enumerate(reader, start=2):  # Start from 2 since header is row 1
                try:
                    # Extract CSV data
                    csv_job_id = row.get('job_id', '').strip()
                    description = row.get('description', '').strip()
                    due_date_str = row.get('due_date', '').strip()
                    
                    # Validate required fields
                    if not csv_job_id or not description or not due_date_str:
                        print(f"Row {row_num}: Skipping - missing required fields")
                        skipped_count += 1
                        continue
                    
                    # Check if job already exists using description as job_number
                    existing_job = session.query(Job).filter(Job.job_number == description).first()
                    if existing_job:
                        print(f"Row {row_num}: Job with number '{description}' already exists, skipping")
                        skipped_count += 1
                        continue
                    
                    # Parse due_date
                    try:
                        due_date = parse_datetime_with_timezone(due_date_str)
                    except ValueError as e:
                        print(f"Row {row_num}: Invalid due_date format '{due_date_str}': {e}")
                        skipped_count += 1
                        continue
                    
                    # Create new job
                    new_job = Job(
                        job_number=description,  # Use description as job_number (e.g., "OB3.19")
                        customer_name="Imported Customer",  # Default since not in CSV
                        part_number=f"PART-{description}",  # Generate part number
                        quantity=1,  # Default quantity
                        priority=PriorityLevelEnum.NORMAL,  # Default priority
                        status=JobStatusEnum.PLANNED,  # Default status
                        due_date=due_date,
                        notes=f"Imported from CSV - Original ID: {csv_job_id}",
                        created_by="csv_import_script"
                    )
                    
                    session.add(new_job)
                    imported_count += 1
                    
                    print(f"Row {row_num}: Imported job '{description}' with due date {due_date}")
                    
                except Exception as e:
                    print(f"Row {row_num}: Error processing row: {e}")
                    skipped_count += 1
                    continue
            
            # Commit all changes
            try:
                session.commit()
                print(f"\n✅ Import completed successfully!")
                print(f"   - Imported: {imported_count} jobs")
                print(f"   - Skipped: {skipped_count} jobs")
                
            except Exception as e:
                session.rollback()
                print(f"\n❌ Error committing to database: {e}")
                return False
    
    return True


def main():
    """Main execution function."""
    
    # CSV file path
    csv_file_path = "/Users/quanta/projects/archive2/ortool_engine/supabase_data/jobs.csv"
    
    # Verify CSV file exists
    if not Path(csv_file_path).exists():
        print(f"❌ CSV file not found: {csv_file_path}")
        return 1
    
    print(f"🔄 Starting CSV import from: {csv_file_path}")
    
    # Create database engine
    try:
        engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
        print(f"✅ Connected to database: {settings.POSTGRES_SERVER}")
        
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return 1
    
    # Import jobs
    success = import_jobs_from_csv(csv_file_path, engine)
    
    if success:
        print("\n🎉 Job import completed successfully!")
        return 0
    else:
        print("\n💥 Job import failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)