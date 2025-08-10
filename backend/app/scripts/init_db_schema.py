#!/usr/bin/env python3
"""
Initialize database schema directly using SQLModel.

This script creates all the database tables based on the SQLModel entities.
"""

import sys
from pathlib import Path

from sqlmodel import SQLModel, create_engine

# Load environment variables from .env file
from dotenv import load_dotenv

# Find and load .env file from monorepo root
env_path = Path(__file__).parents[4] / ".env"  # Go up 4 levels to monorepo root
load_dotenv(env_path)

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))

from core.config import settings
from infrastructure.database.sqlmodel_entities import *  # Import all models


def create_database_schema():
    """Create all database tables using SQLModel."""
    
    print(f"🔄 Initializing database schema...")
    print(f"   Database: {settings.POSTGRES_DB}")
    print(f"   Host: {settings.POSTGRES_SERVER}")
    
    try:
        # Create database engine
        engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), echo=True)
        
        # Create all tables
        SQLModel.metadata.create_all(engine)
        
        print(f"\n✅ Database schema created successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create database schema: {e}")
        return False


def main():
    """Main execution function."""
    
    success = create_database_schema()
    
    if success:
        print("\n🎉 Database initialization completed successfully!")
        return 0
    else:
        print("\n💥 Database initialization failed!")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)