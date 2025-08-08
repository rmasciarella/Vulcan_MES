-- Create TaskMode tables for manufacturing scheduling system
-- 
-- This migration implements the TaskMode architecture to support multiple 
-- execution approaches for tasks with different resource requirements and durations.
-- 
-- Based on manufacturing domain requirements:
-- - ~20 out of 105 tasks will have multiple execution modes
-- - Each mode has different duration and resource requirements
-- - Supports primary/alternative/express/fallback mode types

-- First, create the main task_modes table
CREATE TABLE task_modes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL, -- Will reference tasks table when created
    name VARCHAR(50) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('primary', 'alternative', 'express', 'fallback')),
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes >= 15 AND duration_minutes % 15 = 0),
    priority INTEGER NOT NULL DEFAULT 50 CHECK (priority >= 1 AND priority <= 100),
    is_primary_mode BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1,
    
    -- Constraints
    CONSTRAINT task_modes_name_check CHECK (char_length(name) >= 1),
    CONSTRAINT task_modes_duration_15min_increment CHECK (duration_minutes % 15 = 0)
);

-- Create indexes for performance
CREATE INDEX idx_task_modes_task_id ON task_modes(task_id);
CREATE INDEX idx_task_modes_type ON task_modes(type);
CREATE INDEX idx_task_modes_is_primary ON task_modes(is_primary_mode);
CREATE INDEX idx_task_modes_priority ON task_modes(priority);
CREATE INDEX idx_task_modes_duration ON task_modes(duration_minutes);

-- Create skill requirements table for TaskModes
CREATE TABLE task_mode_skill_requirements (
    task_mode_id UUID NOT NULL REFERENCES task_modes(id) ON DELETE CASCADE,
    skill_level VARCHAR(20) NOT NULL CHECK (skill_level IN ('novice', 'competent', 'proficient', 'expert')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1 AND quantity <= 10),
    
    PRIMARY KEY (task_mode_id, skill_level)
);

-- Create WorkCell requirements table for TaskModes
CREATE TABLE task_mode_workcell_requirements (
    task_mode_id UUID NOT NULL REFERENCES task_modes(id) ON DELETE CASCADE,
    workcell_id VARCHAR(50) NOT NULL CHECK (char_length(workcell_id) >= 1),
    
    PRIMARY KEY (task_mode_id, workcell_id)
);

-- Create indexes for skill and WorkCell requirements
CREATE INDEX idx_task_mode_skills_task_mode_id ON task_mode_skill_requirements(task_mode_id);
CREATE INDEX idx_task_mode_skills_level ON task_mode_skill_requirements(skill_level);
CREATE INDEX idx_task_mode_workcells_task_mode_id ON task_mode_workcell_requirements(task_mode_id);
CREATE INDEX idx_task_mode_workcells_id ON task_mode_workcell_requirements(workcell_id);

-- Create update trigger for task_modes updated_at timestamp
CREATE OR REPLACE FUNCTION update_task_modes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_task_modes_updated_at
    BEFORE UPDATE ON task_modes
    FOR EACH ROW
    EXECUTE FUNCTION update_task_modes_updated_at();

-- Add comments for documentation
COMMENT ON TABLE task_modes IS 'Alternative execution approaches for tasks with different resource requirements and durations';
COMMENT ON COLUMN task_modes.task_id IS 'References the parent task that can be executed in this mode';
COMMENT ON COLUMN task_modes.type IS 'Mode type: primary (default), alternative (secondary), express (faster), fallback (backup)';
COMMENT ON COLUMN task_modes.duration_minutes IS 'Mode-specific execution time in 15-minute increments';
COMMENT ON COLUMN task_modes.priority IS 'Selection priority (1=highest, 100=lowest) for optimization';
COMMENT ON COLUMN task_modes.is_primary_mode IS 'Indicates if this is the default execution mode for the task';

COMMENT ON TABLE task_mode_skill_requirements IS 'Operator skill level requirements for each task mode';
COMMENT ON COLUMN task_mode_skill_requirements.skill_level IS 'Required operator proficiency: novice, competent, proficient, expert';
COMMENT ON COLUMN task_mode_skill_requirements.quantity IS 'Number of operators required at this skill level';

COMMENT ON TABLE task_mode_workcell_requirements IS 'WorkCell requirements for each task mode execution';
COMMENT ON COLUMN task_mode_workcell_requirements.workcell_id IS 'WorkCell identifier that can execute this mode';

-- Business rule constraints
-- Ensure each task has at least one mode (will be enforced at application level)
-- Ensure only one primary mode per task (will be enforced at application level)
-- Ensure express modes have appropriate characteristics (will be enforced at application level)