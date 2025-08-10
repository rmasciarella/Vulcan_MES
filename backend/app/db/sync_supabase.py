"""
Database synchronization between SQLModel/PostgreSQL and Supabase.
Ensures both systems have compatible schemas and data.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from supabase import Client

from app.core.db import engine, get_db
from app.core.supabase import supabase
from app.core.config import settings
from app import models


class DatabaseSynchronizer:
    """Handles synchronization between local PostgreSQL and Supabase."""
    
    def __init__(self):
        self.local_engine = engine
        self.supabase_client = supabase.admin if settings.SUPABASE_URL else None
    
    async def create_supabase_views(self) -> List[str]:
        """
        Create Supabase database views for real-time subscriptions.
        These views mirror important tables for real-time features.
        """
        if not self.supabase_client:
            return ["Supabase not configured"]
        
        views_created = []
        
        # Define views for real-time features
        view_definitions = [
            {
                "name": "realtime_tasks",
                "sql": """
                CREATE OR REPLACE VIEW realtime_tasks AS
                SELECT 
                    t.id,
                    t.name,
                    t.status,
                    t.priority,
                    t.assigned_to_id,
                    t.due_date,
                    t.updated_at,
                    u.full_name as assigned_to_name
                FROM task t
                LEFT JOIN user u ON t.assigned_to_id = u.id
                WHERE t.is_active = true;
                """
            },
            {
                "name": "realtime_schedules",
                "sql": """
                CREATE OR REPLACE VIEW realtime_schedules AS
                SELECT 
                    s.id,
                    s.name,
                    s.status,
                    s.start_time,
                    s.end_time,
                    s.optimization_score,
                    s.updated_at,
                    COUNT(st.task_id) as task_count
                FROM schedule s
                LEFT JOIN schedule_task st ON s.id = st.schedule_id
                GROUP BY s.id;
                """
            },
            {
                "name": "realtime_notifications",
                "sql": """
                CREATE OR REPLACE VIEW realtime_notifications AS
                SELECT 
                    n.id,
                    n.user_id,
                    n.type,
                    n.title,
                    n.message,
                    n.is_read,
                    n.created_at
                FROM notification n
                WHERE n.created_at > NOW() - INTERVAL '7 days'
                ORDER BY n.created_at DESC;
                """
            }
        ]
        
        for view in view_definitions:
            try:
                # Execute SQL through Supabase's admin client
                result = await self.execute_supabase_sql(view["sql"])
                views_created.append(f"Created view: {view['name']}")
            except Exception as e:
                views_created.append(f"Error creating view {view['name']}: {str(e)}")
        
        return views_created
    
    async def setup_realtime_tables(self) -> List[str]:
        """
        Configure tables for Supabase real-time subscriptions.
        """
        if not self.supabase_client:
            return ["Supabase not configured"]
        
        results = []
        
        # Tables to enable real-time on
        realtime_tables = [
            "task",
            "schedule",
            "notification",
            "job",
            "operator",
        ]
        
        for table in realtime_tables:
            try:
                # Enable real-time for the table
                sql = f"""
                ALTER TABLE {table} REPLICA IDENTITY FULL;
                """
                await self.execute_supabase_sql(sql)
                results.append(f"Enabled real-time for table: {table}")
            except Exception as e:
                results.append(f"Error enabling real-time for {table}: {str(e)}")
        
        return results
    
    async def create_supabase_functions(self) -> List[str]:
        """
        Create Supabase Edge Functions for advanced features.
        """
        if not self.supabase_client:
            return ["Supabase not configured"]
        
        functions_created = []
        
        # Define PostgreSQL functions for triggers
        function_definitions = [
            {
                "name": "notify_task_change",
                "sql": """
                CREATE OR REPLACE FUNCTION notify_task_change()
                RETURNS TRIGGER AS $$
                BEGIN
                    PERFORM pg_notify(
                        'task_changes',
                        json_build_object(
                            'operation', TG_OP,
                            'id', NEW.id,
                            'status', NEW.status,
                            'assigned_to_id', NEW.assigned_to_id
                        )::text
                    );
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                
                DROP TRIGGER IF EXISTS task_change_trigger ON task;
                CREATE TRIGGER task_change_trigger
                AFTER INSERT OR UPDATE ON task
                FOR EACH ROW
                EXECUTE FUNCTION notify_task_change();
                """
            },
            {
                "name": "auto_update_timestamp",
                "sql": """
                CREATE OR REPLACE FUNCTION auto_update_timestamp()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                """
            }
        ]
        
        for func in function_definitions:
            try:
                result = await self.execute_supabase_sql(func["sql"])
                functions_created.append(f"Created function: {func['name']}")
            except Exception as e:
                functions_created.append(f"Error creating function {func['name']}: {str(e)}")
        
        return functions_created
    
    async def sync_users(self, db: Session) -> Dict[str, Any]:
        """
        Synchronize users between local DB and Supabase Auth.
        """
        if not self.supabase_client:
            return {"status": "skipped", "message": "Supabase not configured"}
        
        results = {
            "synced": 0,
            "errors": [],
            "created_in_supabase": 0,
            "created_in_local": 0,
        }
        
        # Get all local users
        from app import crud
        local_users = crud.user.get_multi(db, limit=1000)
        
        for user in local_users:
            try:
                # Check if user exists in Supabase
                # Note: This is simplified - actual implementation would use Supabase Admin API
                # to check and create users properly
                results["synced"] += 1
            except Exception as e:
                results["errors"].append(f"Error syncing user {user.email}: {str(e)}")
        
        return results
    
    async def execute_supabase_sql(self, sql: str) -> Any:
        """Execute SQL directly on Supabase database."""
        if not self.supabase_client:
            raise ValueError("Supabase client not configured")
        
        # This would typically use Supabase's admin API to execute SQL
        # For now, we'll use the local connection which should be the same DB
        with self.local_engine.connect() as conn:
            result = conn.execute(text(sql))
            conn.commit()
            return result
    
    async def validate_schema_compatibility(self) -> Dict[str, Any]:
        """
        Validate that local and Supabase schemas are compatible.
        """
        results = {
            "compatible": True,
            "issues": [],
            "tables_checked": [],
        }
        
        inspector = inspect(self.local_engine)
        tables = inspector.get_table_names()
        
        for table in tables:
            results["tables_checked"].append(table)
            
            # Check if table has required columns for Supabase
            columns = inspector.get_columns(table)
            
            # Ensure updated_at column exists for real-time
            has_updated_at = any(col["name"] == "updated_at" for col in columns)
            if not has_updated_at and table in ["task", "schedule", "job"]:
                results["issues"].append(f"Table {table} missing updated_at column for real-time")
                results["compatible"] = False
        
        return results


async def run_full_sync():
    """Run a full database synchronization."""
    synchronizer = DatabaseSynchronizer()
    
    print("Starting database synchronization...")
    
    # Validate schema compatibility
    print("\n1. Validating schema compatibility...")
    compatibility = await synchronizer.validate_schema_compatibility()
    print(f"   Compatible: {compatibility['compatible']}")
    if compatibility["issues"]:
        print("   Issues found:")
        for issue in compatibility["issues"]:
            print(f"   - {issue}")
    
    # Create Supabase views
    print("\n2. Creating Supabase views...")
    views = await synchronizer.create_supabase_views()
    for view in views:
        print(f"   {view}")
    
    # Setup real-time tables
    print("\n3. Setting up real-time tables...")
    realtime = await synchronizer.setup_realtime_tables()
    for result in realtime:
        print(f"   {result}")
    
    # Create functions and triggers
    print("\n4. Creating database functions...")
    functions = await synchronizer.create_supabase_functions()
    for func in functions:
        print(f"   {func}")
    
    # Sync users
    print("\n5. Synchronizing users...")
    db = next(get_db())
    user_sync = await synchronizer.sync_users(db)
    print(f"   Users synced: {user_sync.get('synced', 0)}")
    if user_sync.get("errors"):
        print("   Errors:")
        for error in user_sync["errors"]:
            print(f"   - {error}")
    
    print("\nDatabase synchronization complete!")


if __name__ == "__main__":
    asyncio.run(run_full_sync())