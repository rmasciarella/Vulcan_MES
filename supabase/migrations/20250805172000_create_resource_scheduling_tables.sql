-- Create resource and scheduling tables for Vulcan MES Manufacturing Scheduling System
-- This migration creates tables for machines, operators, departments, and scheduling results
-- 
-- Based on the dual resource model:
-- - Machines grouped into WorkCells for spatial capacity constraints
-- - Operators grouped by Departments for skill-based assignment

-- Create departments table (groups operators by skills)
CREATE TABLE departments (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create operators table
CREATE TABLE operators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    department_id VARCHAR(50) NOT NULL REFERENCES departments(id),
    skill_level VARCHAR(20) NOT NULL CHECK (skill_level IN ('novice', 'competent', 'proficient', 'expert')),
    is_available BOOLEAN NOT NULL DEFAULT true,
    hourly_rate DECIMAL(10, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT operators_name_check CHECK (char_length(name) >= 1),
    CONSTRAINT operators_hourly_rate_check CHECK (hourly_rate IS NULL OR hourly_rate > 0)
);

-- Create workcells table (groups machines with capacity constraints)
CREATE TABLE workcells (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    max_concurrent_tasks INTEGER NOT NULL DEFAULT 1 CHECK (max_concurrent_tasks >= 1),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create machines table
CREATE TABLE machines (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    workcell_id VARCHAR(50) NOT NULL REFERENCES workcells(id),
    machine_type VARCHAR(50),
    is_active BOOLEAN NOT NULL DEFAULT true,
    capabilities JSONB DEFAULT '[]'::jsonb,
    maintenance_schedule JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT machines_name_check CHECK (char_length(name) >= 1)
);

-- Create solved_schedules table (optimization results)
CREATE TABLE solved_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'optimizing', 'completed', 'failed', 'published')),
    solver_type VARCHAR(50),
    objective_function VARCHAR(50),
    optimization_params JSONB,
    solver_statistics JSONB,
    total_makespan INTEGER, -- Total time in minutes
    total_cost DECIMAL(12, 2),
    resource_utilization JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    created_by UUID,
    
    -- Constraints
    CONSTRAINT solved_schedules_name_check CHECK (char_length(schedule_name) >= 1)
);

-- Create scheduled_tasks table (task assignments in a schedule)
CREATE TABLE scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES solved_schedules(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id),
    task_mode_id UUID NOT NULL REFERENCES task_modes(id),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    assigned_machines TEXT[] NOT NULL DEFAULT '{}',
    assigned_operators UUID[] NOT NULL DEFAULT '{}',
    assigned_workcells TEXT[] NOT NULL DEFAULT '{}',
    is_critical_path BOOLEAN NOT NULL DEFAULT false,
    slack_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT scheduled_tasks_time_check CHECK (start_time < end_time),
    CONSTRAINT scheduled_tasks_duration_check CHECK (
        EXTRACT(EPOCH FROM (end_time - start_time))/60 = duration_minutes
    )
);

-- Create indexes for performance
CREATE INDEX idx_operators_department ON operators(department_id);
CREATE INDEX idx_operators_skill_level ON operators(skill_level);
CREATE INDEX idx_operators_availability ON operators(is_available);

CREATE INDEX idx_machines_workcell ON machines(workcell_id);
CREATE INDEX idx_machines_active ON machines(is_active);

CREATE INDEX idx_solved_schedules_status ON solved_schedules(status);
CREATE INDEX idx_solved_schedules_created ON solved_schedules(created_at DESC);

CREATE INDEX idx_scheduled_tasks_schedule ON scheduled_tasks(schedule_id);
CREATE INDEX idx_scheduled_tasks_task ON scheduled_tasks(task_id);
CREATE INDEX idx_scheduled_tasks_times ON scheduled_tasks(start_time, end_time);
CREATE INDEX idx_scheduled_tasks_critical ON scheduled_tasks(is_critical_path);

-- Create update triggers for updated_at timestamps
CREATE TRIGGER trigger_departments_updated_at
    BEFORE UPDATE ON departments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_operators_updated_at
    BEFORE UPDATE ON operators
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_workcells_updated_at
    BEFORE UPDATE ON workcells
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_machines_updated_at
    BEFORE UPDATE ON machines
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_solved_schedules_updated_at
    BEFORE UPDATE ON solved_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_scheduled_tasks_updated_at
    BEFORE UPDATE ON scheduled_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add table comments for documentation
COMMENT ON TABLE departments IS 'Groups operators by skill area for task assignment';
COMMENT ON COLUMN departments.id IS 'Department code (e.g., LASER, ASSEMBLY, QC)';

COMMENT ON TABLE operators IS 'Individual workers with specific skill levels';
COMMENT ON COLUMN operators.skill_level IS 'Proficiency level: novice < competent < proficient < expert';
COMMENT ON COLUMN operators.hourly_rate IS 'Optional hourly rate for cost calculations';

COMMENT ON TABLE workcells IS 'Physical work areas grouping machines with capacity constraints';
COMMENT ON COLUMN workcells.max_concurrent_tasks IS 'Maximum tasks that can run simultaneously';

COMMENT ON TABLE machines IS 'Individual production equipment within workcells';
COMMENT ON COLUMN machines.capabilities IS 'JSON array of machine capabilities';
COMMENT ON COLUMN machines.maintenance_schedule IS 'Scheduled maintenance windows';

COMMENT ON TABLE solved_schedules IS 'Optimization results from OR-Tools solver';
COMMENT ON COLUMN solved_schedules.solver_statistics IS 'Performance metrics from optimization';
COMMENT ON COLUMN solved_schedules.resource_utilization IS 'Utilization percentages by resource';

COMMENT ON TABLE scheduled_tasks IS 'Task assignments with timing and resource allocation';
COMMENT ON COLUMN scheduled_tasks.is_critical_path IS 'Whether task is on the critical path';
COMMENT ON COLUMN scheduled_tasks.slack_minutes IS 'Available slack time before affecting completion';

-- Insert sample departments
INSERT INTO departments (id, name, description) VALUES
    ('LASER', 'Laser Operations', 'Laser cutting and engraving operations'),
    ('ASSEMBLY', 'Assembly', 'Product assembly and integration'),
    ('QC', 'Quality Control', 'Quality inspection and testing'),
    ('PACKAGING', 'Packaging', 'Product packaging and shipping preparation');

-- Insert sample workcells
INSERT INTO workcells (id, name, max_concurrent_tasks) VALUES
    ('CELL-01', 'Laser Cell 1', 1),
    ('CELL-02', 'Laser Cell 2', 1),
    ('CELL-03', 'Assembly Station A', 2),
    ('CELL-04', 'Assembly Station B', 2),
    ('CELL-05', 'QC Station', 1),
    ('CELL-06', 'Packaging Area', 3);