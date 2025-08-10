-- Create core domain tables for Vulcan MES Manufacturing Scheduling System
-- This migration creates the fundamental tables needed for Jobs and Tasks domains
-- 
-- Based on DDD domain requirements and repository implementations:
-- - Jobs: Production orders with due dates and release constraints  
-- - Tasks: Work units bridging Jobs to TaskModes, with precedence relationships
-- - Task-TaskMode composition for multiple execution approaches

-- First, create the Jobs table (job_instances matches repository expectations)
CREATE TABLE job_instances (
    instance_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL, -- Serial number / job identifier
    description TEXT, -- Product type description
    template_id VARCHAR(50), -- Job template reference
    due_date TIMESTAMPTZ NOT NULL,
    earliest_start_date TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'ON_HOLD', 'COMPLETED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT job_instances_name_check CHECK (char_length(name) >= 1),
    CONSTRAINT job_instances_dates_check CHECK (earliest_start_date <= due_date)
);

-- Create indexes for Jobs performance
CREATE INDEX idx_job_instances_status ON job_instances(status);
CREATE INDEX idx_job_instances_due_date ON job_instances(due_date);
CREATE INDEX idx_job_instances_template_id ON job_instances(template_id);
CREATE INDEX idx_job_instances_earliest_start ON job_instances(earliest_start_date);

-- Create the main Tasks table
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES job_instances(instance_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'not_ready' CHECK (status IN ('not_ready', 'ready', 'scheduled', 'in_progress', 'completed', 'on_hold', 'cancelled')),
    is_setup_task BOOLEAN NOT NULL DEFAULT false,
    is_unattended BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT tasks_name_check CHECK (char_length(name) >= 1),
    -- Unique sequence per job
    CONSTRAINT tasks_unique_sequence_per_job UNIQUE (job_id, sequence_number)
);

-- Create indexes for Tasks performance
CREATE INDEX idx_tasks_job_id ON tasks(job_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_sequence ON tasks(job_id, sequence_number);
CREATE INDEX idx_tasks_setup_flag ON tasks(is_setup_task);
CREATE INDEX idx_tasks_attendance ON tasks(is_unattended);

-- Update the existing task_modes table to properly reference tasks
-- Add foreign key constraint that was missing
ALTER TABLE task_modes 
ADD CONSTRAINT task_modes_task_id_fkey 
FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE;

-- Create optimized_tasks table for the current repository implementation
-- This appears to be a denormalized view or optimization table
CREATE TABLE optimized_tasks (
    optimized_task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID, -- Job template reference
    name VARCHAR(100) NOT NULL,
    position INTEGER, -- Sequence position
    is_setup BOOLEAN DEFAULT false,
    is_unattended BOOLEAN DEFAULT false,
    min_operators INTEGER DEFAULT 1 CHECK (min_operators >= 0),
    max_operators INTEGER DEFAULT 1 CHECK (max_operators >= min_operators),
    department_id VARCHAR(50),
    sequence_id UUID,
    operator_efficiency_curve JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT optimized_tasks_name_check CHECK (char_length(name) >= 1)
);

-- Create indexes for optimized_tasks performance
CREATE INDEX idx_optimized_tasks_pattern_id ON optimized_tasks(pattern_id);
CREATE INDEX idx_optimized_tasks_position ON optimized_tasks(pattern_id, position);
CREATE INDEX idx_optimized_tasks_setup ON optimized_tasks(is_setup);
CREATE INDEX idx_optimized_tasks_unattended ON optimized_tasks(is_unattended);
CREATE INDEX idx_optimized_tasks_operators ON optimized_tasks(min_operators, max_operators);

-- Create update triggers for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    IF TG_TABLE_NAME = 'job_instances' OR TG_TABLE_NAME = 'tasks' THEN
        NEW.version = OLD.version + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers to all tables with updated_at
CREATE TRIGGER trigger_job_instances_updated_at
    BEFORE UPDATE ON job_instances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_tasks_updated_at
    BEFORE UPDATE ON tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_optimized_tasks_updated_at
    BEFORE UPDATE ON optimized_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add table comments for documentation
COMMENT ON TABLE job_instances IS 'Production jobs/orders with due dates and release constraints';
COMMENT ON COLUMN job_instances.instance_id IS 'Unique job instance identifier';
COMMENT ON COLUMN job_instances.name IS 'Job serial number or identifier';
COMMENT ON COLUMN job_instances.description IS 'Product type or job description';
COMMENT ON COLUMN job_instances.template_id IS 'Reference to job template defining standard tasks';
COMMENT ON COLUMN job_instances.due_date IS 'Customer due date for job completion';
COMMENT ON COLUMN job_instances.earliest_start_date IS 'Release date - earliest date job can start';
COMMENT ON COLUMN job_instances.status IS 'Current lifecycle status of the job';

COMMENT ON TABLE tasks IS 'Individual work units within production jobs';
COMMENT ON COLUMN tasks.job_id IS 'Parent job this task belongs to';
COMMENT ON COLUMN tasks.sequence_number IS 'Execution order within the job (1, 2, 3...)';
COMMENT ON COLUMN tasks.is_setup_task IS 'Whether this is a machine setup/changeover task';
COMMENT ON COLUMN tasks.is_unattended IS 'Whether task can run without operator presence';

COMMENT ON TABLE optimized_tasks IS 'Denormalized task data for performance optimization and legacy compatibility';
COMMENT ON COLUMN optimized_tasks.pattern_id IS 'Job template pattern reference';
COMMENT ON COLUMN optimized_tasks.position IS 'Task position within job sequence';
COMMENT ON COLUMN optimized_tasks.min_operators IS 'Minimum operators required';
COMMENT ON COLUMN optimized_tasks.max_operators IS 'Maximum operators that can be assigned';

-- Business rule constraints and checks
-- Ensure TaskModes have valid relationships (enforced at application level)
-- Ensure at least one TaskMode exists per Task (enforced at application level)
-- Ensure exactly one primary TaskMode per Task (enforced at application level)