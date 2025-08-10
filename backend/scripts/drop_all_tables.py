#!/usr/bin/env python3
"""Drop all tables in the database - USE WITH CAUTION!"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, MetaData
from app.core.config import settings

def drop_all_tables():
    """Drop all tables in the database including alembic_version"""
    
    # Create engine
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            # Drop all tables in public schema
            conn.execute(text("""
                DO $$ 
                DECLARE 
                    r RECORD;
                BEGIN
                    -- Drop all tables
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
                    LOOP
                        EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                        RAISE NOTICE 'Dropped table: %', r.tablename;
                    END LOOP;
                    
                    -- Drop all sequences
                    FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public')
                    LOOP
                        EXECUTE 'DROP SEQUENCE IF EXISTS public.' || quote_ident(r.sequence_name) || ' CASCADE';
                        RAISE NOTICE 'Dropped sequence: %', r.sequence_name;
                    END LOOP;
                    
                    -- Drop all types
                    FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'public' AND t.typtype = 'e')
                    LOOP
                        EXECUTE 'DROP TYPE IF EXISTS public.' || quote_ident(r.typname) || ' CASCADE';
                        RAISE NOTICE 'Dropped type: %', r.typname;
                    END LOOP;
                END $$;
            """))
            
            trans.commit()
            print("✅ Successfully dropped all tables, sequences, and types")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Error dropping tables: {e}")
            raise

if __name__ == "__main__":
    response = input("⚠️  WARNING: This will DROP ALL TABLES in the database. Are you sure? (type 'yes' to confirm): ")
    if response.lower() == 'yes':
        drop_all_tables()
    else:
        print("Aborted.")